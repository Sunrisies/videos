use crate::models::VideoInfo;
use rusqlite::{Connection, Result};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use walkdir::WalkDir;

/// Database Manager Implementation
pub struct VideoDbManager {
    conn: Connection,
}

impl VideoDbManager {
    /// Initializes the database connection and creates the schema if it doesn't exist.
    pub fn new(db_path: &str) -> Result<Self> {
        let conn = Connection::open(db_path)?;

        // Create videos table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                thumbnail TEXT,
                duration INTEGER,
                size TEXT,
                resolution TEXT,
                bitrate TEXT,
                codec TEXT,
                created_at TEXT,
                subtitle TEXT,
                parent_path TEXT,
                last_modified INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )",
            [],
        )?;

        // Create index for faster queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON videos(path)", [])?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_parent ON videos(parent_path)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deleted ON videos(is_deleted)",
            [],
        )?;

        Ok(Self { conn })
    }

    /// Recursively scans a directory and populates the database.
    pub fn initialize_from_directory(&self, root_path: &str) -> Result<()> {
        println!("Initializing database from directory: {}", root_path);

        // Clear existing data for fresh initialization
        self.conn.execute("DELETE FROM videos", [])?;

        // Scan and populate
        self.sync_directory(root_path)?;

        println!("Database initialization completed");
        Ok(())
    }

    /// Scans the directory and updates the database (Add/Update).
    /// Detects deletions by comparing DB entries against the filesystem.
    pub fn sync_directory(&self, root_path: &str) -> Result<()> {
        let root = PathBuf::from(root_path);
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            .to_string();

        // Mark all existing entries as potentially deleted
        self.conn.execute(
            "UPDATE videos SET is_deleted = 1 WHERE parent_path LIKE ?1",
            &[&format!("{}%", root_path)],
        )?;

        // Scan and insert/update entries
        self.scan_and_insert(&root, &current_time)?;

        // Remove entries that are still marked as deleted (not found during scan)
        let deleted_count = self.conn.execute(
            "DELETE FROM videos WHERE is_deleted = 1 AND parent_path LIKE ?1",
            &[&format!("{}%", root_path)],
        )?;

        if deleted_count > 0 {
            println!("Removed {} deleted entries from database", deleted_count);
        }

        Ok(())
    }

    fn scan_and_insert(&self, path: &Path, current_time: &str) -> Result<()> {
        if path.is_dir() {
            // Check if this directory contains m3u8 files
            let has_m3u8 = self.has_m3u8_file(path);

            if has_m3u8 {
                // For m3u8 directories, store the directory but don't store individual m3u8/ts files
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

                // Get duration from m3u8 file
                let duration = self.get_m3u8_duration(path);

                // Insert or update the directory as hls_directory
                self.conn.execute(
                    "INSERT OR REPLACE INTO videos
                    (name, path, type, parent_path, created_at, last_modified, is_deleted, duration)
                    VALUES (?1, ?2, ?3, ?4, ?5, ?6, 0, ?7)",
                    &[
                        &name,
                        &path.to_string_lossy().to_string(),
                        "hls_directory",
                        &parent_path,
                        &created_at.as_deref().unwrap_or(""),
                        current_time,
                        &duration.as_deref().unwrap_or(""),
                    ],
                )?;

                // Don't recursively scan m3u8 directories - we don't want to store individual files
                return Ok(());
            }

            // For non-m3u8 directories, scan normally
            for entry in WalkDir::new(path)
                .max_depth(1)
                .into_iter()
                .filter_map(|e| e.ok())
            {
                let entry_path = entry.path();

                // Skip the root directory itself
                if entry_path == path {
                    continue;
                }

                if entry_path.is_dir() {
                    // For directories, we need to check if they contain video content
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

                        let r#type = if self.has_m3u8_file(entry_path) {
                            "hls_directory"
                        } else {
                            "directory"
                        };

                        let created_at = self.get_created_at(entry_path);

                        // Insert or update
                        self.conn.execute(
                            "INSERT OR REPLACE INTO videos
                            (name, path, type, parent_path, created_at, last_modified, is_deleted)
                            VALUES (?1, ?2, ?3, ?4, ?5, ?6, 0)",
                            &[
                                &name,
                                &entry_path.to_string_lossy().to_string(),
                                r#type,
                                &parent_path,
                                &created_at.as_deref().unwrap_or(""),
                                current_time,
                            ],
                        )?;

                        // Recursively scan subdirectories
                        self.scan_and_insert(entry_path, current_time)?;
                    }
                } else if entry_path.is_file() {
                    // Check if it's a video-related file
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
                            "mp4"
                        } else if extension == "m3u8" {
                            "m3u8"
                        } else if extension == "ts" {
                            "ts"
                        } else if extension == "vtt" || extension == "srt" {
                            "subtitle"
                        } else if extension == "jpg" || extension == "png" || extension == "gif" {
                            "image"
                        } else {
                            "unknown"
                        };
                        // Get file metadata
                        let metadata = std::fs::metadata(entry_path).ok();
                        let size = metadata.as_ref().map(|m| self.format_size(m.len()));
                        let created_at = metadata.and_then(|m| self.get_systemtime_created(&m));

                        // Get thumbnail path
                        let thumbnail = self.get_thumbnail_path(entry_path);

                        // Get video duration based on type
                        let duration = if r#type == "mp4" {
                            self.get_video_duration(entry_path)
                        } else if r#type == "m3u8" {
                            // For m3u8 files, get duration from the file itself
                            self.get_m3u8_duration(entry_path.parent().unwrap_or(entry_path))
                        } else {
                            None
                        };
                        println!("duration: {:?}", duration);
                        // If it's a subtitle file, set subtitle field
                        let subtitle = if r#type == "subtitle" {
                            Some(entry_path.to_string_lossy().to_string())
                        } else {
                            None
                        };

                        // Insert or update
                        self.conn.execute(
                            "INSERT OR REPLACE INTO videos
                            (name, path, type, parent_path, thumbnail, size, created_at, subtitle, last_modified, is_deleted, duration)
                            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 0, ?10)",
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
                            ]
                        )?;
                    }
                }
            }
        }
        Ok(())
    }

    /// Retrieves all videos and reconstructs the hierarchy into a Vec<VideoInfo>.
    pub fn get_video_tree(&self) -> Result<Vec<VideoInfo>> {
        // Get all non-deleted entries
        let mut stmt = self.conn.prepare(
            "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, parent_path
             FROM videos WHERE is_deleted = 0
             ORDER BY type DESC, name ASC"
        )?;

        let video_iter = stmt.query_map([], |row| {
            Ok(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        // Build tree structure
        Ok(self.build_tree(videos))
    }

    /// Get videos at root level (public directory)
    pub fn get_root_videos(&self) -> Result<Vec<VideoInfo>> {
        let public_path = Path::new("public").to_string_lossy().to_string();

        let mut stmt = self.conn.prepare(
            "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle
             FROM videos
             WHERE parent_path = ? AND is_deleted = 0
             ORDER BY type DESC, name ASC"
        )?;

        let video_iter = stmt.query_map([&public_path], |row| {
            Ok(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        Ok(videos)
    }

    /// Get children of a specific path
    pub fn get_children(&self, parent_path: &str) -> Result<Vec<VideoInfo>> {
        // First check if this is an hls_directory
        let mut type_stmt = self
            .conn
            .prepare("SELECT type FROM videos WHERE path = ? AND is_deleted = 0")?;
        let mut type_rows = type_stmt.query([parent_path])?;

        if let Some(row) = type_rows.next()? {
            let parent_type: String = row.get(0)?;
            if parent_type == "hls_directory" {
                // For hls directories, return empty children (files are not stored separately)
                return Ok(Vec::new());
            }
        }

        let mut stmt = self.conn.prepare(
            "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle
             FROM videos
             WHERE parent_path = ? AND is_deleted = 0
             ORDER BY type DESC, name ASC"
        )?;

        let video_iter = stmt.query_map([parent_path], |row| {
            Ok(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        Ok(videos)
    }

    /// Get a single video info by path
    pub fn get_video_by_path(&self, path: &str) -> Result<Option<VideoInfo>> {
        let mut stmt = self.conn.prepare(
            "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle
             FROM videos
             WHERE path = ? AND is_deleted = 0"
        )?;

        let mut rows = stmt.query([path])?;

        if let Some(row) = rows.next()? {
            Ok(Some(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
            }))
        } else {
            Ok(None)
        }
    }

    /// Build tree structure from flat list
    fn build_tree(&self, videos: Vec<VideoInfo>) -> Vec<VideoInfo> {
        use std::collections::HashMap;

        // Create maps for building the tree
        let mut map: HashMap<String, VideoInfo> = HashMap::new();
        let mut children_map: HashMap<String, Vec<String>> = HashMap::new();

        // First pass: store all videos and track parent-child relationships
        for video in videos {
            let path = video.path.clone();
            let parent_path = self.get_parent_path(&path);

            // Store the video
            map.insert(path.clone(), video);

            // Track parent-child relationship
            if let Some(parent) = parent_path {
                children_map.entry(parent).or_default().push(path);
            }
        }

        // Second pass: build tree by attaching children to parents
        let mut root_items: Vec<VideoInfo> = Vec::new();
        let public_path = Path::new("public").to_string_lossy().to_string();

        // Get all paths that need to be processed
        let all_paths: Vec<String> = map.keys().cloned().collect();

        for path in all_paths {
            // Check if this item still exists in map (it might have been moved)
            if let Some(video) = map.get(&path).cloned() {
                let mut modified_video = video.clone();

                // Attach children if any
                if let Some(children_paths) = children_map.get(&path) {
                    let mut children: Vec<VideoInfo> = Vec::new();
                    for child_path in children_paths {
                        if let Some(child) = map.get(child_path) {
                            children.push(child.clone());
                        }
                    }
                    if !children.is_empty() {
                        modified_video.children = Some(children);
                    }
                }

                // Check if this is a root item (parent is public directory)
                let parent = self.get_parent_path(&path);
                if let Some(parent_path) = parent {
                    if parent_path == public_path {
                        root_items.push(modified_video);
                    }
                }
            }
        }

        root_items
    }

    fn get_parent_path(&self, path: &str) -> Option<String> {
        let path_buf = PathBuf::from(path);
        path_buf.parent().map(|p| p.to_string_lossy().to_string())
    }

    /// Helper: Check if path is video or container
    fn is_video_or_container(&self, path: &Path) -> bool {
        if path.is_dir() {
            return self.has_m3u8_file(path) || self.has_video_file(path);
        }
        if path.is_file() {
            let extension = path.extension().and_then(|e| e.to_str()).unwrap_or("");

            // If this is a ts file, check if there's an m3u8 file in the same directory
            if extension.eq_ignore_ascii_case("ts") {
                if let Some(parent) = path.parent() {
                    if self.has_m3u8_file(parent) {
                        return false; // Skip ts files when m3u8 exists
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

    /// Helper: Check if directory has m3u8 file
    fn has_m3u8_file(&self, path: &Path) -> bool {
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
                    .map(|ext| ext.eq_ignore_ascii_case("m3u8"))
                    .unwrap_or(false)
            })
    }

    /// Helper: Check if directory has video file
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

    /// Helper: Get created time
    fn get_created_at(&self, path: &Path) -> Option<String> {
        std::fs::metadata(path)
            .ok()
            .and_then(|m| self.get_systemtime_created(&m))
    }

    /// Helper: Format system time
    fn get_systemtime_created(&self, metadata: &std::fs::Metadata) -> Option<String> {
        use std::time::UNIX_EPOCH;

        metadata.created().ok().and_then(|time| {
            let duration = time.duration_since(UNIX_EPOCH).ok()?;
            let seconds = duration.as_secs();

            let days = seconds / 86400;
            let remaining = seconds % 86400;
            let hours = remaining / 3600;
            let remaining = remaining % 3600;
            let minutes = remaining / 60;
            let secs = remaining % 60;

            let year = 1970 + (days / 365);
            let day_of_year = days % 365;
            let month = (day_of_year / 30) + 1;
            let day = (day_of_year % 30) + 1;

            Some(format!(
                "{:04}-{:02}-{:02} {:02}:{:02}:{:02}",
                year, month, day, hours, minutes, secs
            ))
        })
    }

    /// Helper: Format file size
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

    /// Helper: Get thumbnail path
    fn get_thumbnail_path(&self, file_path: &Path) -> Option<String> {
        // Get relative path from public directory
        let public_path = Path::new("public");
        if let Ok(relative_path) = file_path.strip_prefix(public_path) {
            let thumbnails_path = Path::new("thumbnails");
            let thumbnail_path = thumbnails_path.join(relative_path).with_extension("jpg");

            if thumbnail_path.exists() {
                Some(thumbnail_path.to_string_lossy().to_string())
            } else {
                None
            }
        } else {
            None
        }
    }

    /// Get video duration using FFprobe
    fn get_video_duration(&self, video_path: &Path) -> Option<String> {
        // Use ffmpeg to get video duration
        let output = Command::new("ffmpeg")
            .arg("-i")
            .arg(video_path)
            .arg("-f")
            .arg("null")
            .arg("-")
            .output()
            .ok()?;

        // Parse the output to extract duration information
        let output_str = String::from_utf8_lossy(&output.stderr);

        // Look for duration in the output
        // Example line: "Duration: 00:01:23.45, start: 0.000000, bitrate: 1234 kb/s"
        let duration_regex =
            regex::Regex::new(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})").ok()?;

        if let Some(captures) = duration_regex.captures(&output_str) {
            let hours = captures.get(1)?.as_str().parse::<u32>().ok()?;
            let minutes = captures.get(2)?.as_str().parse::<u32>().ok()?;
            let seconds = captures.get(3)?.as_str().parse::<u32>().ok()?;

            return Some(format!("{:02}:{:02}:{:02}", hours, minutes, seconds));
        }

        None
    }

    /// Get m3u8 duration by parsing the m3u8 file
    fn get_m3u8_duration(&self, m3u8_path: &Path) -> Option<String> {
        // Find the index.m3u8 file in the directory
        let index_m3u8 = m3u8_path.join("index.m3u8");

        if !index_m3u8.exists() {
            return None;
        }

        // Read the m3u8 file content
        let content = fs::read_to_string(&index_m3u8).ok()?;

        // Parse the m3u8 file to calculate total duration
        let mut total_duration = 0.0;

        for line in content.lines() {
            // Look for lines starting with #EXTINF: which contain duration info
            if line.starts_with("#EXTINF:") {
                // Extract the duration value
                let duration_part = line.trim_start_matches("#EXTINF:");
                if let Some(comma_pos) = duration_part.find(',') {
                    let duration_str = &duration_part[..comma_pos];
                    if let Ok(duration) = duration_str.trim().parse::<f64>() {
                        total_duration += duration;
                    }
                }
            }
        }

        // Convert total duration to HH:MM:SS format
        let hours = (total_duration / 3600.0).floor() as u32;
        let minutes = ((total_duration % 3600.0) / 60.0).floor() as u32;
        let seconds = (total_duration % 60.0).floor() as u32;

        Some(format!("{:02}:{:02}:{:02}", hours, minutes, seconds))
    }
}
