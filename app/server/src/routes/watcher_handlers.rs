use axum::{
    Json,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use std::sync::Arc;

use crate::AppState;

/// 文件监听器状态响应
#[derive(serde::Serialize)]
pub struct WatcherStatus {
    running: bool,
    message: String,
}

/// 启动文件监听器
pub async fn start_watcher(
    State(state): State<Arc<AppState>>,
) -> Result<Json<WatcherStatus>, Response> {
    let mut watcher = state.file_watcher.lock().unwrap();

    if watcher.is_watching() {
        return Ok(Json(WatcherStatus {
            running: true,
            message: "文件监听器已经在运行".to_string(),
        }));
    }

    match watcher.start("public") {
        Ok(_) => Ok(Json(WatcherStatus {
            running: true,
            message: "文件监听器已启动".to_string(),
        })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("启动监听器失败: {}", e),
        )
            .into_response()),
    }
}

/// 停止文件监听器
pub async fn stop_watcher(
    State(state): State<Arc<AppState>>,
) -> Result<Json<WatcherStatus>, Response> {
    let mut watcher = state.file_watcher.lock().unwrap();

    if !watcher.is_watching() {
        return Ok(Json(WatcherStatus {
            running: false,
            message: "文件监听器未运行".to_string(),
        }));
    }

    match watcher.stop() {
        Ok(_) => Ok(Json(WatcherStatus {
            running: false,
            message: "文件监听器已停止".to_string(),
        })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("停止监听器失败: {}", e),
        )
            .into_response()),
    }
}

/// 获取文件监听器状态
pub async fn get_watcher_status(State(state): State<Arc<AppState>>) -> Json<WatcherStatus> {
    let watcher = state.file_watcher.lock().unwrap();
    let running = watcher.is_watching();

    Json(WatcherStatus {
        running,
        message: if running {
            "文件监听器正在运行".to_string()
        } else {
            "文件监听器已停止".to_string()
        },
    })
}
