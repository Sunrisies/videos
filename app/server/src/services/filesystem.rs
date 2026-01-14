//! 文件系统服务
//!
//! 提供文件系统相关的操作，包括：
//! - 缩略图目录初始化
//! - 批量缩略图生成

use log::{debug, info};
use rayon::iter::{IntoParallelRefIterator, ParallelIterator};
use std::path::Path as StdPath;
use std::time::Instant;

use crate::services::ffmpeg::get_ffmpeg_service;
use crate::utils::get_files_without_thumbnails;

/// 使用自定义数据源目录初始化缩略图目录
pub fn initialize_thumbnails_with_source(source_dir: &str) {
    let start = Instant::now();
    let thumbnails_path = StdPath::new("thumbnails");

    // 创建 thumbnails 目录
    if !thumbnails_path.exists() {
        std::fs::create_dir(thumbnails_path).expect("Failed to create thumbnails directory");
        info!("已创建缩略图目录");
    }

    let source_path = StdPath::new(source_dir);
    let files_without_thumbnails = get_files_without_thumbnails(source_path, thumbnails_path);

    if files_without_thumbnails.is_empty() {
        debug!("所有文件都已有缩略图");
        return;
    }

    info!("需要生成缩略图的文件数量: {}", files_without_thumbnails.len());

    // 使用新的 FFmpeg 服务并行生成缩略图
    let ffmpeg = get_ffmpeg_service();

    files_without_thumbnails
        .par_iter()
        .for_each(|(name, file)| {
            let thumbnail_filename = format!("{}.jpg", name);
            let thumbnail_path = thumbnails_path.join(&thumbnail_filename);

            // 确保缩略图目录存在
            if let Some(parent) = thumbnail_path.parent() {
                if !parent.exists() {
                    let _ = std::fs::create_dir_all(parent);
                }
            }

            // 使用 FFmpeg 服务生成缩略图
            let extension = file
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_lowercase();

            if extension == "mp4" || extension == "avi" || extension == "mkv" || extension == "mov" {
                ffmpeg.generate_thumbnail(file, &thumbnail_path);
            } else {
                ffmpeg.generate_placeholder_thumbnail(&thumbnail_path, "media");
            }
        });

    info!("缩略图初始化完成，耗时: {:?}", start.elapsed());
}

/// 为视频文件生成缩略图（兼容旧接口）
pub fn generate_video_thumbnail(video_path: &StdPath, thumbnail_path: &StdPath) {
    let ffmpeg = get_ffmpeg_service();
    ffmpeg.generate_thumbnail(video_path, thumbnail_path);
}

/// 生成默认缩略图（兼容旧接口）
pub fn generate_default_thumbnail(thumbnail_path: &StdPath, file_type: &str) {
    let ffmpeg = get_ffmpeg_service();
    ffmpeg.generate_placeholder_thumbnail(thumbnail_path, file_type);
}
