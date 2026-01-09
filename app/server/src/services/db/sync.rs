use crate::services::db::connection::VideoDbManager;
use crate::services::db::schema::{queries, video_types};
use crate::services::filesystem::{
    generate_default_thumbnail, generate_image_thumbnail, generate_video_thumbnail,
};
use crate::utils::{
    check_m3u8_file, format_size, get_created_at, get_m3u8_duration, get_systemtime_created,
    get_video_duration, has_m3u8_file, has_video_file, is_video_or_container,
};
use rusqlite::Result;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// 目录同步器
///
/// 负责扫描文件系统并同步数据到数据库，实现双向同步
pub struct DirectorySync<'a> {
    db_manager: &'a VideoDbManager,
}

/// 文件信息结构体，用于比较文件和数据库记录
#[derive(Debug, Clone)]
struct FileInfo {
    name: String,
    path: String,
    created_at: String,
    file_type: String,
    parent_path: String,
    thumbnail: Option<String>,
    size: Option<String>,
    subtitle: Option<String>,
    duration: Option<String>,
}

impl<'a> DirectorySync<'a> {
    /// 创建新的目录同步器
    pub fn new(db_manager: &'a VideoDbManager) -> Self {
        Self { db_manager }
    }

    /// 从目录初始化数据库（双向同步）
    pub fn initialize_from_directory(&self, root_path: &str, force: bool) -> Result<()> {
        println!("=== 开始数据库双向同步: {} ===", root_path);

        // 检查数据库是否已初始化
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL_COUNT)?;
        let count: i64 = stmt.query_row([], |row| row.get(0))?;

        if count > 0 && !force {
            println!("数据库已包含 {} 条记录，执行增量同步...", count);
            return self.bidirectional_sync(root_path);
        }

        // 如果 force 为 true 或数据库为空，则清除并重新初始化
        if force {
            println!("请求强制重新初始化，清除现有数据...");
            self.db_manager.conn.execute("DELETE FROM videos", [])?;
        }

        // 执行完整的双向同步
        self.bidirectional_sync(root_path)?;

        println!("=== 数据库双向同步完成 ===");
        Ok(())
    }

    /// 兼容旧接口：扫描目录并更新数据库
    pub fn sync_directory(&self, root_path: &str) -> Result<()> {
        self.bidirectional_sync(root_path)
    }

    /// 双向同步：文件系统 -> 数据库 + 数据库 -> 文件系统
    fn bidirectional_sync(&self, root_path: &str) -> Result<()> {
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            .to_string();

        // 1. 获取数据库中所有未删除的记录
        let db_records = self.get_all_db_records()?;
        println!("数据库中未删除记录数: {}", db_records.len());

        // 2. 扫描文件系统，构建文件映射
        let (fs_files, scan_errors) = self.scan_filesystem(root_path)?;
        println!(
            "文件系统扫描到文件数: {}, 错误数: {}",
            fs_files.len(),
            scan_errors.len()
        );

        // 记录扫描错误
        for error in &scan_errors {
            println!("扫描错误: {}", error);
        }

        // 3. 处理新增和变更的文件（文件系统 -> 数据库）
        let mut new_count = 0;
        let mut changed_count = 0;
        let mut skipped_count = 0;

        for (path, file_info) in &fs_files {
            match db_records.get(path) {
                None => {
                    // 文件在数据库中不存在，作为新记录插入
                    self.insert_new_record(file_info, &current_time)?;
                    new_count += 1;
                    println!("新增文件: {}", path);
                }
                Some(db_record) => {
                    // 文件在数据库中存在，检查是否需要更新
                    if self.is_record_changed(file_info, db_record) {
                        // 数据已变化，硬删除旧记录并插入新记录
                        self.hard_delete_record(path)?;
                        self.insert_new_record(file_info, &current_time)?;
                        changed_count += 1;
                        println!("变更文件: {}", path);
                    } else {
                        // 数据完全一致，跳过
                        skipped_count += 1;
                    }
                }
            }
        }

        // 4. 处理删除的文件（数据库 -> 文件系统）
        let mut deleted_count = 0;
        for (path, _db_record) in &db_records {
            if !fs_files.contains_key(path) {
                // 数据库记录对应的文件已不存在，硬删除
                self.hard_delete_record(path)?;
                deleted_count += 1;
                println!("删除文件: {}", path);
            }
        }

        println!("=== 同步统计 ===");
        println!("新增文件: {}", new_count);
        println!("变更文件: {}", changed_count);
        println!("删除文件: {}", deleted_count);
        println!("跳过文件: {}", skipped_count);
        println!("错误数量: {}", scan_errors.len());

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
            };
            records.insert(record.path.clone(), record);
        }

        Ok(records)
    }

    /// 扫描文件系统，返回文件映射和错误列表
    fn scan_filesystem(&self, root_path: &str) -> Result<(HashMap<String, FileInfo>, Vec<String>)> {
        let mut files = HashMap::new();
        let mut errors = Vec::new();

        let root = PathBuf::from(root_path);

        // 检查根目录是否存在
        if !root.exists() {
            errors.push(format!("根目录不存在: {}", root_path));
            return Ok((files, errors));
        }

        // 使用 WalkDir 递归扫描
        for entry in WalkDir::new(&root).max_depth(1).into_iter() {
            let entry = match entry {
                Ok(e) => e,
                Err(e) => {
                    errors.push(format!("无法访问条目: {}", e));
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

            // 处理 m3u8 目录特殊情况
            if path.is_dir() && has_m3u8_file(path) {
                println!("处理 m3u8 目录: {:?}", path);
                match self.process_m3u8_directory(path, &root) {
                    Ok(file_info) => {
                        println!("m3u8 目录处理完成: {:?}", file_info);
                        files.insert(file_info.path.clone(), file_info);
                    }
                    Err(e) => {
                        errors.push(format!("处理 m3u8 目录错误: {}", e));
                    }
                }
                continue;
            }

            // 处理普通文件和目录
            match self.process_file_or_directory(path, &root) {
                Ok(Some(file_info)) => {
                    files.insert(file_info.path.clone(), file_info);
                }
                Ok(None) => {
                    // 跳过不需要处理的条目
                }
                Err(e) => {
                    errors.push(format!("处理条目错误: {}", e));
                }
            }
        }

        Ok((files, errors))
    }

    /// 处理 m3u8 目录
    fn process_m3u8_directory(&self, path: &Path, _root: &Path) -> Result<FileInfo> {
        let parent_path = path
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        let path_str = check_m3u8_file(&path).unwrap_or_default();
        println!("m3u8 目录处理完成:------ {:?}", path_str);

        // 使用目录名称作为文件名
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        let created_at = get_created_at(path).unwrap_or_default();
        let duration = get_m3u8_duration(path);

        Ok(FileInfo {
            name,
            path: path_str.to_string_lossy().to_string(),
            created_at,
            file_type: video_types::M3U8.to_string(),
            parent_path,
            thumbnail: Some(format!("{}\\index.jpg", path.display())),
            size: None,
            subtitle: None,
            duration,
        })
    }

    /// 处理普通文件或目录
    fn process_file_or_directory(&self, path: &Path, _root: &Path) -> Result<Option<FileInfo>> {
        if path.is_dir() {
            // 对于目录，检查是否包含视频内容
            if !has_video_file(path) {
                return Ok(None);
            }

            let parent_path = path
                .parent()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_default();

            let name = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("")
                .to_string();

            let created_at = get_created_at(path).unwrap_or_default();
            let r#type = if has_m3u8_file(path) {
                video_types::M3U8
            } else {
                video_types::DIRECTORY
            };
            let duration = get_m3u8_duration(path);
            let thumbnail = Some(format!("{}\\index.jpg", path.display()));

            Ok(Some(FileInfo {
                name,
                path: path.to_string_lossy().to_string(),
                created_at,
                file_type: r#type.to_string(),
                parent_path,
                thumbnail,
                size: None,
                subtitle: None,
                duration,
            }))
        } else if path.is_file() {
            // 获取文件扩展名
            let extension = path
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_lowercase();

            // 确定文件类型
            let r#type = match extension.as_str() {
                "mp4" => video_types::MP4,
                "m3u8" => video_types::M3U8,
                "ts" => video_types::TS,
                "vtt" | "srt" => video_types::SUBTITLE,
                "jpg" | "png" | "gif" => video_types::IMAGE,
                _ => video_types::UNKNOWN,
            };

            // 对于 ts 文件，如果同一目录下有 m3u8 文件，则跳过
            if extension == "ts" {
                if let Some(parent) = path.parent() {
                    if has_m3u8_file(parent) {
                        return Ok(None);
                    }
                }
            }

            let parent_path = path
                .parent()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_default();

            let name = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("")
                .to_string();

            // 获取文件元数据
            let metadata = std::fs::metadata(path).ok();
            let size = metadata.as_ref().map(|m| format_size(m.len()));
            let created_at = metadata
                .and_then(|m| get_systemtime_created(&m))
                .unwrap_or_default();

            // 生成或获取缩略图路径
            let thumbnail = self.ensure_thumbnail(path);

            // 获取视频时长
            let duration = if r#type == video_types::MP4 {
                get_video_duration(path)
            } else {
                None
            };

            // 获取字幕路径
            let subtitle = if r#type == video_types::SUBTITLE {
                Some(path.to_string_lossy().to_string())
            } else {
                None
            };

            Ok(Some(FileInfo {
                name,
                path: path.to_string_lossy().to_string(),
                created_at,
                file_type: r#type.to_string(),
                parent_path,
                thumbnail,
                size,
                subtitle,
                duration,
            }))
        } else {
            Ok(None)
        }
    }

    /// 检查数据库记录是否与文件信息不同
    fn is_record_changed(&self, file_info: &FileInfo, db_record: &FileInfo) -> bool {
        // 检查关键字段是否发生变化
        // 注意：我们只检查 name 和 created_at，因为 path 是唯一的标识符
        file_info.name != db_record.name || file_info.created_at != db_record.created_at
    }

    /// 插入新记录
    fn insert_new_record(&self, file_info: &FileInfo, current_time: &str) -> Result<()> {
        self.db_manager.conn.execute(
            queries::INSERT_NEW,
            &[
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

    /// 确保缩略图存在，如果不存在则生成
    fn ensure_thumbnail(&self, file_path: &Path) -> Option<String> {
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

            if extension == "mp4" || extension == "avi" || extension == "mkv" || extension == "mov"
            {
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
}
