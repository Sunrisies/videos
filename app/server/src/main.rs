use axum::{
    Json, Router,
    extract::Path,
    http::{HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
};
use serde::Serialize;
use std::net::SocketAddr;
use std::path::Path as StdPath;
use std::time::UNIX_EPOCH;
use tower_http::{cors::CorsLayer, services::ServeDir};
use walkdir::WalkDir;

#[derive(Serialize)]
struct VideoInfo {
    name: String,
    path: String,
    r#type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    children: Option<Vec<VideoInfo>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    thumbnail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    duration: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    resolution: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bitrate: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    codec: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    subtitle: Option<String>,
}

#[derive(Serialize)]
struct VideoList {
    videos: Vec<VideoInfo>,
}

#[tokio::main]
async fn main() {
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
        .route("/api/videos", get(list_videos))
        // 获取指定路径的详细信息（包括子文件）
        .route("/api/videos/*path", get(get_video_details))
        // 静态文件服务，public 目录下的文件可以通过 /public/... 访问
        .nest_service("/public", ServeDir::new("public"))
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    println!("listening on {}", addr);
    println!("CORS enabled - allowing all origins");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

/// 列出 public 目录下的所有视频文件和目录
async fn list_videos() -> Result<Json<VideoList>, Response> {
    let public_path = StdPath::new("public");
    if !public_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Public directory not found").into_response());
    }

    let videos = scan_directory(public_path, 1)?; // 只扫描第一层
    Ok(Json(VideoList { videos }))
}

/// 获取指定路径的视频详细信息
async fn get_video_details(Path(path): Path<String>) -> Result<Json<VideoInfo>, Response> {
    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = StdPath::new("public").join(path);

    if !full_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Path not found").into_response());
    }

    let info = get_video_info(&full_path, path, 2)?; // 递归深度为2，获取子目录信息
    Ok(Json(info))
}

/// 扫描目录并生成视频信息列表
fn scan_directory(base_path: &StdPath, max_depth: usize) -> Result<Vec<VideoInfo>, Response> {
    let mut videos = Vec::new();

    for entry in WalkDir::new(base_path)
        .max_depth(max_depth)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        // 跳过根目录本身
        if path == base_path {
            continue;
        }

        // 只处理第一层
        if let Ok(relative_path) = path.strip_prefix(base_path) {
            if relative_path.components().count() > 1 {
                continue;
            }

            if is_video_or_container(path) {
                let info = get_video_info(path, relative_path.to_str().unwrap(), 0)?;
                videos.push(info);
            }
        }
    }

    Ok(videos)
}

/// 获取单个视频或目录的信息
fn get_video_info(
    path: &StdPath,
    relative_path: &str,
    child_depth: usize,
) -> Result<VideoInfo, Response> {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();

    let public_path = StdPath::new("public");
    let full_relative_path = public_path.join(relative_path);
    let web_path = format!("/public/{}", full_relative_path.display());

    if path.is_dir() {
        // 检查是否是包含 m3u8 的目录
        let has_m3u8 = has_m3u8_file(path);
        let r#type = if has_m3u8 {
            "hls_directory"
        } else {
            "directory"
        };

        let children = if child_depth > 0 {
            Some(scan_subdirectory(path, child_depth)?)
        } else {
            None
        };

        // 获取目录的创建时间
        let created_at = get_created_at(path);

        Ok(VideoInfo {
            name,
            path: web_path,
            r#type: r#type.to_string(),
            children,
            thumbnail: None,
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
        } else {
            "unknown"
        };

        // 获取文件元数据
        let metadata = std::fs::metadata(path).ok();
        let size = metadata.as_ref().map(|m| format_size(m.len()));
        let created_at = metadata.and_then(|m| get_systemtime_created(&m));

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

        // 生成缩略图路径（如果有）
        let thumbnail = if r#type == "mp4" {
            // 假设缩略图在同一目录下，文件名为 video_name.jpg
            let thumb_path = path.with_extension("jpg");
            if thumb_path.exists() {
                Some(format!(
                    "/public/{}",
                    thumb_path
                        .strip_prefix(StdPath::new("public"))
                        .unwrap()
                        .display()
                ))
            } else {
                None
            }
        } else {
            None
        };

        Ok(VideoInfo {
            name,
            path: web_path,
            r#type: r#type.to_string(),
            children: None,
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

/// 扫描子目录
fn scan_subdirectory(base_path: &StdPath, depth: usize) -> Result<Vec<VideoInfo>, Response> {
    let mut children = Vec::new();

    for entry in WalkDir::new(base_path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        if path == base_path {
            continue;
        }

        if is_video_or_container(path) {
            let relative_path = path.strip_prefix(StdPath::new("public")).unwrap();
            let info = get_video_info(path, relative_path.to_str().unwrap(), depth - 1)?;
            children.push(info);
        }
    }

    Ok(children)
}

/// 检查路径是否是视频文件或视频容器（目录）
fn is_video_or_container(path: &StdPath) -> bool {
    if path.is_dir() {
        // 目录如果包含 m3u8 文件或者包含视频文件，则视为有效
        return has_m3u8_file(path) || has_video_file(path);
    }
    if path.is_file() {
        let extension = path.extension().and_then(|e| e.to_str()).unwrap_or("");
        return extension.eq_ignore_ascii_case("mp4")
            || extension.eq_ignore_ascii_case("m3u8")
            || extension.eq_ignore_ascii_case("ts")
            || extension.eq_ignore_ascii_case("vtt")
            || extension.eq_ignore_ascii_case("srt");
    }
    false
}

/// 检查目录是否包含 m3u8 文件
fn has_m3u8_file(path: &StdPath) -> bool {
    if !path.is_dir() {
        return false;
    }
    WalkDir::new(path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
        .any(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| ext.eq_ignore_ascii_case("m3u8"))
                .unwrap_or(false)
        })
}

/// 检查目录是否包含视频文件
fn has_video_file(path: &StdPath) -> bool {
    if !path.is_dir() {
        return false;
    }
    WalkDir::new(path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
        .any(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| ext.eq_ignore_ascii_case("mp4"))
                .unwrap_or(false)
        })
}

/// 获取文件创建时间
fn get_created_at(path: &StdPath) -> Option<String> {
    std::fs::metadata(path)
        .ok()
        .and_then(|m| get_systemtime_created(&m))
}

/// 从 SystemTime 获取可读的创建时间字符串
fn get_systemtime_created(metadata: &std::fs::Metadata) -> Option<String> {
    metadata.created().ok().and_then(|time| {
        let duration = time.duration_since(UNIX_EPOCH).ok()?;
        let seconds = duration.as_secs();

        // 手动格式化时间
        let days = seconds / 86400;
        let remaining = seconds % 86400;
        let hours = remaining / 3600;
        let remaining = remaining % 3600;
        let minutes = remaining / 60;
        let secs = remaining % 60;

        // 计算年月日（简化计算，从1970年开始）
        let year = 1970 + (days / 365);
        let day_of_year = days % 365;

        // 简化的月份计算
        let month = (day_of_year / 30) + 1;
        let day = (day_of_year % 30) + 1;

        Some(format!(
            "{:04}-{:02}-{:02} {:02}:{:02}:{:02}",
            year, month, day, hours, minutes, secs
        ))
    })
}

/// 格式化文件大小
fn format_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.2} GB", (bytes as f64) / (GB as f64))
    } else if bytes >= MB {
        format!("{:.2} MB", (bytes as f64) / (MB as f64))
    } else if bytes >= KB {
        format!("{:.2} KB", (bytes as f64) / (KB as f64))
    } else {
        format!("{} B", bytes)
    }
}
