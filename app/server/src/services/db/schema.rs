//! 数据库表结构定义
//!
//! 定义视频数据表的结构和字段

/// 视频类型常量
pub mod video_types {
    pub const HLS_DIRECTORY: &str = "hls_directory";
    pub const DIRECTORY: &str = "directory";
    pub const MP4: &str = "mp4";
    pub const M3U8: &str = "m3u8";
    pub const TS: &str = "ts";
    pub const SUBTITLE: &str = "subtitle";
    pub const IMAGE: &str = "image";
    pub const UNKNOWN: &str = "unknown";
}

/// SQL 查询语句常量
pub mod queries {
    pub const INSERT_OR_REPLACE: &str = "INSERT OR REPLACE INTO videos
        (name, path, type, parent_path, created_at, last_modified, is_deleted, duration)
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, 0, ?7)";

    pub const INSERT_OR_REPLACE_WITH_THUMBNAIL: &str = "INSERT OR REPLACE INTO videos
        (name, path, type, parent_path, created_at, last_modified, thumbnail, is_deleted, duration)
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 0, ?8)";

    pub const INSERT_OR_REPLACE_FULL: &str = "INSERT OR REPLACE INTO videos
        (name, path, type, parent_path, thumbnail, size, created_at, subtitle, last_modified, is_deleted, duration)
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 0, ?10)";

    pub const UPDATE_MARK_DELETED: &str =
        "UPDATE videos SET is_deleted = 1 WHERE parent_path LIKE ?1";

    pub const DELETE_MARKED: &str =
        "DELETE FROM videos WHERE is_deleted = 1 AND parent_path LIKE ?1";

    pub const SELECT_ALL_COUNT: &str = "SELECT COUNT(*) FROM videos";

    pub const SELECT_ALL_NON_DELETED: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, parent_path
        FROM videos WHERE is_deleted = 0
        ORDER BY type DESC, name ASC";

    pub const SELECT_BY_PARENT: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle
        FROM videos
        WHERE parent_path = ? AND is_deleted = 0
        ORDER BY type DESC, name ASC";

    pub const SELECT_BY_PATH: &str = "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle
        FROM videos
        WHERE path = ? AND is_deleted = 0";

    pub const SELECT_TYPE_BY_PATH: &str =
        "SELECT type FROM videos WHERE path = ? AND is_deleted = 0";
}
