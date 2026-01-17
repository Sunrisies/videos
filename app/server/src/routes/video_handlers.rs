use axum::{
    extract::Query,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use log::info;
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
