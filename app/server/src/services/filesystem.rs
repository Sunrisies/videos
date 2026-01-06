use std::path::Path as StdPath;
use std::process::Command;
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
