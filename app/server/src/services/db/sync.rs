//! 目录同步器
//!
//! 负责扫描文件系统并同步数据到数据库，支持：
//! - 并行文件处理
//! - 增量扫描
//! - 双向同步
//! - 流式处理优化

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
    /// 优化版本：使用流式处理，减少内存占用
    fn bidirectional_sync_with_progress(&self, mappings: &Vec<DiskMapping>) -> Result<()> {
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            .to_string();

        // 1. 获取数据库中所有记录
        let db_records = self.get_all_db_records()?;
        info!("数据库中记录数: {}", db_records.len());

        // 2. 使用流式处理同步文件系统
        let mut new_count = 0;
        let mut changed_count = 0;
        let mut skipped_count = 0;
        let mut deleted_count = 0;

        // 使用 Arc 和 Mutex 共享计数器，用于跨线程统计
        let stats = Arc::new(StdMutex::new(Stats {
            new: 0,
            changed: 0,
            skipped: 0,
        }));

        // 创建数据库连接的克隆（如果支持）
        // 注意：SQLite 连接不支持跨线程使用，需要在每个线程创建新连接
        // 这里假设 VideoDbManager 提供了创建新连接的方法
        // 如果不支持，需要使用通道将数据发送到主线程处理

        for mapping in mappings.iter() {
            let physical_path = Path::new(&mapping.physical_path);
            let route_path = &mapping.route_path;

            // 流式处理文件系统
            let (processed_count, error_count) = self.process_filesystem_streaming(
                physical_path,
                route_path,
                &db_records,
                &current_time,
                &stats,
            )?;

            info!(
                "处理目录 {} 完成: 处理 {} 个文件, {} 个错误",
                mapping.route_path, processed_count, error_count
            );
        }

        // 获取统计结果
        let stats_guard = stats.lock().unwrap();
        new_count = stats_guard.new;
        changed_count = stats_guard.changed;
        skipped_count = stats_guard.skipped;
        drop(stats_guard);

        // 3. 处理删除的文件
        let mut processed_files = HashMap::new();
        for mapping in mappings.iter() {
            self.collect_file_paths(Path::new(&mapping.physical_path), &mut processed_files);
        }

        for (path, db_record) in db_records.iter() {
            if !processed_files.contains_key(path) {
                self.hard_delete_record(path)?;
                deleted_count += 1;
                debug!("删除: {}", db_record.name);
            }
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

        Ok(())
    }

    /// 流式处理文件系统
    /// 优化版本：边扫描边处理，减少内存占用
    fn process_filesystem_streaming(
        &self,
        root_path: &Path,
        route_path: &str,
        db_records: &HashMap<String, FileInfo>,
        current_time: &str,
        stats: &Arc<StdMutex<Stats>>,
    ) -> Result<(usize, usize)> {
        let root = PathBuf::from(root_path);

        // 检查根目录是否存在
        if !root.exists() {
            warn!("根目录不存在: {}", root_path.display());
            return Ok((0, 0));
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
        let total = pending_entries.len();
        let processed_counter = Arc::new(StdMutex::new(0usize));
        let error_counter = Arc::new(StdMutex::new(0usize));

        // 使用通道收集处理结果
        let (tx, rx) = std::sync::mpsc::channel();

        // 分批处理以避免通道过大
        let batch_size = 100;
        let batches: Vec<_> = pending_entries.chunks(batch_size).collect();

        // 处理批次
        for batch in batches {
            let batch = batch.to_vec();
            let tx_clone = tx.clone();
            let root_ref = root.clone();
            let route_path_ref = route_path.to_string();
            let db_records_ref = db_records.clone();
            let current_time_ref = current_time.to_string();
            let stats_ref = stats.clone();
            let processed_counter_ref = processed_counter.clone();
            let error_counter_ref = error_counter.clone();
            let total_ref = total;

            // 在线程池中处理每个批次
            rayon::spawn(move || {
                for entry in batch {
                    let result = Self::process_file_static(
                        &entry.path,
                        &root_ref,
                        &route_path_ref,
                        &db_records_ref,
                        &current_time_ref,
                        &stats_ref,
                    );

                    match result {
                        Ok(Some(file_info)) => {
                            // 发送处理结果到主线程
                            let _ = tx_clone.send(Ok(file_info));
                        }
                        Ok(None) => {
                            // 跳过不需要处理的条目
                        }
                        Err(e) => {
                            let _ = tx_clone.send(Err(e));
                            let mut guard = error_counter_ref.lock().unwrap();
                            *guard += 1;
                        }
                    }

                    // 更新进度
                    let mut guard = processed_counter_ref.lock().unwrap();
                    *guard += 1;
                    let processed = *guard;

                    if processed % 10 == 0 || processed == total_ref {
                        info!("已处理 {} / {}", processed, total_ref);
                    }
                }
            });
        }

        // 关闭发送端
        drop(tx);

        // 主线程处理数据库操作
        for result in rx {
            match result {
                Ok(file_info) => {
                    // 直接处理数据库操作
                    match db_records.get(&file_info.path) {
                        None => {
                            if let Err(e) = self.insert_new_record(&file_info, current_time) {
                                warn!("插入记录失败: {} - {}", file_info.name, e);
                            }
                        }
                        Some(db_record) => {
                            if self.is_record_changed(&file_info, db_record) {
                                if let Err(e) = self.hard_delete_record(&file_info.path) {
                                    warn!("删除旧记录失败: {} - {}", file_info.name, e);
                                }
                                if let Err(e) = self.insert_new_record(&file_info, current_time) {
                                    warn!("更新记录失败: {} - {}", file_info.name, e);
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!("处理文件失败: {}", e);
                }
            }
        }

        // 获取处理计数
        let processed = *processed_counter.lock().unwrap();
        let errors = *error_counter.lock().unwrap();

        Ok((processed, errors))
    }

    /// 收集文件路径（用于检测删除的文件）
    fn collect_file_paths(&self, root: &Path, paths: &mut HashMap<String, ()>) {
        for entry in WalkDir::new(root)
            .max_depth(1)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            let path = entry.path();
            if path == root || !is_video_or_container(path) {
                continue;
            }
            paths.insert(path.to_string_lossy().to_string(), ());
        }
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

    /// 静态方法：处理普通文件（用于并行处理）
    /// 优化版本：增加数据库记录比较，避免不必要的处理
    fn process_file_static(
        path: &Path,
        _root: &Path,
        route_path: &str,
        db_records: &HashMap<String, FileInfo>,
        current_time: &str,
        stats: &Arc<StdMutex<Stats>>,
    ) -> std::result::Result<Option<FileInfo>, String> {
        if !path.is_file() {
            return Ok(None);
        }

        let path_str = path.to_string_lossy().to_string();

        // 检查是否已存在于数据库中，如果存在且未变更，则跳过处理
        if let Some(db_record) = db_records.get(&path_str) {
            let metadata = std::fs::metadata(path).ok();
            let created_at = metadata
                .as_ref()
                .and_then(|m| get_systemtime_created(m))
                .unwrap_or_default();

            // 如果创建时间相同，且已有缩略图和尺寸信息，则跳过详细处理
            if created_at == db_record.created_at
                && db_record.thumbnail.is_some()
                && db_record.width.is_some()
                && db_record.height.is_some()
            {
                // 更新跳过计数
                let mut stats_guard = stats.lock().unwrap();
                stats_guard.skipped += 1;
                return Ok(None);
            }
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

        // 更新统计信息
        let path_str = path.to_string_lossy().to_string();
        if db_records.contains_key(&path_str) {
            let mut stats_guard = stats.lock().unwrap();
            info!("changed: {}", path_str);
            stats_guard.changed += 1;
        } else {
            let mut stats_guard = stats.lock().unwrap();
            stats_guard.new += 1;
        }

        Ok(Some(FileInfo {
            name,
            path: path_str,
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

/// 统计信息结构体
#[derive(Debug, Default)]
struct Stats {
    new: usize,
    changed: usize,
    skipped: usize,
}
