use crate::services::db::connection::VideoDbManager;
use crate::services::db::schema::{queries, video_types};
use crate::utils::{get_m3u8_duration, get_thumbnail_path, get_video_duration, has_m3u8_file};
use chrono::{DateTime, FixedOffset};
use rusqlite::Result;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// 目录同步器
///
/// 负责扫描文件系统并同步数据到数据库
pub struct DirectorySync<'a> {
    db_manager: &'a VideoDbManager,
}

impl<'a> DirectorySync<'a> {
    /// 创建新的目录同步器
    pub fn new(db_manager: &'a VideoDbManager) -> Self {
        Self { db_manager }
    }

    /// 从目录初始化数据库
    pub fn initialize_from_directory(&self, root_path: &str, force: bool) -> Result<()> {
        println!("从目录初始化数据库: {}", root_path);

        // 检查数据库是否已初始化
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL_COUNT)?;
        let count: i64 = stmt.query_row([], |row| row.get(0))?;

        if count > 0 && !force {
            println!("数据库已包含 {} 条记录，跳过初始化。", count);
            return Ok(());
        }

        // 如果 force 为 true 或数据库为空，则清除并重新初始化
        if force {
            println!("请求强制重新初始化，清除现有数据...");
            self.db_manager.conn.execute("DELETE FROM videos", [])?;
        }

        // 扫描并填充
        self.sync_directory(root_path)?;

        println!("数据库初始化完成");
        Ok(())
    }

    /// 扫描目录并更新数据库（添加/更新）
    /// 通过比较数据库条目与文件系统检测删除
    pub fn sync_directory(&self, root_path: &str) -> Result<()> {
        let root = PathBuf::from(root_path);
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            .to_string();

        // 将所有现有条目标记为可能已删除
        self.db_manager
            .conn
            .execute(queries::UPDATE_MARK_DELETED, &[&format!("{}%", root_path)])?;

        // 扫描并插入/更新条目
        self.scan_and_insert(&root, &current_time)?;

        // 删除仍标记为已删除的条目（扫描期间未找到）
        let deleted_count = self
            .db_manager
            .conn
            .execute(queries::DELETE_MARKED, &[&format!("{}%", root_path)])?;

        if deleted_count > 0 {
            println!("从数据库中删除了 {} 个已删除的条目", deleted_count);
        }

        Ok(())
    }

    /// 扫描并插入条目
    fn scan_and_insert(&self, path: &Path, current_time: &str) -> Result<()> {
        if path.is_dir() {
            // 检查此目录是否包含 m3u8 文件
            let has_m3u8 = has_m3u8_file(path);

            if has_m3u8 {
                // 对于 m3u8 目录，存储目录但不存储单独的 m3u8/ts 文件
                let parent_path = path
                    .parent()
                    .map(|p| p.to_string_lossy().to_string())
                    .unwrap_or_default();

                let name = path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("")
                    .to_string();

                let created_at = self.get_created_at(path);

                // 从 m3u8 文件获取时长
                let duration = get_m3u8_duration(path);
                println!(
                    "时长: {:?}------父路径: {:?}----名称: {:?}",
                    duration, parent_path, name
                );
                // 插入或更新目录为 hls_directory
                self.db_manager.conn.execute(
                    queries::INSERT_OR_REPLACE,
                    &[
                        &name,
                        &path.to_string_lossy().to_string(),
                        video_types::HLS_DIRECTORY,
                        &parent_path,
                        &created_at.as_deref().unwrap_or(""),
                        current_time,
                        &duration.as_deref().unwrap_or(""),
                    ],
                )?;

                // 不要递归扫描 m3u8 目录 - 我们不存储单独的文件
                return Ok(());
            }

            // 对于非 m3u8 目录，正常扫描
            for entry in WalkDir::new(path)
                .max_depth(1)
                .into_iter()
                .filter_map(|e| e.ok())
            {
                let entry_path = entry.path();

                // 跳过根目录本身
                if entry_path == path {
                    continue;
                }

                if entry_path.is_dir() {
                    println!("路径：{},是m3u8的目录", entry_path.to_string_lossy());
                    // 对于目录，我们需要检查它们是否包含视频内容
                    if self.is_video_or_container(entry_path) {
                        let parent_path = entry_path
                            .parent()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default();

                        let name = entry_path
                            .file_name()
                            .and_then(|n| n.to_str())
                            .unwrap_or("")
                            .to_string();
                        // 读取当前目录下面的 m3u8 文件中的数据
                        let m3u8_file_path = entry_path.join("*.m3u8");
                        println!("m3u8_file_path: {:?}", m3u8_file_path);
                        println!(
                            "路径：{},是m3u8的目录,父目录：{}",
                            entry_path.to_string_lossy(),
                            parent_path
                        );
                        let r#type = if has_m3u8_file(entry_path) {
                            video_types::HLS_DIRECTORY
                        } else {
                            video_types::DIRECTORY
                        };
                        let duration = get_m3u8_duration(entry_path);
                        let created_at = self.get_created_at(entry_path);
                        let jpg_path_str = format!("{}\\index.jpg", entry_path.display());
                        println!("缩略图路径: {}", jpg_path_str); // 调试输出
                        // 插入或更新
                        self.db_manager.conn.execute(
                            queries::INSERT_OR_REPLACE_WITH_THUMBNAIL,
                            &[
                                &name,
                                &entry_path.to_string_lossy().to_string(),
                                r#type,
                                &parent_path,
                                &created_at.as_deref().unwrap_or(""),
                                current_time,
                                &jpg_path_str.to_string(),
                                duration.as_deref().unwrap_or(""),
                            ],
                        )?;
                    }
                } else if entry_path.is_file() {
                    // 检查是否为视频相关文件
                    if self.is_video_or_container(entry_path) {
                        let parent_path = entry_path
                            .parent()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default();

                        let name = entry_path
                            .file_name()
                            .and_then(|n| n.to_str())
                            .unwrap_or("")
                            .to_string();

                        let extension = entry_path
                            .extension()
                            .and_then(|e| e.to_str())
                            .unwrap_or("")
                            .to_lowercase();

                        let r#type = if extension == "mp4" {
                            video_types::MP4
                        } else if extension == "m3u8" {
                            video_types::M3U8
                        } else if extension == "ts" {
                            video_types::TS
                        } else if extension == "vtt" || extension == "srt" {
                            video_types::SUBTITLE
                        } else if extension == "jpg" || extension == "png" || extension == "gif" {
                            video_types::IMAGE
                        } else {
                            video_types::UNKNOWN
                        };
                        // 获取文件元数据
                        let metadata = std::fs::metadata(entry_path).ok();
                        let size = metadata.as_ref().map(|m| self.format_size(m.len()));
                        let created_at = metadata.and_then(|m| self.get_systemtime_created(&m));

                        // 获取缩略图路径
                        let thumbnail = get_thumbnail_path(entry_path);

                        // 根据类型获取视频时长
                        let duration = if r#type == video_types::MP4 {
                            get_video_duration(entry_path)
                        } else {
                            None
                        };
                        // 如果是字幕文件，设置 subtitle 字段
                        let subtitle = if r#type == video_types::SUBTITLE {
                            Some(entry_path.to_string_lossy().to_string())
                        } else {
                            None
                        };
                        // 插入或更新
                        self.db_manager.conn.execute(
                            queries::INSERT_OR_REPLACE_FULL,
                            &[
                                &name,
                                &entry_path.to_string_lossy().to_string(),
                                r#type,
                                &parent_path,
                                &thumbnail.as_deref().unwrap_or(""),
                                &size.as_deref().unwrap_or(""),
                                &created_at.as_deref().unwrap_or(""),
                                &subtitle.as_deref().unwrap_or(""),
                                current_time,
                                &duration.as_deref().unwrap_or(""),
                            ],
                        )?;
                    }
                }
            }
        }
        Ok(())
    }

    /// 辅助函数：检查路径是否为视频或容器
    fn is_video_or_container(&self, path: &Path) -> bool {
        if path.is_dir() {
            return has_m3u8_file(path) || self.has_video_file(path);
        }
        if path.is_file() {
            let extension = path.extension().and_then(|e| e.to_str()).unwrap_or("");

            // 如果是 ts 文件，检查同一目录下是否有 m3u8 文件
            if extension.eq_ignore_ascii_case("ts") {
                if let Some(parent) = path.parent() {
                    if has_m3u8_file(parent) {
                        return false; // 当 m3u8 存在时跳过 ts 文件
                    }
                }
            }

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

    /// 辅助函数：检查目录是否有视频文件
    fn has_video_file(&self, path: &Path) -> bool {
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

    /// 辅助函数：获取创建时间
    fn get_created_at(&self, path: &Path) -> Option<String> {
        std::fs::metadata(path)
            .ok()
            .and_then(|m| self.get_systemtime_created(&m))
    }

    /// 辅助函数：格式化系统时间
    fn get_systemtime_created(&self, metadata: &std::fs::Metadata) -> Option<String> {
        use std::time::UNIX_EPOCH;
        println!("metadata: {:?}", metadata);

        metadata.created().ok().and_then(|time| {
            let timestamp = time.duration_since(UNIX_EPOCH).ok()?;
            let nanos = timestamp.as_nanos() as i64;
            let datetime = DateTime::from_timestamp_nanos(nanos);
            let beijing = FixedOffset::east_opt(8 * 3600).unwrap();
            let bj = datetime.with_timezone(&beijing);
            Some(bj.format("%Y-%m-%d %H:%M:%S").to_string())
        })
    }

    /// 辅助函数：格式化文件大小
    fn format_size(&self, bytes: u64) -> String {
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
}
