use rayon::prelude::*;
use std::{
    collections::{HashMap, HashSet},
    path::{Path, PathBuf},
    time::SystemTime,
};

use chrono::{DateTime, FixedOffset};
use log::info;
use std::fs::File;
use std::io::BufReader;
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
            || extension.eq_ignore_ascii_case("vtt")
            || extension.eq_ignore_ascii_case("srt")
            || extension.eq_ignore_ascii_case("jpg")
            || extension.eq_ignore_ascii_case("png")
            || extension.eq_ignore_ascii_case("gif");
    }
    false
}
/// 获取多个目录下面的文件数据
pub fn get_files(root_paths: &[String]) -> Vec<(String, String, String, PathBuf)> {
    let mut files: Vec<(String, String, String, PathBuf)> = Vec::new();

    for root_path_str in root_paths {
        let root_path = Path::new(root_path_str);

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
    }
    files
}

// 新增函数：获取没有缩略图的文件路径,以及文件名
pub fn get_files_without_thumbnails(
    source_dir: &Path,
    thumbnails_path: &Path,
) -> Vec<(String, PathBuf)> {
    // 获取文件元数据
    let get_metadata = |path: &Path| -> HashMap<String, (PathBuf, SystemTime)> {
        std::fs::read_dir(path)
            .unwrap()
            .filter_map(|entry| {
                let entry = entry.ok()?;
                let path = entry.path();
                let name = path.file_stem()?.to_string_lossy().into_owned();
                let metadata = entry.metadata().ok()?;
                let modified = metadata.modified().ok()?;
                Some((name, (path, modified)))
            })
            .collect()
    };

    // 并行获取源目录和缩略图目录的文件元数据
    let (source_files, thumbnail_files) = rayon::join(
        || get_metadata(source_dir),
        || get_metadata(thumbnails_path),
    );

    // 筛选出需要更新的文件
    source_files
        .into_par_iter()
        .filter(
            |(name, (_source_path, source_modified))| match thumbnail_files.get(name) {
                Some((_, thumbnail_modified)) => source_modified > thumbnail_modified,
                None => true,
            },
        )
        .map(|(name, (path, _))| (name, path))
        .collect()
}

#[derive(Debug)]
pub struct VideoInfo {
    pub duration: String, // 秒
    pub width: u16,
    pub height: u16,
}

pub fn get_video_info(file_path: &str) -> Result<VideoInfo, Box<dyn std::error::Error>> {
    // 打开文件并获取大小
    let file = File::open(file_path)?;
    let size = file.metadata()?.len();
    let reader = BufReader::new(file);

    // 快速解析MP4头部
    let mp4 = mp4::Mp4Reader::read_header(reader, size)?;

    // 获取时长（转换为秒）
    let duration = mp4.duration().as_secs_f64();
    let duration = format_duration(duration);
    // 查找视频轨道
    let mut video_info = VideoInfo {
        duration,
        width: 0,
        height: 0,
    };

    for track in mp4.tracks().values() {
        if let mp4::TrackType::Video = track.track_type()? {
            video_info.width = track.width();
            video_info.height = track.height();
            break; // 只取第一个视频轨道
        }
    }

    Ok(video_info)
}
fn format_duration(seconds: f64) -> String {
    let total_seconds = seconds.round() as u32;
    let hours = total_seconds / 3600;
    let minutes = (total_seconds % 3600) / 60;
    let seconds = total_seconds % 60;

    if hours > 0 {
        format!("{:02}:{:02}:{:02}", hours, minutes, seconds)
    } else {
        format!("{:02}:{:02}", minutes, seconds)
    }
}
