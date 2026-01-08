use std::path::Path;

use walkdir::WalkDir;

/// 助手：检查目录中是否有m3u8文件
pub fn has_m3u8_file(path: &Path) -> bool {
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
