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
use std::sync::{Arc, Mutex};
use std::{net::SocketAddr, path::PathBuf};
use tower_http::{cors::CorsLayer, services::ServeDir};

use crate::{
    services::{init_task_queue, VideoDbManager},
    utils::init_logger,
};
// 定义一个简单的结构体来存储映射关系
#[derive(Debug, Clone)]
pub struct DiskMapping {
    pub route_path: String,    // 例如 "/public/disk1"
    pub physical_path: String, // 例如 "D:/videos"
}

// 统一的应用状态
pub struct AppState {
    pub db_manager: Arc<Mutex<VideoDbManager>>,
    pub data_source_dirs: Arc<Vec<DiskMapping>>,
}

#[tokio::main]
async fn main() {
    init_logger(); // 初始化日志
                   // 获取项目根目录的绝对路径
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let env_path = manifest_dir.join(".env");

    // 打印路径以便调试
    println!("尝试加载 .env 文件，路径: {:?}", env_path);
    // 初始化后台任务队列（最大4个并发任务）
    init_task_queue(4);
    match dotenvy::from_path(&env_path) {
        Ok(_) => println!(".env 文件加载成功"),
        Err(e) => println!(".env 文件加载失败: {}", e),
    }
    // G:/videos/app/server/public;
    // 从环境变量获取数据源目录，支持多个目录（用分号分隔）
    let data_source_dirs_str =
        std::env::var("DATA_SOURCE_DIRS").unwrap_or_else(|_| "F:/public".to_string());
    info!("DATA_SOURCE_DIRS: {}", data_source_dirs_str);
    // 2. 解析为 Vec<String> (纯物理路径列表)
    let physical_dirs: Vec<String> = data_source_dirs_str
        .split(';')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    if physical_dirs.is_empty() {
        panic!("至少需要配置一个数据源目录");
    }
    let disk_mappings: Vec<DiskMapping> = physical_dirs
        .iter()
        .enumerate()
        .map(|(index, dir)| DiskMapping {
            route_path: format!("/public/disk{}", index + 1),
            physical_path: dir.clone(),
        })
        .collect();

    // 初始化缩略图目录
    services::initialize_thumbnails_with_source(&physical_dirs);

    // 初始化数据库
    let db_manager = VideoDbManager::new("videos.db").expect("Failed to initialize database");

    // 从指定目录中初始化数据库
    let sync = services::DirectorySync::new(&db_manager);
    if let Err(e) = sync.initialize_from_directory(&disk_mappings, false) {
        println!("警告：无法从数据源目录初始化数据库: {}", e);
    } else {
        println!("数据库初始化成功");
    }

    // 创建共享状态
    let db_manager_arc = Arc::new(Mutex::new(db_manager));

    // 7. 构建 disk_mappings (路由 -> 物理路径)
    let app_state = Arc::new(AppState {
        db_manager: db_manager_arc,
        data_source_dirs: Arc::new(disk_mappings),
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
        // 任务队列状态端点
        .route("/api/tasks/status", get(routes::get_task_queue_status))
        // 静态文件服务，thumbnails 目录下的文件可以通过 /thumbnails/... 访问
        .nest_service("/thumbnails", ServeDir::new("thumbnails"))
        .layer(cors);

    let state_clone = app_state.clone();
    for mapping in state_clone.data_source_dirs.iter() {
        app = app.nest_service(&mapping.route_path, ServeDir::new(&mapping.physical_path));
        info!(
            "静态文件服务: {} -> {}",
            mapping.route_path, mapping.physical_path
        );
    }

    let app = app.with_state(app_state);
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
    info!("  GET  /api/tasks/status        - Get task queue status");
    info!("");
    info!("File watcher is NOT running by default. Use /api/watcher/start to enable auto-sync.");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
