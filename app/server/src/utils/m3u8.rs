use std::fs;
use std::path::{Path, PathBuf};
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

/// 检查当前目录下面以m3u8结尾的文件
pub fn check_m3u8_file(path: &Path) -> Option<PathBuf> {
    // 查找当前目录下面以m3u8结尾的文件
    let m3u8_file = fs::read_dir(&path)
        .ok()?
        .filter_map(|entry| entry.ok()) // 忽略读取错误的条目
        .find(|entry| {
            // 检查是否是文件，且扩展名是 "m3u8"
            let path = entry.path();
            path.is_file()
                && path
                    .extension()
                    .map_or(false, |ext| ext.eq_ignore_ascii_case("m3u8"))
        })
        .map(|entry| entry.path()); // 获取找到的文件的 PathBuf
    m3u8_file
}
