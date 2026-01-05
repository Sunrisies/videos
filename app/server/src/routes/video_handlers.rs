use axum::{
    Json,
    extract::Path,
    http::StatusCode,
    response::{IntoResponse, Response},
};

use crate::models::{VideoInfo, VideoList};
use crate::services::{
    format_size, get_created_at, get_thumbnail_web_path, get_web_path, scan_directory_children,
    scan_directory_first_level,
};

/// 列出 public 目录下的所有视频文件和目录（只扫描第一层，不递归）
pub async fn list_videos() -> Result<Json<VideoList>, Response> {
    let public_path = std::path::Path::new("public");
    if !public_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Public directory not found").into_response());
    }

    let items = scan_directory_first_level(public_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Scan error: {}", e),
        )
            .into_response()
    })?;

    let videos: Vec<VideoInfo> = items
        .into_iter()
        .map(|(path, relative_path)| {
            let relative_str = relative_path.to_string_lossy().to_string();
            create_video_info(&path, &relative_str)
        })
        .collect::<Result<Vec<_>, _>>()?;

    Ok(Json(VideoList { videos }))
}

/// 获取指定路径的视频详细信息
pub async fn get_video_details(Path(path): Path<String>) -> Result<Json<VideoInfo>, Response> {
    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = std::path::Path::new("public").join(path);

    if !full_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Path not found").into_response());
    }

    let info = if full_path.is_dir() {
        // 如果是目录，获取目录信息和子文件
        let children = scan_directory_children(&full_path).map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Scan error: {}", e),
            )
                .into_response()
        })?;

        let child_infos: Vec<VideoInfo> = children
            .into_iter()
            .map(|(child_path, child_relative_path)| {
                let relative_str = child_relative_path.to_string_lossy().to_string();
                create_video_info(&child_path, &relative_str)
            })
            .collect::<Result<Vec<_>, _>>()?;

        let mut dir_info = create_video_info(&full_path, path)?;
        dir_info.children = Some(child_infos);
        dir_info
    } else {
        // 如果是文件，直接获取信息
        create_video_info(&full_path, path)?
    };

    Ok(Json(info))
}

/// 创建 VideoInfo 对象
fn create_video_info(path: &std::path::Path, relative_path: &str) -> Result<VideoInfo, Response> {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();

    let web_path = get_web_path(relative_path);
    let thumbnail = get_thumbnail_web_path(relative_path);

    if path.is_dir() {
        // 检查是否是包含 m3u8 的目录
        let has_m3u8 = crate::services::filesystem::has_m3u8_file(path);
        let r#type = if has_m3u8 {
            "hls_directory"
        } else {
            "directory"
        };

        // 获取目录的创建时间
        let created_at = get_created_at(path);

        Ok(VideoInfo {
            name,
            path: web_path,
            r#type: r#type.to_string(),
            children: None,  // 目录的children在调用处设置
            thumbnail: None, // 目录暂时不提供缩略图
            duration: None,
            size: None,
            resolution: None,
            bitrate: None,
            codec: None,
            created_at,
            subtitle: None,
        })
    } else if path.is_file() {
        let extension = path.extension().and_then(|e| e.to_str()).unwrap_or("");
        let r#type = if extension.eq_ignore_ascii_case("mp4") {
            "mp4"
        } else if extension.eq_ignore_ascii_case("m3u8") {
            "m3u8"
        } else if extension.eq_ignore_ascii_case("ts") {
            "ts"
        } else if extension.eq_ignore_ascii_case("vtt") || extension.eq_ignore_ascii_case("srt") {
            "subtitle"
        } else if extension.eq_ignore_ascii_case("jpg")
            || extension.eq_ignore_ascii_case("png")
            || extension.eq_ignore_ascii_case("gif")
        {
            "image"
        } else {
            "unknown"
        };

        // 获取文件元数据
        let metadata = std::fs::metadata(path).ok();
        let size = metadata.as_ref().map(|m| format_size(m.len()));
        let created_at =
            metadata.and_then(|m| crate::services::filesystem::get_systemtime_created(&m));

        // 如果是字幕文件，设置 subtitle 字段
        let subtitle = if r#type == "subtitle" {
            Some(web_path.clone())
        } else {
            None
        };

        // 对于 MP4 文件，尝试获取更多信息（这里返回 None，实际应用中可以使用 ffprobe 等工具）
        let (duration, resolution, bitrate, codec) = if r#type == "mp4" {
            // 这里可以集成 ffprobe 或其他视频分析工具
            // 暂时返回 None
            (None, None, None, None)
        } else {
            (None, None, None, None)
        };

        Ok(VideoInfo {
            name,
            path: web_path,
            r#type: r#type.to_string(),
            children: None, // 文件类型永远没有children
            thumbnail,
            duration,
            size,
            resolution,
            bitrate,
            codec,
            created_at,
            subtitle,
        })
    } else {
        Err((StatusCode::BAD_REQUEST, "Invalid path type").into_response())
    }
}
