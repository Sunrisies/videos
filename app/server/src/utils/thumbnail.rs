use std::path::Path;

/// 助手：获取缩略图路径（已废弃，使用 DirectorySync::ensure_thumbnail）
#[deprecated(note = "使用 DirectorySync::ensure_thumbnail 代替")]
pub fn get_thumbnail_path(_file_path: &Path) -> Option<String> {
    None
}
