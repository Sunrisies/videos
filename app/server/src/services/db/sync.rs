//! 目录同步器
//!
//! 负责扫描文件系统并同步数据到数据库，支持：
//! - 并行文件处理
//! - 增量扫描
//! - 双向同步

use crate::services::db::connection::VideoDbManager;
use crate::services::db::schema::{queries, video_types};
use crate::services::ffmpeg::get_ffmpeg_service;
use crate::DiskMapping;
use std::time::Instant;

use crate::utils::{format_size, get_systemtime_created, get_video_info, is_video_or_container};
use log::{debug, info, warn};
use rayon::prelude::*;
use rusqlite::Result;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex as StdMutex};
use walkdir::WalkDir;

/// 目录同步器
/// 负责扫描文件系统并同步数据到数据库，实现双向同步
pub struct DirectorySync<'a> {
    db_manager: &'a VideoDbManager,
}

/// 文件信息结构体，用于比较文件和数据库记录
#[derive(Debug, Clone)]
pub struct FileInfo {
    pub name: String,
    pub path: String,
    pub created_at: String,
    pub file_type: String,
    pub parent_path: String,
    pub thumbnail: Option<String>,
    pub size: Option<String>,
    pub subtitle: Option<String>,
    pub duration: Option<String>,
    pub width: Option<i32>,
    pub height: Option<i32>,
}

/// 待处理的文件条目
#[derive(Debug, Clone)]
struct PendingEntry {
    path: PathBuf,
}

impl<'a> DirectorySync<'a> {
    /// 创建新的目录同步器
    pub fn new(db_manager: &'a VideoDbManager) -> Self {
        Self { db_manager }
    }
    /// 从多个目录初始化数据库（双向同步）
    pub fn initialize_from_directory_with_progress(
        &self,
        mappings: &Vec<DiskMapping>,
        force: bool,
    ) -> Result<()> {
        // for mapping in mappings {
        let start_time = Instant::now();

        info!("正在初始化同步...");
        // 检查数据库是否已初始化
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL_COUNT)?;
        let count: i64 = stmt.query_row([], |row| row.get(0))?;

        if count > 0 && !force {
            info!("数据库已包含 {} 条记录，执行增量同步", count);

            self.bidirectional_sync_with_progress(mappings)?;
            info!("同步完成，耗时: {}ms", start_time.elapsed().as_millis());
            return Ok(());
        }
        // 如果 force 为 true 或数据库为空，则清除并重新初始化
        if force {
            info!("强制重新初始化，清除现有数据");

            self.db_manager.conn.execute("DELETE FROM videos", [])?;
        }

        // 执行完整的双向同步
        self.bidirectional_sync_with_progress(mappings)?;

        info!("同步完成，耗时: {}ms", start_time.elapsed().as_millis());

        Ok(())
    }

    /// 双向同步：文件系统 -> 数据库 + 数据库 -> 文件系统
    fn bidirectional_sync_with_progress(&self, mappings: &Vec<DiskMapping>) -> Result<()> {
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            .to_string();

        // 1. 获取数据库中所有记录
        let db_records = self.get_all_db_records()?;
        info!("数据库中记录数: {}", db_records.len());

        // 2. 并行扫描所有文件系统目录
        let mut all_fs_files = HashMap::new();
        let mut all_scan_errors = Vec::new();

        for (i, mapping) in mappings.iter().enumerate() {
            let physical_path = Path::new(&mapping.physical_path);
            let route_path = &mapping.route_path;

            let (fs_files, scan_errors) =
                self.scan_filesystem_with_progress(&mapping.physical_path, route_path);
            all_fs_files.extend(fs_files);
            all_scan_errors.extend(scan_errors);
        }

        let mut new_count = 0;
        let mut changed_count = 0;
        let mut skipped_count = 0;

        // 使用进度计数器
        let processed_counter = Arc::new(StdMutex::new(0));

        // 分批处理以避免频繁锁竞争
        let batch_size = 100;
        let entries: Vec<_> = all_fs_files.iter().collect();

        for batch in entries.chunks(batch_size) {
            info!("共 {:?} 批", entries.len());
            // 处理当前批次
            for (path, file_info) in batch {
                match db_records.get(*path) {
                    None => {
                        self.insert_new_record(file_info, &current_time)?;
                        new_count += 1;
                        debug!("新增: {}", file_info.name);
                    }
                    Some(db_record) => {
                        if self.is_record_changed(file_info, db_record) {
                            self.hard_delete_record(path)?;
                            self.insert_new_record(file_info, &current_time)?;
                            changed_count += 1;
                            debug!("更新: {}", file_info.name);
                        } else {
                            skipped_count += 1;
                        }
                    }
                }
            }

            // 更新进度
            let mut processed_guard = processed_counter.lock().unwrap();
            *processed_guard += batch.len();
        }

        // 4. 处理删除的文件
        let mut deleted_count = 0;
        for (i, (path, db_record)) in db_records.iter().enumerate() {
            if !all_fs_files.contains_key(path) {
                self.hard_delete_record(path)?;
                deleted_count += 1;
                debug!("删除: {}", db_record.name);
            }

            // 每处理100条报告一次进度
            if i % 100 == 0 {}
        }

        // 输出统计信息
        if new_count > 0 || changed_count > 0 || deleted_count > 0 {
            info!(
                "同步完成: 新增 {}, 更新 {}, 删除 {}, 跳过 {}",
                new_count, changed_count, deleted_count, skipped_count
            );
        } else {
            debug!("无变化，跳过 {} 个文件", skipped_count);
        }

        if !all_scan_errors.is_empty() {
            warn!("扫描过程中有 {} 个错误", all_scan_errors.len());
        }

        Ok(())
    }

    /// 获取数据库中所有记录
    fn get_all_db_records(&self) -> Result<HashMap<String, FileInfo>> {
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL_FULL)?;
        let mut records = HashMap::new();

        let mut rows = stmt.query([])?;
        while let Some(row) = rows.next()? {
            let record = FileInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                file_type: row.get(2)?,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
                parent_path: row.get(11)?,
                width: row.get(12)?,
                height: row.get(13)?,
            };
            records.insert(record.path.clone(), record);
        }

        Ok(records)
    }
    /// 带进度报告的扫描文件系统
    fn scan_filesystem_with_progress(
        &self,
        root_path: &str,
        route_path: &str,
    ) -> (HashMap<String, FileInfo>, Vec<String>) {
        let root = PathBuf::from(root_path);

        // 检查根目录是否存在
        if !root.exists() {
            return (HashMap::new(), vec![format!("根目录不存在: {}", root_path)]);
        }

        // 第一步：收集所有待处理的文件条目
        let mut pending_entries: Vec<PendingEntry> = Vec::new();
        let mut collect_errors: Vec<String> = Vec::new();

        for entry in WalkDir::new(&root).max_depth(1).into_iter() {
            let entry = match entry {
                Ok(e) => e,
                Err(e) => {
                    collect_errors.push(format!("无法访问条目: {}", e));
                    continue;
                }
            };

            let path = entry.path();
            // 跳过根目录本身
            if path == root {
                continue;
            }

            // 检查是否为视频相关文件或目录
            if !is_video_or_container(path) {
                continue;
            }

            pending_entries.push(PendingEntry {
                path: path.to_path_buf(),
            });
        }

        debug!("收集到 {} 个待处理条目", pending_entries.len());

        // 第二步：并行处理所有条目
        let files = StdMutex::new(HashMap::new());
        let errors = StdMutex::new(collect_errors);
        let root_ref = &root;

        // 进度跟踪
        let total = pending_entries.len();
        let processed_counter = Arc::new(StdMutex::new(0));

        pending_entries.par_iter().for_each(|entry| {
            let result = Self::process_file_static(&entry.path, root_ref, route_path);
            match result {
                Ok(Some(file_info)) => {
                    let mut files_guard = files.lock().unwrap();
                    files_guard.insert(file_info.path.clone(), file_info);
                }
                Ok(None) => {
                    // 跳过不需要处理的条目
                }
                Err(e) => {
                    let mut errors_guard = errors.lock().unwrap();
                    errors_guard.push(e);
                }
            }

            // 更新进度（每10个文件更新一次）
            let mut processed_guard = processed_counter.lock().unwrap();
            *processed_guard += 1;

            if *processed_guard % 10 == 0 || *processed_guard == total {
                info!("已处理 {} / {}", *processed_guard, total);
            }
        });
        let files = files.into_inner().unwrap();
        let errors = errors.into_inner().unwrap();

        (files, errors)
    }

    /// 静态方法：处理普通文件（用于并行处理）
    fn process_file_static(
        path: &Path,
        _root: &Path,
        route_path: &str,
    ) -> std::result::Result<Option<FileInfo>, String> {
        if !path.is_file() {
            return Ok(None);
        }

        let extension = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_lowercase();

        // 确定文件类型
        let file_type = match extension.as_str() {
            "mp4" => video_types::MP4,
            "vtt" | "srt" => video_types::SUBTITLE,
            "jpg" | "png" | "gif" => video_types::IMAGE,
            _ => video_types::UNKNOWN,
        };

        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        // 获取文件元数据
        let metadata = std::fs::metadata(path).ok();
        let size = metadata.as_ref().map(|m| format_size(m.len()));
        let created_at = metadata
            .as_ref()
            .and_then(|m| get_systemtime_created(m))
            .unwrap_or_default();

        // 获取缩略图路径
        let thumb_path = Self::get_thumbnail_path(path);
        // 使用统一的 FFmpeg 服务获取视频信息
        let (thumbnail, duration, width, height) = if file_type == video_types::MP4 {
            let ffmpeg = get_ffmpeg_service();
            // 检查缩略图是否已存在
            if thumb_path.exists() {
                let video_info = get_video_info(&path.to_string_lossy().to_string());
                match video_info {
                    Ok(info) => (
                        Some(thumb_path.to_string_lossy().to_string()),
                        Some(info.duration.to_string()),
                        Some(info.width as i32),
                        Some(info.height as i32),
                    ),
                    Err(_) => (
                        Some(thumb_path.to_string_lossy().to_string()),
                        None,
                        None,
                        None,
                    ),
                }
            } else {
                info!("---------------------");
                let metadata = ffmpeg.extract_video_info(path, &thumb_path);
                (
                    metadata.thumbnail_path,
                    metadata.duration,
                    metadata.width,
                    metadata.height,
                )
            }
        } else {
            (Self::ensure_thumbnail_static(path), None, None, None)
        };

        // 获取字幕路径
        let subtitle = if file_type == video_types::SUBTITLE {
            Some(path.to_string_lossy().to_string())
        } else {
            None
        };

        Ok(Some(FileInfo {
            name,
            path: path.to_string_lossy().to_string(),
            created_at,
            file_type: file_type.to_string(),
            parent_path: route_path.to_string(),
            thumbnail,
            size,
            subtitle,
            duration,
            width,
            height,
        }))
    }

    /// 获取缩略图路径
    fn get_thumbnail_path(file_path: &Path) -> PathBuf {
        let thumbnails_dir = Path::new("thumbnails");

        // 方法1: 找到 "public" 在路径中的位置，取后面的部分
        let relative_path: PathBuf = file_path
            .components() // 分解路径组件
            .skip_while(|c| c.as_os_str() != "public") // 跳过直到 "public"
            .skip(1) // 跳过 "public" 本身
            .collect(); // 收集剩余部分

        // 如果 relative_path 为空（没找到 public），使用文件名
        let final_path = if relative_path.as_os_str().is_empty() {
            file_path.file_name().map(Path::new).unwrap_or(file_path)
        } else {
            &relative_path
        };

        thumbnails_dir.join(final_path).with_extension("jpg")
    }

    /// 确保缩略图存在（静态方法）
    fn ensure_thumbnail_static(file_path: &Path) -> Option<String> {
        let thumbnail_path = Self::get_thumbnail_path(file_path);

        if thumbnail_path.exists() {
            return Some(thumbnail_path.to_string_lossy().to_string());
        }

        // 确保父目录存在
        if let Some(parent) = thumbnail_path.parent() {
            if !parent.exists() {
                let _ = std::fs::create_dir_all(parent);
            }
        }

        let ffmpeg = get_ffmpeg_service();
        let extension = file_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_lowercase();

        let success =
            if extension == "mp4" || extension == "avi" || extension == "mkv" || extension == "mov"
            {
                ffmpeg.generate_thumbnail(file_path, &thumbnail_path)
            } else {
                ffmpeg.generate_placeholder_thumbnail(&thumbnail_path, "file")
            };

        if success && thumbnail_path.exists() {
            Some(thumbnail_path.to_string_lossy().to_string())
        } else {
            None
        }
    }

    /// 检查数据库记录是否与文件信息不同
    fn is_record_changed(&self, file_info: &FileInfo, db_record: &FileInfo) -> bool {
        file_info.name != db_record.name
            || file_info.created_at != db_record.created_at
            || (db_record.width.is_none() && file_info.width.is_some())
            || (db_record.height.is_none() && file_info.height.is_some())
            || (db_record.thumbnail.is_none() && file_info.thumbnail.is_some())
    }

    /// 插入新记录
    fn insert_new_record(&self, file_info: &FileInfo, current_time: &str) -> Result<()> {
        self.db_manager.conn.execute(
            queries::INSERT_NEW,
            rusqlite::params![
                &file_info.name,
                &file_info.path,
                &file_info.file_type,
                &file_info.parent_path,
                &file_info.thumbnail.clone().unwrap_or_default(),
                &file_info.size.clone().unwrap_or_default(),
                &file_info.created_at,
                &file_info.subtitle.clone().unwrap_or_default(),
                current_time,
                &file_info.duration.clone().unwrap_or_default(),
                &file_info.width,
                &file_info.height,
            ],
        )?;
        Ok(())
    }

    /// 硬删除记录
    fn hard_delete_record(&self, path: &str) -> Result<()> {
        self.db_manager
            .conn
            .execute("DELETE FROM videos WHERE path = ?", &[path])?;
        Ok(())
    }
}
