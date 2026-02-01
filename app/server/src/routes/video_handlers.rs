use axum::{
    extract::Query,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use log::{error, info};
use std::sync::Arc;

use crate::models::{PaginatedVideoList, PaginationParams, VideoList};
use crate::services::{DirectorySync, VideoDao};
use crate::AppState;

/// 列出 public 目录下的所有视频文件和目录（从数据库查询）
pub async fn list_videos(State(state): State<Arc<AppState>>) -> Result<Json<VideoList>, Response> {
    let db_manager = state.db_manager.lock().unwrap();
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

/// 列出 public 目录下的所有视频文件和目录（从数据库查询）- 支持分页
pub async fn list_videos_paginated(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<PaginatedVideoList>, Response> {
    // 验证分页参数
    if params.page == 0 {
        return Err((
            StatusCode::BAD_REQUEST,
            "Page number must be greater than 0",
        )
            .into_response());
    }

    if params.page_size == 0 {
        return Err((StatusCode::BAD_REQUEST, "Page size must be greater than 0").into_response());
    }

    // 限制最大页大小，防止性能问题
    if params.page_size > 1000 {
        return Err((StatusCode::BAD_REQUEST, "Page size cannot exceed 1000").into_response());
    }

    let db_manager = state.db_manager.lock().unwrap();
    let video_dao = VideoDao::new(&db_manager);

    let paginated_videos = video_dao
        .get_root_videos_paginated(
            params.page,
            params.page_size,
            params.search.as_deref(),
            params.sort_by.as_deref(),
            params.sort_order.as_deref(),
        )
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Database error: {}", e),
            )
                .into_response()
        })?;

    Ok(Json(paginated_videos))
}

/// Synchronize database with file system
pub async fn sync_videos(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, Response> {
    // 开始时间
    let start = std::time::Instant::now();
    let db_manager = state.db_manager.lock().unwrap();
    let sync = DirectorySync::new(&db_manager);

    let data_source_dirs = Arc::clone(&state.data_source_dirs);

    match sync.initialize_from_directory_with_progress(&data_source_dirs, false) {
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
            let elapsed = start.elapsed();
            info!("同步消耗时间:{:?}", elapsed);
            Ok(Json(serde_json::json!({
                "success": true,
                "message": "同步完成",
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

/// 删除视频文件（从数据库和物理文件系统中删除）
pub async fn delete_video(
    State(state): State<Arc<AppState>>,
    Query(params): Query<DeleteVideoParams>,
) -> Result<Json<serde_json::Value>, Response> {
    let video_id = params.id;

    // 验证ID是否有效
    if video_id <= 0 {
        return Err((StatusCode::BAD_REQUEST, "Invalid video ID").into_response());
    }

    let db_manager = state.db_manager.lock().unwrap();
    let video_dao = VideoDao::new(&db_manager);

    // 检查视频是否存在
    match video_dao.video_exists_by_id(video_id) {
        Ok(exists) => {
            if !exists {
                return Err((StatusCode::NOT_FOUND, "Video not found in database").into_response());
            }
        }
        Err(e) => {
            error!("Error checking video existence: {}", e);
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Database error: {}", e),
            )
                .into_response());
        }
    }

    // 根据ID获取视频路径
    let video_path = match video_dao.get_video_path_by_id(video_id) {
        Ok(Some(path)) => path,
        Ok(None) => {
            return Err((StatusCode::NOT_FOUND, "Video not found in database").into_response());
        }
        Err(e) => {
            error!("Error getting video path: {}", e);
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Database error: {}", e),
            )
                .into_response());
        }
    };

    // 从数据库中删除记录
    match video_dao.delete_from_database_by_id(video_id) {
        Ok(affected_rows) => {
            if affected_rows == 0 {
                return Err((StatusCode::NOT_FOUND, "Video not found in database").into_response());
            }

            // 物理删除文件
            let full_path = std::path::Path::new(&video_path);
            let mut deleted_files = Vec::new();

            // 删除主视频文件
            if full_path.exists() {
                match std::fs::remove_file(full_path) {
                    Ok(_) => {
                        deleted_files.push(video_path.to_string());
                        info!("Deleted video file: {}", video_path);
                    }
                    Err(e) => {
                        error!("Failed to delete video file {}: {}", video_path, e);
                        // 继续执行，即使文件删除失败
                    }
                }
            }

            // 删除对应的缩略图文件（如果存在）
            let thumbnail_name = full_path
                .file_stem()
                .and_then(|s| s.to_str())
                .map(|s| format!("{}.jpg", s))
                .unwrap_or_default();

            if !thumbnail_name.is_empty() {
                let thumbnail_path = std::path::Path::new("thumbnails").join(&thumbnail_name);
                if thumbnail_path.exists() {
                    match std::fs::remove_file(&thumbnail_path) {
                        Ok(_) => {
                            deleted_files.push(format!("thumbnails/{}", thumbnail_name));
                            info!("Deleted thumbnail file: {}", thumbnail_path.display());
                        }
                        Err(e) => {
                            error!(
                                "Failed to delete thumbnail file {}: {}",
                                thumbnail_path.display(),
                                e
                            );
                        }
                    }
                }
            }

            Ok(Json(serde_json::json!({
                "success": true,
                "message": "Video deleted successfully",
                "deleted_files": deleted_files,
                "database_records_deleted": affected_rows
            })))
        }
        Err(e) => {
            error!("Error deleting video from database: {}", e);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Database error: {}", e),
            )
                .into_response())
        }
    }
}

/// 删除视频请求参数
#[derive(serde::Deserialize)]
pub struct DeleteVideoParams {
    /// 视频ID
    pub id: i64,
}
