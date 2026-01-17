//! 数据库表结构定义
//!
//! 定义视频数据表的结构和字段

/// 视频类型常量
pub mod video_types {
    pub const MP4: &str = "mp4";
    pub const M3U8: &str = "m3u8";
    pub const TS: &str = "ts";
    pub const SUBTITLE: &str = "subtitle";
    pub const IMAGE: &str = "image";
    pub const UNKNOWN: &str = "unknown";
}

/// SQL 查询语句常量
pub mod queries {
    /// 插入新视频记录
    pub const INSERT_NEW: &str = "INSERT INTO videos
        (name, path, type, parent_path, thumbnail, size, created_at, subtitle, last_modified, duration, width, height)
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)";
    /// 获取视频总数
    pub const SELECT_ALL_COUNT: &str = "SELECT COUNT(*) FROM videos";
    /// 获取所有视频记录，按创建时间倒序排序（最新在前）
    pub const SELECT_ALL: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, parent_path, width, height
        FROM videos
        ORDER BY created_at DESC";
    /// 获取所有视频记录的完整信息（不排序）
    pub const SELECT_ALL_FULL: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, parent_path, width, height
        FROM videos";
    /// 根据父路径获取视频记录，按创建时间倒序排序（最新在前）
    pub const SELECT_BY_PARENT: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, width, height
        FROM videos
        WHERE parent_path = ?
        ORDER BY created_at DESC";
}
