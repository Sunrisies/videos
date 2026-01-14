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
                width INTEGER,
                height INTEGER
            )",
            [],
        )?;

        // 创建索引以提高查询速度
        conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON videos(path)", [])?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_parent ON videos(parent_path)",
            [],
        )?;

        // 执行数据库迁移（处理旧版本的 is_deleted 列）
        run_migrations(&conn)?;

        Ok(Self { conn })
    }
}

/// 执行数据库迁移
fn run_migrations(conn: &Connection) -> Result<()> {
    // 检查 videos 表的列信息
    let mut stmt = conn.prepare("PRAGMA table_info(videos)")?;
    let mut rows = stmt.query([])?;

    let mut has_is_deleted = false;
    let mut has_width = false;
    let mut has_height = false;

    while let Some(row) = rows.next()? {
        let name: String = row.get(1)?;
        match name.as_str() {
            "is_deleted" => has_is_deleted = true,
            "width" => has_width = true,
            "height" => has_height = true,
            _ => {}
        }
    }

    // 如果存在 is_deleted 列，执行迁移
    if has_is_deleted {
        println!("检测到旧版本数据库，开始迁移...");

        // 1. 删除可能存在的临时表（如果上次迁移失败）
        conn.execute("DROP TABLE IF EXISTS videos_temp", [])?;

        // 2. 创建临时表（不包含 is_deleted，包含 width/height）
        conn.execute(
            "CREATE TABLE videos_temp (
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
                width INTEGER,
                height INTEGER
            )",
            [],
        )?;

        // 2. 复制数据（排除 is_deleted 列）
        conn.execute(
            "INSERT INTO videos_temp 
             SELECT id, name, path, type, thumbnail, duration, size, resolution, 
                    bitrate, codec, created_at, subtitle, parent_path, last_modified, NULL, NULL
             FROM videos",
            [],
        )?;

        // 3. 删除原表
        conn.execute("DROP TABLE videos", [])?;

        // 4. 重命名临时表
        conn.execute("ALTER TABLE videos_temp RENAME TO videos", [])?;

        // 5. 重新创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON videos(path)", [])?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_parent ON videos(parent_path)",
            [],
        )?;

        println!("数据库迁移完成");
    } else {
        // 添加 width 和 height 列（如果不存在）
        if !has_width {
            conn.execute("ALTER TABLE videos ADD COLUMN width INTEGER", [])?;
            println!("已添加 width 列");
        }
        if !has_height {
            conn.execute("ALTER TABLE videos ADD COLUMN height INTEGER", [])?;
            println!("已添加 height 列");
        }

        if has_width && has_height {
            println!("数据库已是最新版本，无需迁移");
        }
    }

    Ok(())
}
