mod models;
mod routes;
mod services;
mod utils;

use axum::{
    Router,
    http::{HeaderName, HeaderValue},
    routing::get,
};
use log::info;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tower_http::{cors::CorsLayer, services::ServeDir};

use crate::{
    services::{FileWatcher, VideoDbManager, init_task_queue},
    utils::init_logger,
};

// 统一的应用状态
pub struct AppState {
    pub db_manager: Arc<Mutex<VideoDbManager>>,
    pub file_watcher: Arc<Mutex<FileWatcher>>,
}

#[tokio::main]
async fn main() {
    init_logger(); // 初始化日志

    // 初始化后台任务队列（最大4个并发任务）
    init_task_queue(4);

    // 从环境变量获取数据源目录，如果未设置则默认为"public"
    let data_source_dir = std::env::var("DATA_SOURCE_DIR").unwrap_or_else(|_| "public".to_string());
    println!("使用数据源目录: {}", data_source_dir);

    // 初始化缩略图目录
    services::initialize_thumbnails_with_source(&data_source_dir);

    // 初始化数据库
    let db_manager = VideoDbManager::new("videos.db").expect("Failed to initialize database");

    // 从指定目录中初始化数据库
    let sync = services::DirectorySync::new(&db_manager);
    if let Err(e) = sync.initialize_from_directory(&data_source_dir, false) {
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
    });

    // 创建 CORS 中间件 - 允许所有来源
    let cors = CorsLayer::new()
        .allow_origin(HeaderValue::from_static("*"))
        .allow_methods(vec![
            axum::http::Method::GET,
            axum::http::Method::POST,
            axum::http::Method::OPTIONS,
        ])
        .allow_headers(vec![HeaderName::from_static("*")]);

    // 创建路由，添加静态文件服务和 CORS
    let app = Router::new()
        .route("/", get(|| async { "Hello, World!" }))
        // 列出所有视频文件和目录
        .route("/api/videos", get(routes::list_videos))
        // 获取指定路径的详细信息（包括子文件）
        .route("/api/videos/*path", get(routes::get_video_details))
        // 手动同步数据库
        .route("/api/sync", get(routes::sync_videos))
        // 文件监听器控制端点
        .route("/api/watcher/start", get(routes::start_watcher))
        .route("/api/watcher/stop", get(routes::stop_watcher))
        .route("/api/watcher/status", get(routes::get_watcher_status))
        // 任务队列状态端点
        .route("/api/tasks/status", get(routes::get_task_queue_status))
        // 静态文件服务，数据源目录下的文件可以通过 /public/... 访问
        .nest_service("/public", ServeDir::new(&data_source_dir))
        // 静态文件服务，thumbnails 目录下的文件可以通过 /thumbnails/... 访问
        .nest_service("/thumbnails", ServeDir::new("thumbnails"))
        .with_state(app_state)
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 3003));
    info!("listening on {}", addr);
    info!("CORS enabled - allowing all origins");
    info!("Thumbnails directory initialized");
    info!("Database initialized");
    info!("Background task queue initialized (max 4 concurrent)");
    info!("");
    info!("Available API endpoints:");
    info!("  GET  /api/videos              - List all videos");
    info!("  GET  /api/videos/[path]       - Get video details");
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
