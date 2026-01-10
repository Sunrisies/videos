use std::path::Path;

use crate::services::filesystem::{
    generate_default_thumbnail, generate_image_thumbnail, generate_video_thumbnail,
};
/// 确保缩略图存在，如果不存在则生成
pub fn get_ensure_thumbnail(file_path: &Path) -> Option<String> {
    // 获取缩略图目录
    let thumbnails_path = Path::new("thumbnails");

    // 获取相对路径
    let public_path = Path::new("public");
    let relative_path = match file_path.strip_prefix(public_path) {
        Ok(path) => path,
        Err(_) => return None,
    };

    // 构建缩略图路径
    let thumbnail_path = thumbnails_path.join(relative_path).with_extension("jpg");
    println!("Thumbnail path: {:?}", thumbnail_path);
    // 如果缩略图不存在，则生成
    if !thumbnail_path.exists() {
        // 创建缩略图所在的子目录
        if let Some(parent) = thumbnail_path.parent() {
            if !parent.exists() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    println!(
                        "Failed to create thumbnail directory {}: {}",
                        parent.display(),
                        e
                    );
                    return None;
                }
            }
        }

        // 根据文件类型生成缩略图
        let extension = file_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_lowercase();

        if extension == "mp4" || extension == "avi" || extension == "mkv" || extension == "mov" {
            generate_video_thumbnail(file_path, &thumbnail_path);
        } else if extension == "jpg"
            || extension == "jpeg"
            || extension == "png"
            || extension == "gif"
        {
            generate_image_thumbnail(file_path, &thumbnail_path);
        } else if extension == "m3u8" {
            // 对于 m3u8 文件，尝试从目录中的第一个 ts 片段生成
            if let Some(parent) = file_path.parent() {
                let index_m3u8_path = parent.join("index.m3u8");
                if index_m3u8_path.exists() {
                    if let Ok(content) = std::fs::read_to_string(&index_m3u8_path) {
                        if let Some(first_ts_line) =
                            content.lines().find(|line| line.ends_with(".ts"))
                        {
                            let ts_path = parent.join(first_ts_line.trim());
                            if ts_path.exists() {
                                generate_video_thumbnail(&ts_path, &thumbnail_path);
                            } else {
                                generate_default_thumbnail(&thumbnail_path, "media");
                            }
                        } else {
                            generate_default_thumbnail(&thumbnail_path, "media");
                        }
                    } else {
                        generate_default_thumbnail(&thumbnail_path, "media");
                    }
                } else {
                    generate_default_thumbnail(&thumbnail_path, "media");
                }
            } else {
                generate_default_thumbnail(&thumbnail_path, "media");
            }
        } else if extension == "ts" || extension == "vtt" || extension == "srt" {
            generate_default_thumbnail(&thumbnail_path, "media");
        } else {
            generate_default_thumbnail(&thumbnail_path, "file");
        }
    }

    // 返回缩略图路径（如果生成成功）
    if thumbnail_path.exists() {
        Some(thumbnail_path.to_string_lossy().to_string())
    } else {
        None
    }
}
