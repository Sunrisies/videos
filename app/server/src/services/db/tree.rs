use crate::models::VideoInfo;
use std::collections::HashMap;
use std::path::Path;

/// 树形结构构建器
///
/// 负责将扁平的视频数据转换为层次化的树形结构
#[allow(dead_code)]
pub struct TreeBuilder;

#[allow(dead_code)]
impl TreeBuilder {
    /// 从扁平列表构建树形结构
    #[allow(dead_code)]
    pub fn build_tree(videos: Vec<VideoInfo>) -> Vec<VideoInfo> {
        // 创建用于构建树的映射
        let mut map: HashMap<String, VideoInfo> = HashMap::new();
        let mut children_map: HashMap<String, Vec<String>> = HashMap::new();

        // 第一遍：存储所有视频并跟踪父-子关系
        for video in videos {
            let path = video.path.clone();
            let parent_path = Self::get_parent_path(&path);

            // 存储视频
            map.insert(path.clone(), video);

            // 跟踪父-子关系
            if let Some(parent) = parent_path {
                children_map.entry(parent).or_default().push(path);
            }
        }

        // 第二遍：通过将子节点附加到父节点来构建树
        let mut root_items: Vec<VideoInfo> = Vec::new();
        let public_path = Path::new("public").to_string_lossy().to_string();

        // 获取所有需要处理的路径
        let all_paths: Vec<String> = map.keys().cloned().collect();

        for path in all_paths {
            // 检查此项目是否仍存在于映射中（可能已被移动）
            if let Some(video) = map.get(&path).cloned() {
                let mut modified_video = video.clone();

                // 附加子节点（如果有）
                if let Some(children_paths) = children_map.get(&path) {
                    let mut children: Vec<VideoInfo> = Vec::new();
                    for child_path in children_paths {
                        if let Some(child) = map.get(child_path) {
                            children.push(child.clone());
                        }
                    }
                    if !children.is_empty() {
                        modified_video.children = Some(children);
                    }
                }

                // 检查是否为根项目（父节点是 public 目录）
                let parent = Self::get_parent_path(&path);
                if let Some(parent_path) = parent {
                    if parent_path == public_path {
                        root_items.push(modified_video);
                    }
                }
            }
        }

        root_items
    }

    /// 获取父路径
    fn get_parent_path(path: &str) -> Option<String> {
        let path_buf = std::path::PathBuf::from(path);
        path_buf.parent().map(|p| p.to_string_lossy().to_string())
    }
}
