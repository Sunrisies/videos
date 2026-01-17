//! FFmpeg 统一服务层
//!
//! 提供统一的 FFmpeg 调用接口，支持：
//! - 视频缩略图生成
//! - 视频元数据提取（时长、分辨率）
//! - M3U8 合并为 MP4
//! - 批量处理优化

use log::{debug, error, warn};
use std::path::Path;
use std::process::Command;

/// FFmpeg 操作结果
#[derive(Debug, Clone)]
pub struct VideoMetadata {
    pub duration: Option<String>,
    pub width: Option<i32>,
    pub height: Option<i32>,
    pub thumbnail_path: Option<String>,
}

/// FFmpeg 服务配置
#[derive(Clone)]
pub struct FFmpegConfig {
    /// 缩略图质量 (1-31, 越小越好)
    pub thumbnail_quality: u8,
    /// 缩略图提取时间点（秒）
    pub thumbnail_seek_time: f32,
    /// 缩略图宽度
    pub thumbnail_width: u32,
}

impl Default for FFmpegConfig {
    fn default() -> Self {
        Self {
            thumbnail_quality: 2,
            thumbnail_seek_time: 1.0,
            thumbnail_width: 320,
        }
    }
}

/// FFmpeg 统一服务
pub struct FFmpegService {
    config: FFmpegConfig,
}

impl FFmpegService {
    /// 创建新的 FFmpeg 服务实例
    pub fn new(config: FFmpegConfig) -> Self {
        Self { config }
    }

    /// 使用默认配置创建服务
    pub fn with_defaults() -> Self {
        Self::new(FFmpegConfig::default())
    }

    /// 一次性获取视频的所有元数据（时长、分辨率）并生成缩略图
    /// 这比分开调用更高效
    pub fn extract_video_info(&self, video_path: &Path, thumbnail_path: &Path) -> VideoMetadata {
        let mut metadata = VideoMetadata {
            duration: None,
            width: None,
            height: None,
            thumbnail_path: None,
        };

        // 1. 使用 ffprobe 获取元数据（时长和分辨率）
        if let Some((duration, width, height)) = self.probe_video_metadata(video_path) {
            metadata.duration = Some(duration);
            metadata.width = Some(width);
            metadata.height = Some(height);
        }

        // 2. 生成缩略图
        if self.generate_thumbnail(video_path, thumbnail_path) {
            metadata.thumbnail_path = Some(thumbnail_path.to_string_lossy().to_string());
        }

        metadata
    }

    /// 使用 ffprobe 一次性获取视频元数据
    fn probe_video_metadata(&self, video_path: &Path) -> Option<(String, i32, i32)> {
        let input = video_path.to_string_lossy().to_string();

        // 使用 JSON 格式输出以便解析
        let output = Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of",
                "csv=p=0:s=,",
                &input,
            ])
            .output()
            .ok()?;

        if !output.status.success() {
            debug!("ffprobe 失败: {:?}", video_path);
            return None;
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let parts: Vec<&str> = stdout.trim().split(',').collect();

        if parts.len() >= 3 {
            let width: i32 = parts[0].parse().ok()?;
            let height: i32 = parts[1].parse().ok()?;
            let duration_secs: f64 = parts
                .get(2)
                .or(parts.get(3))
                .and_then(|s| s.parse().ok())
                .unwrap_or(0.0);

            let duration = Self::format_duration(duration_secs);
            Some((duration, width, height))
        } else {
            None
        }
    }

    /// 生成视频缩略图
    pub fn generate_thumbnail(&self, video_path: &Path, thumbnail_path: &Path) -> bool {
        // 确保父目录存在
        if let Some(parent) = thumbnail_path.parent() {
            if !parent.exists() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    error!("创建缩略图目录失败: {}", e);
                    return false;
                }
            }
        }

        let input = video_path.to_string_lossy().to_string();
        let output = thumbnail_path.to_string_lossy().to_string();
        let seek_time = format!("{:.2}", self.config.thumbnail_seek_time);
        let scale = format!("scale={}:-1", self.config.thumbnail_width);
        let quality = self.config.thumbnail_quality.to_string();

        let result = Command::new("ffmpeg")
            .args([
                "-ss", &seek_time, "-i", &input, "-vframes", "1", "-vf", &scale, "-q:v", &quality,
                "-y", &output,
            ])
            .output();

        match result {
            Ok(_) => {
                if thumbnail_path.exists() {
                    debug!("缩略图生成成功: {:?}", thumbnail_path);
                    true
                } else {
                    warn!("缩略图生成失败: {:?}", video_path);
                    false
                }
            }
            Err(e) => {
                error!("FFmpeg 执行错误: {}", e);
                false
            }
        }
    }

    /// 生成默认占位缩略图
    pub fn generate_placeholder_thumbnail(&self, thumbnail_path: &Path, label: &str) -> bool {
        // 确保父目录存在
        if let Some(parent) = thumbnail_path.parent() {
            if !parent.exists() {
                let _ = std::fs::create_dir_all(parent);
            }
        }

        let svg_content = match label {
            "video" => {
                r##"<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg"><rect width="320" height="180" fill="#4A90E2"/><text x="160" y="90" font-family="Arial" font-size="20" fill="white" text-anchor="middle">VIDEO</text></svg>"##
            }
            "media" => {
                r##"<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg"><rect width="320" height="180" fill="#F5A623"/><text x="160" y="90" font-family="Arial" font-size="20" fill="white" text-anchor="middle">MEDIA</text></svg>"##
            }
            _ => {
                r##"<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg"><rect width="320" height="180" fill="#95A5A6"/><text x="160" y="90" font-family="Arial" font-size="20" fill="white" text-anchor="middle">FILE</text></svg>"##
            }
        };

        let svg_path = thumbnail_path.with_extension("svg");
        if std::fs::write(&svg_path, svg_content).is_err() {
            return false;
        }

        let input = svg_path.to_string_lossy().to_string();
        let output = thumbnail_path.to_string_lossy().to_string();

        let result = Command::new("ffmpeg")
            .args(["-i", &input, "-y", &output])
            .output();

        let _ = std::fs::remove_file(&svg_path);

        match result {
            Ok(_) => thumbnail_path.exists(),
            Err(_) => false,
        }
    }

    /// 仅获取视频时长
    pub fn get_duration(&self, video_path: &Path) -> Option<String> {
        let input = video_path.to_string_lossy().to_string();

        let output = Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                &input,
            ])
            .output()
            .ok()?;

        let duration_str = String::from_utf8_lossy(&output.stdout);
        let duration_secs: f64 = duration_str.trim().parse().ok()?;
        Some(Self::format_duration(duration_secs))
    }

    /// 仅获取视频分辨率
    pub fn get_dimensions(&self, video_path: &Path) -> Option<(i32, i32)> {
        let input = video_path.to_string_lossy().to_string();

        let output = Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                &input,
            ])
            .output()
            .ok()?;

        let dimensions_str = String::from_utf8_lossy(&output.stdout);
        let parts: Vec<&str> = dimensions_str.trim().split('x').collect();

        if parts.len() == 2 {
            let width: i32 = parts[0].parse().ok()?;
            let height: i32 = parts[1].parse().ok()?;
            Some((width, height))
        } else {
            None
        }
    }

    /// 格式化时长为 HH:MM:SS
    fn format_duration(seconds: f64) -> String {
        let total_seconds = seconds as u64;
        let hours = total_seconds / 3600;
        let minutes = (total_seconds % 3600) / 60;
        let secs = total_seconds % 60;
        format!("{:02}:{:02}:{:02}", hours, minutes, secs)
    }
}

/// 全局 FFmpeg 服务实例（惰性初始化）
static FFMPEG_SERVICE: std::sync::OnceLock<FFmpegService> = std::sync::OnceLock::new();

/// 获取全局 FFmpeg 服务实例
pub fn get_ffmpeg_service() -> &'static FFmpegService {
    FFMPEG_SERVICE.get_or_init(|| FFmpegService::with_defaults())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_duration() {
        assert_eq!(FFmpegService::format_duration(0.0), "00:00:00");
        assert_eq!(FFmpegService::format_duration(61.0), "00:01:01");
        assert_eq!(FFmpegService::format_duration(3661.0), "01:01:01");
    }
}
