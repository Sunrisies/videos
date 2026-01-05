use axum::{
    Json, Router,
    extract::Path,
    http::{HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
};
use serde::Serialize;
use std::net::SocketAddr;
use std::path::{Path as StdPath, PathBuf};
use std::process::Command;
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
    // 初始化缩略图目录
    initialize_thumbnails();

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
        // 静态文件服务，thumbnails 目录下的文件可以通过 /thumbnails/... 访问
        .nest_service("/thumbnails", ServeDir::new("thumbnails"))
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    println!("listening on {}", addr);
    println!("CORS enabled - allowing all origins");
    println!("Thumbnails directory initialized");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

/// 初始化缩略图目录
fn initialize_thumbnails() {
    let thumbnails_path = StdPath::new("thumbnails");

    // 创建 thumbnails 目录
    if !thumbnails_path.exists() {
        std::fs::create_dir(thumbnails_path).expect("Failed to create thumbnails directory");
        println!("Created thumbnails directory");
    }

    // 扫描 public 目录并生成缩略图（递归所有子目录）
    let public_path = StdPath::new("public");
    if public_path.exists() {
        println!("Scanning public directory recursively for files to generate thumbnails...");
        generate_thumbnails_for_directory(public_path, thumbnails_path);
    } else {
        println!("Warning: public directory does not exist");
    }
}

/// 为目录及其所有子目录中的文件生成缩略图
fn generate_thumbnails_for_directory(public_path: &StdPath, thumbnails_path: &StdPath) {
    for entry in WalkDir::new(public_path).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();

        // 跳过根目录本身
        if path == public_path {
            continue;
        }

        if path.is_file() {
            let relative_path = path.strip_prefix(public_path).unwrap();
            let thumbnail_path = thumbnails_path.join(relative_path).with_extension("jpg");

            // 创建缩略图所在的子目录
            if let Some(parent) = thumbnail_path.parent() {
                if !parent.exists() {
                    if let Err(e) = std::fs::create_dir_all(parent) {
                        println!("Failed to create directory {}: {}", parent.display(), e);
                        continue;
                    }
                }
            }

            // 如果缩略图已存在，跳过
            if thumbnail_path.exists() {
                continue;
            }

            // 根据文件类型生成缩略图
            let extension = path
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_lowercase();

            // 视频文件和m3u8文件都生成缩略图
            if extension == "mp4"
                || extension == "avi"
                || extension == "mkv"
                || extension == "mov"
                || extension == "m3u8"
            {
                // 视频文件 - 使用 ffmpeg 生成缩略图
                generate_video_thumbnail(&path, &thumbnail_path);
            } else if extension == "jpg"
                || extension == "jpeg"
                || extension == "png"
                || extension == "gif"
            {
                // 图片文件 - 直接复制
                generate_image_thumbnail(&path, &thumbnail_path);
            } else if extension == "ts" || extension == "vtt" || extension == "srt" {
                // 媒体相关文件 - 生成默认图标
                generate_default_thumbnail(&thumbnail_path, "media");
            } else {
                // 其他文件 - 生成默认图标
                generate_default_thumbnail(&thumbnail_path, "file");
            }
        }
    }
}

/// 为视频文件生成缩略图
fn generate_video_thumbnail(video_path: &StdPath, thumbnail_path: &StdPath) {
    // 使用 ffmpeg 从视频的第一帧生成缩略图
    // 命令: ffmpeg -i input.mp4 -ss 00:00:01 -vframes 1 -q:v 2 output.jpg
    let output = thumbnail_path.to_string_lossy().to_string();
    let input = video_path.to_string_lossy().to_string();

    match Command::new("ffmpeg")
        .args(&[
            "-i", &input, "-ss", "00:00:01", "-vframes", "1", "-q:v", "2",
            "-y", // 覆盖输出文件
            &output,
        ])
        .output()
    {
        Ok(_) => {
            if thumbnail_path.exists() {
                println!("✓ Generated thumbnail for video: {}", video_path.display());
            } else {
                println!(
                    "✗ Failed to generate thumbnail for video: {}",
                    video_path.display()
                );
            }
        }
        Err(e) => {
            println!("✗ FFmpeg error for {}: {}", video_path.display(), e);
            // 生成默认图标作为备用
            generate_default_thumbnail(thumbnail_path, "video");
        }
    }
}

/// 为图片文件生成缩略图
fn generate_image_thumbnail(image_path: &StdPath, thumbnail_path: &StdPath) {
    // 使用 ffmpeg 将图片转换为缩略图（可以调整大小）
    // 命令: ffmpeg -i input.jpg -vf "scale=320:240" output.jpg
    let output = thumbnail_path.to_string_lossy().to_string();
    let input = image_path.to_string_lossy().to_string();

    match Command::new("ffmpeg")
        .args(&["-i", &input, "-vf", "scale=320:240", "-y", &output])
        .output()
    {
        Ok(_) => {
            if thumbnail_path.exists() {
                println!("✓ Generated thumbnail for image: {}", image_path.display());
            } else {
                println!(
                    "✗ Failed to generate thumbnail for image: {}",
                    image_path.display()
                );
            }
        }
        Err(e) => {
            println!("✗ FFmpeg error for {}: {}", image_path.display(), e);
            // 直接复制原图作为备用
            if let Err(copy_err) = std::fs::copy(image_path, thumbnail_path) {
                println!(
                    "✗ Failed to copy image {}: {}",
                    image_path.display(),
                    copy_err
                );
            } else {
                println!("✓ Copied image as thumbnail: {}", image_path.display());
            }
        }
    }
}

/// 生成默认缩略图（简单颜色块 + 文字）
fn generate_default_thumbnail(thumbnail_path: &StdPath, file_type: &str) {
    // 创建一个简单的 SVG 作为默认缩略图
    let svg_content = match file_type {
        "video" => {
            "<svg width=\"320\" height=\"240\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"240\" fill=\"#4A90E2\"/><text x=\"160\" y=\"120\" font-family=\"Arial\" font-size=\"24\" fill=\"white\" text-anchor=\"middle\">VIDEO</text></svg>"
        }
        "media" => {
            "<svg width=\"320\" height=\"240\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"240\" fill=\"#F5A623\"/><text x=\"160\" y=\"120\" font-family=\"Arial\" font-size=\"24\" fill=\"white\" text-anchor=\"middle\">MEDIA</text></svg>"
        }
        _ => {
            "<svg width=\"320\" height=\"240\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"240\" fill=\"#95A5A6\"/><text x=\"160\" y=\"120\" font-family=\"Arial\" font-size=\"24\" fill=\"white\" text-anchor=\"middle\">FILE</text></svg>"
        }
    };

    // 使用 ffmpeg 将 SVG 转换为 JPG
    let svg_path = thumbnail_path.with_extension("svg");
    std::fs::write(&svg_path, svg_content).ok();

    let output = thumbnail_path.to_string_lossy().to_string();
    let input = svg_path.to_string_lossy().to_string();

    match Command::new("ffmpeg")
        .args(&["-i", &input, "-y", &output])
        .output()
    {
        Ok(_) => {
            let _ = std::fs::remove_file(&svg_path); // 删除临时 SVG
            if thumbnail_path.exists() {
                println!(
                    "✓ Generated default thumbnail: {}",
                    thumbnail_path.display()
                );
            }
        }
        Err(e) => {
            println!("✗ Failed to generate default thumbnail: {}", e);
            let _ = std::fs::remove_file(&svg_path);
        }
    }
}

/// 列出 public 目录下的所有视频文件和目录（递归扫描）
async fn list_videos() -> Result<Json<VideoList>, Response> {
    let public_path = StdPath::new("public");
    if !public_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Public directory not found").into_response());
    }

    let videos = scan_directory_recursive(public_path, public_path, 0)?;
    Ok(Json(VideoList { videos }))
}

/// 递归扫描目录，生成视频信息列表
fn scan_directory_recursive(
    base_path: &StdPath,
    current_path: &StdPath,
    depth: usize,
) -> Result<Vec<VideoInfo>, Response> {
    let mut items = Vec::new();

    for entry in WalkDir::new(current_path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();

        // 跳过当前目录本身
        if path == current_path {
            continue;
        }

        if path.is_dir() {
            // 递归处理子目录
            let relative_path = path.strip_prefix(base_path).unwrap();
            let children = scan_directory_recursive(base_path, path, depth + 1)?;

            // 只有包含视频文件的目录才添加到结果中
            if !children.is_empty() {
                let info =
                    get_video_info(path, relative_path.to_str().unwrap(), 0, Some(children))?;
                items.push(info);
            }
        } else if path.is_file() {
            // 检查是否是视频相关文件
            if is_video_or_container(path) {
                let relative_path = path.strip_prefix(base_path).unwrap();
                let info = get_video_info(path, relative_path.to_str().unwrap(), 0, None)?;
                items.push(info);
            }
        }
    }

    Ok(items)
}

/// 获取指定路径的视频详细信息（递归）
async fn get_video_details(Path(path): Path<String>) -> Result<Json<VideoInfo>, Response> {
    // 移除可能的前缀斜杠
    let path = path.trim_start_matches('/');
    let full_path = StdPath::new("public").join(path);

    if !full_path.exists() {
        return Err((StatusCode::NOT_FOUND, "Path not found").into_response());
    }

    let info = if full_path.is_dir() {
        // 如果是目录，递归获取子文件
        let children = scan_directory_recursive(StdPath::new("public"), &full_path, 0)?;
        get_video_info(&full_path, path, 2, Some(children))?
    } else {
        // 如果是文件，直接获取信息
        get_video_info(&full_path, path, 2, None)?
    };

    Ok(Json(info))
}

/// 获取单个视频或目录的信息
fn get_video_info(
    path: &StdPath,
    relative_path: &str,
    child_depth: usize,
    children: Option<Vec<VideoInfo>>,
) -> Result<VideoInfo, Response> {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();

    let public_path = StdPath::new("public");
    let full_relative_path = public_path.join(relative_path);
    let web_path = format!("/public/{}", full_relative_path.display());

    // 获取缩略图路径 - 修复这里：确保路径正确
    let thumbnail_path = get_correct_thumbnail_path(relative_path);

    if path.is_dir() {
        // 检查是否是包含 m3u8 的目录
        let has_m3u8 = has_m3u8_file(path);
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
            children,
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

        // 设置缩略图路径（如果存在）- 修复这里：确保返回正确的缩略图路径
        let thumbnail = if thumbnail_path.exists() {
            // 将缩略图路径转换为URL路径
            let thumbnail_relative = thumbnail_path
                .strip_prefix(StdPath::new("thumbnails"))
                .unwrap();
            Some(format!("/thumbnails/{}", thumbnail_relative.display()))
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

/// 获取正确的缩略图路径 - 修复版本
fn get_correct_thumbnail_path(relative_path: &str) -> PathBuf {
    let thumbnails_path = StdPath::new("thumbnails");
    // 保持相同的相对路径结构，但改变扩展名为.jpg
    thumbnails_path.join(relative_path).with_extension("jpg")
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
            || extension.eq_ignore_ascii_case("srt")
            || extension.eq_ignore_ascii_case("jpg")
            || extension.eq_ignore_ascii_case("png")
            || extension.eq_ignore_ascii_case("gif");
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
