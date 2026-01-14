use crate::models::VideoInfo;
use crate::services::db::connection::VideoDbManager;
use crate::services::db::schema::queries;
use rusqlite::Result;

/// 视频数据访问对象
///
/// 提供视频数据的增删改查操作
pub struct VideoDao<'a> {
    db_manager: &'a VideoDbManager,
}

impl<'a> VideoDao<'a> {
    /// 创建新的视频数据访问对象
    pub fn new(db_manager: &'a VideoDbManager) -> Self {
        Self { db_manager }
    }

    /// 获取所有视频并重建层次结构
    #[allow(dead_code)]
    pub fn get_video_tree(&self) -> Result<Vec<VideoInfo>> {
        // 获取所有未删除的条目
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL)?;

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
                width: row.get(12)?,
                height: row.get(13)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        // 使用 TreeBuilder 构建树形结构
        Ok(crate::services::db::tree::TreeBuilder::build_tree(videos))
    }

    /// 获取根目录下的视频（public 目录）
    pub fn get_root_videos(&self) -> Result<Vec<VideoInfo>> {
        let public_path = std::path::Path::new("public").to_string_lossy().to_string();

        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_BY_PARENT)?;
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
                width: row.get(11)?,
                height: row.get(12)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        Ok(videos)
    }

    /// 获取指定路径的子节点
    pub fn get_children(&self, parent_path: &str) -> Result<Vec<VideoInfo>> {
        // 首先检查是否为 m3u8 类型
        let mut type_stmt = self.db_manager.conn.prepare(queries::SELECT_TYPE_BY_PATH)?;
        let mut type_rows = type_stmt.query([parent_path])?;

        if let Some(row) = type_rows.next()? {
            let parent_type: String = row.get(0)?;
            if parent_type == "m3u8" {
                // 对于 m3u8 类型，返回空子节点（文件不单独存储）
                return Ok(Vec::new());
            }
        }

        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_BY_PARENT)?;
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
                width: row.get(11)?,
                height: row.get(12)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        Ok(videos)
    }

    /// 通过路径获取单个视频信息
    pub fn get_video_by_path(&self, path: &str) -> Result<Option<VideoInfo>> {
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_BY_PATH)?;
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
                width: row.get(11)?,
                height: row.get(12)?,
            }))
        } else {
            Ok(None)
        }
    }
}
