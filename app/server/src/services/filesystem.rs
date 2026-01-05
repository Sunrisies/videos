use std::path::{Path as StdPath, PathBuf};
use std::process::Command;
use std::time::UNIX_EPOCH;
use walkdir::WalkDir;

/// 初始化缩略图目录
pub fn initialize_thumbnails() {
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
pub fn generate_thumbnails_for_directory(public_path: &StdPath, thumbnails_path: &StdPath) {
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
pub fn generate_video_thumbnail(video_path: &StdPath, thumbnail_path: &StdPath) {
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
pub fn generate_image_thumbnail(image_path: &StdPath, thumbnail_path: &StdPath) {
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
pub fn generate_default_thumbnail(thumbnail_path: &StdPath, file_type: &str) {
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

/// 扫描第一层目录和文件
pub fn scan_directory_first_level(
    base_path: &StdPath,
) -> Result<Vec<(PathBuf, PathBuf)>, std::io::Error> {
    let mut items = Vec::new();

    for entry in WalkDir::new(base_path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();

        // 跳过根目录本身
        if path == base_path {
            continue;
        }

        if path.is_dir() {
            // 目录 - 检查是否包含视频文件
            if is_video_or_container(path) {
                let relative_path = path.strip_prefix(base_path).unwrap();
                items.push((path.to_path_buf(), relative_path.to_path_buf()));
            }
        } else if path.is_file() {
            // 文件 - 检查是否是视频相关文件
            if is_video_or_container(path) {
                let relative_path = path.strip_prefix(base_path).unwrap();
                items.push((path.to_path_buf(), relative_path.to_path_buf()));
            }
        }
    }

    Ok(items)
}

/// 扫描目录的子文件（用于详情页）
pub fn scan_directory_children(
    parent_path: &StdPath,
) -> Result<Vec<(PathBuf, PathBuf)>, std::io::Error> {
    let mut children = Vec::new();

    for entry in WalkDir::new(parent_path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();

        // 跳过父目录本身
        if path == parent_path {
            continue;
        }

        if path.is_file() {
            // 只添加文件，不递归目录
            if is_video_or_container(path) {
                let relative_path = path.strip_prefix(StdPath::new("public")).unwrap();
                children.push((path.to_path_buf(), relative_path.to_path_buf()));
            }
        }
    }

    Ok(children)
}

/// 检查路径是否是视频文件或视频容器（目录）
pub fn is_video_or_container(path: &StdPath) -> bool {
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
pub fn has_m3u8_file(path: &StdPath) -> bool {
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
pub fn has_video_file(path: &StdPath) -> bool {
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
pub fn get_created_at(path: &StdPath) -> Option<String> {
    std::fs::metadata(path)
        .ok()
        .and_then(|m| get_systemtime_created(&m))
}

/// 从 SystemTime 获取可读的创建时间字符串
pub fn get_systemtime_created(metadata: &std::fs::Metadata) -> Option<String> {
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
pub fn format_size(bytes: u64) -> String {
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

/// 获取正确的缩略图路径
pub fn get_correct_thumbnail_path(relative_path: &str) -> PathBuf {
    let thumbnails_path = StdPath::new("thumbnails");
    // 保持相同的相对路径结构，但改变扩展名为.jpg
    thumbnails_path.join(relative_path).with_extension("jpg")
}

/// 获取Web路径（修复路径格式）
pub fn get_web_path(relative_path: &str) -> String {
    let public_path = StdPath::new("public");
    let full_relative_path = public_path.join(relative_path);
    // 修复路径：使用正斜杠，并移除重复的public
    format!(
        "/public/{}",
        full_relative_path
            .display()
            .to_string()
            .replace("\\", "/")
            .replace("public/", "")
    )
}

/// 获取缩略图的Web路径
pub fn get_thumbnail_web_path(relative_path: &str) -> Option<String> {
    let thumbnail_path = get_correct_thumbnail_path(relative_path);
    if thumbnail_path.exists() {
        let thumbnail_relative = thumbnail_path
            .strip_prefix(StdPath::new("thumbnails"))
            .unwrap();
        let thumbnail_str = thumbnail_relative.display().to_string().replace("\\", "/");
        Some(format!("/thumbnails/{}", thumbnail_str))
    } else {
        None
    }
}
