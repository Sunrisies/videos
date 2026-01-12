use log::{error, info, warn};
use rayon::iter::{IntoParallelRefIterator, ParallelIterator};
use std::path::Path as StdPath;
use std::process::Command;
use std::time::Instant;

use crate::utils::get_files_without_thumbnails;

/// 使用自定义数据源目录初始化缩略图目录
pub fn initialize_thumbnails_with_source(source_dir: &str) {
    // 开始时间
    let start = Instant::now();
    let thumbnails_path = StdPath::new("thumbnails");
    // 创建 thumbnails 目录
    if !thumbnails_path.exists() {
        std::fs::create_dir(thumbnails_path).expect("Failed to create thumbnails directory");
        info!("已创建缩略图目录");
    }

    let source_path = StdPath::new(source_dir);
    let files_without_thumbnails = get_files_without_thumbnails(source_path, thumbnails_path);

    info!("没有缩略图的文件数量: {}", files_without_thumbnails.len());
    // 使用并行迭代器处理文件
    files_without_thumbnails
        .par_iter()
        .for_each(|(name, file)| {
            // 构建缩略图文件名（将原文件名改为.jpg扩展名）
            let thumbnail_filename = format!("{}.jpg", name);

            // 构建完整的缩略图路径（使用thumbnails_path作为基础目录）
            let thumbnail_path = thumbnails_path.join(&thumbnail_filename);

            // 确保缩略图目录存在
            if let Some(parent) = thumbnail_path.parent() {
                if !parent.exists() {
                    // 在多线程环境中创建目录可能需要处理并发问题
                    std::fs::create_dir_all(parent).expect("无法创建缩略图目录");
                }
            }

            // 生成缩略图
            generate_video_thumbnail(file, &thumbnail_path);
        });

    info!("缩略图生成完成，耗时: {:?}", start.elapsed());
}

/// 为视频文件生成缩略图
pub fn generate_video_thumbnail(video_path: &StdPath, thumbnail_path: &StdPath) {
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
                info!("✓ Generated thumbnail for video: {}", video_path.display());
            } else {
                warn!(
                    "✗ Failed to generate thumbnail for video: {}",
                    video_path.display()
                );
            }
        }
        Err(e) => {
            error!("✗ FFmpeg error for {}: {}", video_path.display(), e);
            // 生成默认图标作为备用
            generate_default_thumbnail(thumbnail_path, "video");
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
