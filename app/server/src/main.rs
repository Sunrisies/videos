mod models;
mod routes;
mod services;
mod utils;

use axum::{
    Router,
    http::{HeaderName, HeaderValue},
    routing::get,
};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tower_http::{cors::CorsLayer, services::ServeDir};

// Global database manager instance
pub struct AppState {
    pub db_manager: Arc<Mutex<services::VideoDbManager>>,
}

#[tokio::main]
async fn main() {
    // 初始化缩略图目录
    services::initialize_thumbnails();

    // Initialize database
    let db_manager =
        services::VideoDbManager::new("videos.db").expect("Failed to initialize database");

    // Scan and populate database from public directory
    if let Err(e) = db_manager.initialize_from_directory("public") {
        println!(
            "Warning: Failed to initialize database from public directory: {}",
            e
        );
    } else {
        println!("Database initialized successfully");
    }

    // Create shared state
    let shared_state = Arc::new(Mutex::new(db_manager));

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
        // 同步数据库
        .route("/api/sync", get(routes::sync_videos))
        // 静态文件服务，public 目录下的文件可以通过 /public/... 访问
        .nest_service("/public", ServeDir::new("public"))
        // 静态文件服务，thumbnails 目录下的文件可以通过 /thumbnails/... 访问
        .nest_service("/thumbnails", ServeDir::new("thumbnails"))
        .with_state(shared_state)
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    println!("listening on {}", addr);
    println!("CORS enabled - allowing all origins");
    println!("Thumbnails directory initialized");
    println!("Database initialized");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
