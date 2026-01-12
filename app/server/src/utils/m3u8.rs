use log::{error, info};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
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

/// 将指定目录下的 m3u8 文件合并为 mp4 文件
///
/// # 参数
/// * `dir_path` - 包含 m3u8 文件的目录路径
///
/// # 返回
/// 返回生成的 mp4 文件的路径，如果失败则返回错误
pub fn merge_m3u8_to_mp4(dir_path: &Path) -> Result<PathBuf, String> {
    // 确保目录存在
    // if !dir_path.exists() {
    //     return Err(format!("目录不存在: {:?}", dir_path));
    // }
    info!("dir_path:{:?}", dir_path);
    // 查找目录中的 m3u8 文件
    let m3u8_files = find_m3u8_files(dir_path);
    info!("找到 m3u8 文件数量: {:?}", m3u8_files);
    if m3u8_files.is_empty() {
        return Err(format!("在目录 {:?} 中未找到 m3u8 文件", dir_path));
    }

    // 如果有多个 m3u8 文件，只处理第一个
    let m3u8_file = &m3u8_files[0];
    info!("找到 m3u8 文件: {:?}", dir_path);

    // 生成输出文件名（与 m3u8 同名，但扩展名为 mp4）
    let file_stem = dir_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("output");
    let root = PathBuf::from("public");
    let output_path = root.join(format!("{}.mp4", file_stem));

    // 如果输出文件已存在，先删除
    if output_path.exists() {
        fs::remove_file(&output_path)
            .map_err(|e| format!("无法删除已存在的输出文件 {:?}: {}", output_path, e))?;
    }

    // 使用 ffmpeg 合并 m3u8 文件
    let m3u8_path = m3u8_file.to_string_lossy().to_string();
    let output_path_str = output_path.to_string_lossy().to_string();
    info!(
        "m3u8_path:{:?}, output_path_str:{:?}",
        m3u8_path, output_path_str
    );
    info!("开始合并 m3u8 文件到 mp4...");
    let output = Command::new("ffmpeg")
        .args([
            "-i",
            &m3u8_path, // 输入 m3u8 文件
            "-c",
            "copy", // 直接复制流，不重新编码
            "-bsf:a",
            "aac_adtstoasc",  // 修复 AAC 流
            "-y",             // 覆盖输出文件
            &output_path_str, // 输出 mp4 文件
        ])
        .output();

    match output {
        Ok(output) => {
            if output.status.success() && output_path.exists() {
                info!("✓ 成功将 m3u8 合并为 mp4: {:?}", output_path);
                info!("删除原目录: {:?}", dir_path);
                if let Err(e) = fs::remove_dir_all(dir_path) {
                    error!("删除目录失败: {}", e);
                    // 即使删除失败，也返回成功，因为 mp4 文件已经生成
                }
                Ok(output_path)
            } else {
                let error_msg = format!(
                    "合并 m3u8 失败: {:?}, FFmpeg 错误: {}",
                    m3u8_file,
                    String::from_utf8_lossy(&output.stderr)
                );
                error!("{}", error_msg);
                Err(error_msg)
            }
        }
        Err(e) => {
            let error_msg = format!("执行 FFmpeg 失败: {}", e);
            error!("{}", error_msg);
            Err(error_msg)
        }
    }
}
/// 在指定目录中查找所有 m3u8 文件
fn find_m3u8_files(dir_path: &Path) -> Vec<PathBuf> {
    let mut m3u8_files = Vec::new();

    if let Ok(entries) = fs::read_dir(dir_path) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() {
                if let Some(extension) = path.extension() {
                    if extension == "m3u8" {
                        m3u8_files.push(path);
                    }
                }
            }
        }
    }

    m3u8_files
}
