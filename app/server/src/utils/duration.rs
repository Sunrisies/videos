use std::{fs, path::Path, process::Command};

pub fn get_video_duration(video_path: &Path) -> Option<String> {
    let output = Command::new("ffprobe")
        .arg("-v")
        .arg("error")
        .arg("-show_entries")
        .arg("format=duration")
        .arg("-of")
        .arg("default=noprint_wrappers=1:nokey=1")
        .arg(video_path)
        .output()
        .ok()?;

    let duration_str = String::from_utf8_lossy(&output.stdout);
    let duration_secs: f64 = duration_str.trim().parse().ok()?;

    let total_seconds = duration_secs as u64;
    let hours = total_seconds / 3600;
    let minutes = (total_seconds % 3600) / 60;
    let seconds = total_seconds % 60;

    Some(format!("{:02}:{:02}:{:02}", hours, minutes, seconds))
}
pub fn get_m3u8_duration(m3u8_path: &Path) -> Option<String> {
    // 在目录中找到index.m3u8文件
    let index_m3u8 = m3u8_path.join("index.m3u8");

    if !index_m3u8.exists() {
        return None;
    }

    // 读取m3u8文件内容
    let content = fs::read_to_string(&index_m3u8).ok()?;

    // 解析m3u8文件以计算总时长
    let mut total_duration = 0.0;

    for line in content.lines() {
        // 寻找以#EXTINF开头的行：这些行包含持续时间信息
        if line.starts_with("#EXTINF:") {
            // 提取持续时间值
            let duration_part = line.trim_start_matches("#EXTINF:");
            if let Some(comma_pos) = duration_part.find(',') {
                let duration_str = &duration_part[..comma_pos];
                if let Ok(duration) = duration_str.trim().parse::<f64>() {
                    total_duration += duration;
                }
            }
        }
    }

    // 将总时长转换为“时:分:秒”格式
    let hours = (total_duration / 3600.0).floor() as u32;
    let minutes = ((total_duration % 3600.0) / 60.0).floor() as u32;
    let seconds = (total_duration % 60.0).floor() as u32;

    Some(format!("{:02}:{:02}:{:02}", hours, minutes, seconds))
}
