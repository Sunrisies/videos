use std::{
    collections::HashSet,
    path::{Path, PathBuf},
};

use chrono::{DateTime, FixedOffset};
use walkdir::WalkDir;

/// 辅助函数：格式化文件大小
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

/// 辅助函数：格式化系统时间
pub fn get_systemtime_created(metadata: &std::fs::Metadata) -> Option<String> {
    use std::time::UNIX_EPOCH;

    metadata.created().ok().and_then(|time| {
        let timestamp = time.duration_since(UNIX_EPOCH).ok()?;
        let nanos = timestamp.as_nanos() as i64;
        let datetime = DateTime::from_timestamp_nanos(nanos);
        let beijing = FixedOffset::east_opt(8 * 3600).unwrap();
        let bj = datetime.with_timezone(&beijing);
        Some(bj.format("%Y-%m-%d %H:%M:%S").to_string())
    })
}

/// 辅助函数：获取创建时间
pub fn get_created_at(path: &Path) -> Option<String> {
    std::fs::metadata(path)
        .ok()
        .and_then(|m| get_systemtime_created(&m))
}

/// 辅助函数：检查路径是否为视频或容器
pub fn is_video_or_container(path: &Path) -> bool {
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
/// 获取当前目录下面的文件数据
pub fn get_files(root_path: &Path) -> Vec<(String, String, String, PathBuf)> {
    let mut files: Vec<(String, String, String, PathBuf)> = Vec::new();
    for entry in WalkDir::new(root_path)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        // 过滤掉当前的目录
        if root_path == path {
            continue;
        }
        if is_video_or_container(path) {
            // 获取不带扩展名的文件名
            let name_without_ext = path
                .file_stem()
                .and_then(|n| n.to_str())
                .unwrap_or("")
                .to_string();
            let size = format_size(path.metadata().unwrap().len());
            let created_at = get_created_at(path).unwrap_or_default();
            files.push((name_without_ext, size, created_at, path.to_path_buf()));
        }
    }
    files
}

// 新增函数：获取没有缩略图的文件路径,以及文件名
pub fn get_files_without_thumbnails(
    source_dir: &Path,
    thumbnails_path: &Path,
) -> Vec<(String, PathBuf)> {
    // 获取源目录和缩略图目录的所有文件
    let source_files = get_files(source_dir);
    let thumbnail_files = get_files(thumbnails_path);

    // 创建缩略图文件名的集合，便于快速查找
    let thumbnail_names: HashSet<String> = thumbnail_files
        .iter()
        .map(|(name, _, _, _)| name.clone())
        .collect();
    // 筛选出没有对应缩略图的源文件
    let files_without_thumbnails = source_files
        .iter()
        .filter(|(name, _, _, _)| !thumbnail_names.contains(name))
        .map(|(name, _, _, path)| (name.clone(), path.clone()))
        .collect();

    files_without_thumbnails
}
