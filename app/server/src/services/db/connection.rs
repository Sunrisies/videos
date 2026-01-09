use rusqlite::{Connection, Result};

/// 数据库连接管理器
///
/// 负责数据库连接的创建、初始化和管理
pub struct VideoDbManager {
    pub(crate) conn: Connection,
}

impl VideoDbManager {
    /// 初始化数据库连接并创建表结构（如果不存在）
    pub fn new(db_path: &str) -> Result<Self> {
        let conn = Connection::open(db_path)?;

        // 创建视频表
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

        // 创建索引以提高查询速度
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
}
