use std::path::Path;

/// 助手：获取缩略图路径
pub fn get_thumbnail_path(file_path: &Path) -> Option<String> {
    // 从公共目录获取相对路径
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
