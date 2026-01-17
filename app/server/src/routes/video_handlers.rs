use axum::{
    extract::Path,
    extract::Query,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use log::info;
use std::sync::Arc;

use crate::models::{PaginatedVideoList, PaginationParams, VideoInfo, VideoList};
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

/// 获取指定路径的视频详细信息
pub async fn get_video_details(
    State(state): State<Arc<AppState>>,
    Path(path): Path<String>,
) -> Result<Json<VideoInfo>, Response> {
    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = std::path::Path::new("public").join(path);
    let full_path_str = full_path.to_string_lossy().to_string();

    let db_manager = state.db_manager.lock().unwrap();
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

/// 获取指定路径的视频详细信息 - 支持分页
pub async fn get_video_details_paginated(
    State(state): State<Arc<AppState>>,
    Path(path): Path<String>,
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

    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = std::path::Path::new("public").join(path);
    let full_path_str = full_path.to_string_lossy().to_string();

    let db_manager = state.db_manager.lock().unwrap();
    let video_dao = VideoDao::new(&db_manager);

    // First check if the path exists in database
    let info_opt = video_dao.get_video_by_path(&full_path_str).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Database error: {}", e),
        )
            .into_response()
    })?;

    if let Some(info) = info_opt {
        // If it's a directory or m3u8, get its children with pagination
        if info.r#type == "directory" || info.r#type == "m3u8" {
            let paginated_children = video_dao
                .get_children_paginated(
                    &full_path_str,
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

            return Ok(Json(paginated_children));
        }

        // For non-directory types, return empty result
        return Ok(Json(PaginatedVideoList {
            videos: Vec::new(),
            pagination: crate::models::PaginationInfo {
                page: params.page,
                page_size: params.page_size,
                total: 0,
                total_pages: 0,
                has_next: false,
                has_prev: false,
            },
        }));
    }

    // If not in database, return not found
    Err((StatusCode::NOT_FOUND, "Path not found in database").into_response())
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
