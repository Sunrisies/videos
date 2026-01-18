use serde::{Deserialize, Serialize};

#[derive(Serialize, Debug, Clone)]
pub struct VideoInfo {
    pub id: i64,
    pub name: String,
    pub path: String,
    pub r#type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub children: Option<Vec<VideoInfo>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub thumbnail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resolution: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bitrate: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub codec: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subtitle: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<i32>,
}

#[derive(Serialize)]
pub struct VideoList {
    pub videos: Vec<VideoInfo>,
}

/// 分页查询参数
#[derive(Deserialize, Debug)]
pub struct PaginationParams {
    /// 页码，从1开始，默认为1
    #[serde(default = "default_page")]
    pub page: u32,

    /// 每页数量，默认为20
    #[serde(default = "default_page_size")]
    pub page_size: u32,

    /// 搜索关键词（可选）
    pub search: Option<String>,

    /// 排序字段（可选），默认按创建时间排序
    pub sort_by: Option<String>,

    /// 排序方向（可选），默认为desc
    pub sort_order: Option<String>,
}

fn default_page() -> u32 {
    1
}

fn default_page_size() -> u32 {
    20
}

/// 分页响应结构
#[derive(Serialize)]
pub struct PaginatedVideoList {
    pub videos: Vec<VideoInfo>,
    pub pagination: PaginationInfo,
}

/// 分页信息
#[derive(Serialize)]
pub struct PaginationInfo {
    pub page: u32,
    pub page_size: u32,
    pub total: u64,
    pub total_pages: u32,
    pub has_next: bool,
    pub has_prev: bool,
}
