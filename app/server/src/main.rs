mod models;
mod routes;
mod services;
mod utils;

use axum::{
    http::{HeaderName, HeaderValue},
    routing::{delete, get},
    Router,
};
use log::info;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tower_http::{cors::CorsLayer, services::ServeDir};

use crate::{
    services::{init_task_queue, FileWatcher, VideoDbManager},
    utils::init_logger,
};

// 统一的应用状态
pub struct AppState {
    pub db_manager: Arc<Mutex<VideoDbManager>>,
    pub file_watcher: Arc<Mutex<FileWatcher>>,
    pub data_source_dirs: Arc<Vec<String>>,
}

#[tokio::main]
async fn main() {
    init_logger(); // 初始化日志

    // 初始化后台任务队列（最大4个并发任务）
    init_task_queue(4);
    // G:/videos/app/server/public;
    // 从环境变量获取数据源目录，支持多个目录（用分号分隔）
    let data_source_dirs_str =
        std::env::var("DATA_SOURCE_DIRS").unwrap_or_else(|_| "F:/public".to_string());
    let data_source_dirs: Vec<String> = data_source_dirs_str
        .split(';')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    if data_source_dirs.is_empty() {
        panic!("至少需要配置一个数据源目录");
    }

    println!("使用数据源目录: {}", data_source_dirs.join(", "));

    // 初始化缩略图目录
    services::initialize_thumbnails_with_source(&data_source_dirs);

    // 初始化数据库
    let db_manager = VideoDbManager::new("videos.db").expect("Failed to initialize database");

    // 从指定目录中初始化数据库
    let sync = services::DirectorySync::new(&db_manager);
    if let Err(e) = sync.initialize_from_directory(&data_source_dirs, false) {
        println!("警告：无法从数据源目录初始化数据库: {}", e);
    } else {
        println!("数据库初始化成功");
    }

    // 创建共享状态
    let db_manager_arc = Arc::new(Mutex::new(db_manager));

    // 创建文件监听器
    let file_watcher = FileWatcher::new(db_manager_arc.clone());
    let file_watcher_arc = Arc::new(Mutex::new(file_watcher));

    // 创建统一的应用状态
    let app_state = Arc::new(AppState {
        db_manager: db_manager_arc,
        file_watcher: file_watcher_arc,
        data_source_dirs: Arc::new(data_source_dirs.clone()),
    });

    // 创建 CORS 中间件 - 允许所有来源
    let cors = CorsLayer::new()
        .allow_origin(HeaderValue::from_static("*"))
        .allow_methods(vec![
            axum::http::Method::GET,
            axum::http::Method::POST,
            axum::http::Method::DELETE,
            axum::http::Method::OPTIONS,
        ])
        .allow_headers(vec![HeaderName::from_static("*")]);

    // 创建路由，添加静态文件服务和 CORS
    let mut app = Router::new()
        .route("/", get(|| async { "Hello, World!" }))
        // 列出所有视频文件和目录
        .route("/api/videos", get(routes::list_videos))
        // 列出所有视频文件和目录 - 支持分页
        .route("/api/videos/paginated", get(routes::list_videos_paginated))
        // 删除视频文件（从数据库和物理文件系统中删除）
        .route("/api/videos/delete", delete(routes::delete_video))
        // 手动同步数据库
        .route("/api/sync", get(routes::sync_videos))
        // 文件监听器控制端点
        .route("/api/watcher/start", get(routes::start_watcher))
        .route("/api/watcher/stop", get(routes::stop_watcher))
        .route("/api/watcher/status", get(routes::get_watcher_status))
        // 任务队列状态端点
        .route("/api/tasks/status", get(routes::get_task_queue_status))
        // 静态文件服务，thumbnails 目录下的文件可以通过 /thumbnails/... 访问
        .nest_service("/thumbnails", ServeDir::new("thumbnails"))
        .with_state(app_state)
        .layer(cors);

    // 为每个数据源目录创建静态文件服务路由
    for (index, dir) in data_source_dirs.iter().enumerate() {
        let route_path = format!("/public/disk{}", index + 1);
        app = app.nest_service(&route_path, ServeDir::new(dir));
        info!("静态文件服务: {} -> {}", route_path, dir);
    }

    let addr = SocketAddr::from(([0, 0, 0, 0], 3003));
    info!("listening on {}", addr);
    info!("CORS enabled - allowing all origins");
    info!("Thumbnails directory initialized");
    info!("Database initialized");
    info!("Background task queue initialized (max 4 concurrent)");
    info!("");
    info!("Available API endpoints:");
    info!("  GET  /api/videos              - List all videos");
    info!("  GET  /api/videos/paginated    - List all videos with pagination");
    info!("  DELETE /api/videos/delete     - Delete video file (database + physical file)");
    info!("  GET  /api/sync                - Manual database sync");
    info!("  GET  /api/watcher/start       - Start file watcher");
    info!("  GET  /api/watcher/stop        - Stop file watcher");
    info!("  GET  /api/watcher/status      - Get watcher status");
    info!("  GET  /api/tasks/status        - Get task queue status");
    info!("");
    info!("File watcher is NOT running by default. Use /api/watcher/start to enable auto-sync.");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
