use axum::{
    Json,
    extract::Path,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use std::sync::{Arc, Mutex};

use crate::models::{VideoInfo, VideoList};
use crate::services::{DirectorySync, VideoDao, VideoDbManager};

/// 列出 public 目录下的所有视频文件和目录（从数据库查询）
pub async fn list_videos(
    State(state): State<Arc<Mutex<VideoDbManager>>>,
) -> Result<Json<VideoList>, Response> {
    let db_manager = state.lock().unwrap();
    let video_dao = VideoDao::new(&db_manager);

    let videos = video_dao.get_root_videos().map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Database error: {}", e),
        )
            .into_response()
    })?;

    Ok(Json(VideoList { videos }))
}

/// 获取指定路径的视频详细信息
pub async fn get_video_details(
    State(state): State<Arc<Mutex<VideoDbManager>>>,
    Path(path): Path<String>,
) -> Result<Json<VideoInfo>, Response> {
    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = std::path::Path::new("public").join(path);
    let full_path_str = full_path.to_string_lossy().to_string();

    let db_manager = state.lock().unwrap();
    let video_dao = VideoDao::new(&db_manager);

    // First check if the path exists in database
    let info_opt = video_dao.get_video_by_path(&full_path_str).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Database error: {}", e),
        )
            .into_response()
    })?;

    if let Some(mut info) = info_opt {
        // If it's a directory, get its children
        if info.r#type == "directory" || info.r#type == "m3u8" {
            let children = video_dao.get_children(&full_path_str).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("Database error: {}", e),
                )
                    .into_response()
            })?;
            info.children = Some(children);
        }

        return Ok(Json(info));
    }

    // If not in database, return not found
    Err((StatusCode::NOT_FOUND, "Path not found in database").into_response())
}

/// Synchronize database with file system
pub async fn sync_videos(
    State(state): State<Arc<Mutex<VideoDbManager>>>,
) -> Result<Json<serde_json::Value>, Response> {
    let db_manager = state.lock().unwrap();
    let sync = DirectorySync::new(&db_manager);

    match sync.sync_directory("public") {
        Ok(_) => {
            // Get updated count
            let video_dao = VideoDao::new(&db_manager);
            let videos = video_dao.get_root_videos().map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("Database error: {}", e),
                )
                    .into_response()
            })?;

            Ok(Json(serde_json::json!({
                "success": true,
                "message": "Database synchronized successfully",
                "count": videos.len()
            })))
        }
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Sync error: {}", e),
        )
            .into_response()),
    }
}
