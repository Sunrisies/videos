use crate::models::{PaginatedVideoList, PaginationInfo, VideoInfo};
use crate::services::db::connection::VideoDbManager;
use crate::services::db::schema::queries;
use rusqlite::Result;

/// 视频数据访问对象
///
/// 提供视频数据的增删改查操作
pub struct VideoDao<'a> {
    db_manager: &'a VideoDbManager,
}

impl<'a> VideoDao<'a> {
    /// 创建新的视频数据访问对象
    pub fn new(db_manager: &'a VideoDbManager) -> Self {
        Self { db_manager }
    }

    /// 获取所有视频并重建层次结构
    #[allow(dead_code)]
    pub fn get_video_tree(&self) -> Result<Vec<VideoInfo>> {
        // 获取所有未删除的条目
        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_ALL)?;

        let video_iter = stmt.query_map([], |row| {
            Ok(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
                width: row.get(12)?,
                height: row.get(13)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        // 使用 TreeBuilder 构建树形结构
        Ok(crate::services::db::tree::TreeBuilder::build_tree(videos))
    }

    /// 获取根目录下的视频（public 目录）
    pub fn get_root_videos(&self) -> Result<Vec<VideoInfo>> {
        let public_path = std::path::Path::new("public").to_string_lossy().to_string();

        let mut stmt = self.db_manager.conn.prepare(queries::SELECT_BY_PARENT)?;
        let video_iter = stmt.query_map([&public_path], |row| {
            Ok(VideoInfo {
                name: row.get(0)?,
                path: row.get(1)?,
                r#type: row.get(2)?,
                children: None,
                thumbnail: row.get(3)?,
                duration: row.get(4)?,
                size: row.get(5)?,
                resolution: row.get(6)?,
                bitrate: row.get(7)?,
                codec: row.get(8)?,
                created_at: row.get(9)?,
                subtitle: row.get(10)?,
                width: row.get(11)?,
                height: row.get(12)?,
            })
        })?;

        let mut videos: Vec<VideoInfo> = Vec::new();
        for video in video_iter {
            videos.push(video?);
        }

        Ok(videos)
    }

    /// 获取根目录下的视频（public 目录）- 支持分页
    pub fn get_root_videos_paginated(
        &self,
        page: u32,
        page_size: u32,
        search: Option<&str>,
        sort_by: Option<&str>,
        sort_order: Option<&str>,
    ) -> Result<PaginatedVideoList> {
        let public_path = std::path::Path::new("public").to_string_lossy().to_string();

        // 计算偏移量
        let offset = (page - 1) * page_size;

        // 构建查询条件
        let mut where_clause = String::from("WHERE parent_path = ?");
        let mut params: Vec<String> = vec![public_path];

        // 添加搜索条件
        if let Some(search_term) = search {
            if !search_term.is_empty() {
                where_clause.push_str(" AND (name LIKE ? OR path LIKE ?)");
                let search_pattern = format!("%{}%", search_term);
                params.push(search_pattern.clone());
                params.push(search_pattern);
            }
        }

        // 构建排序
        let order_by = match (sort_by, sort_order) {
            (Some(field), Some(order)) => {
                let valid_fields = ["name", "path", "created_at", "size", "duration"];
                if valid_fields.contains(&field) {
                    format!("ORDER BY {} {}", field, order.to_uppercase())
                } else {
                    "ORDER BY created_at DESC".to_string()
                }
            }
            (Some(field), None) => {
                let valid_fields = ["name", "path", "created_at", "size", "duration"];
                if valid_fields.contains(&field) {
                    format!("ORDER BY {} DESC", field)
                } else {
                    "ORDER BY created_at DESC".to_string()
                }
            }
            (None, Some(order)) => {
                format!("ORDER BY created_at {}", order.to_uppercase())
            }
            (None, None) => "ORDER BY created_at DESC".to_string(),
        };

        // 构建完整的查询语句
        let query = format!(
            "SELECT name, path, type, thumbnail, duration, size, resolution, bitrate, codec, created_at, subtitle, width, height
             FROM videos
             {}
             {}
             LIMIT ? OFFSET ?",
            where_clause, order_by
        );

        // 获取总数
        let count_query = format!("SELECT COUNT(*) FROM videos {}", where_clause);

        let mut count_stmt = self.db_manager.conn.prepare(&count_query)?;
        let total: u64 = match params.len() {
            1 => count_stmt.query_row([params[0].as_str()], |row| row.get(0))?,
            2 => {
                count_stmt.query_row([params[0].as_str(), params[1].as_str()], |row| row.get(0))?
            }
            3 => count_stmt.query_row(
                [params[0].as_str(), params[1].as_str(), params[2].as_str()],
                |row| row.get(0),
            )?,
            _ => count_stmt.query_row([params[0].as_str()], |row| row.get(0))?,
        };

        // 获取分页数据
        let mut stmt = self.db_manager.conn.prepare(&query)?;

        // 添加分页参数
        let page_size_str = page_size.to_string();
        let offset_str = offset.to_string();
        let mut params_with_pagination = params.clone();
        params_with_pagination.push(page_size_str);
        params_with_pagination.push(offset_str);

        let mut videos: Vec<VideoInfo> = Vec::new();

        match params_with_pagination.len() {
            3 => {
                let mut video_iter = stmt.query_map(
                    [
                        params_with_pagination[0].as_str(),
                        params_with_pagination[1].as_str(),
                        params_with_pagination[2].as_str(),
                    ],
                    |row| {
                        Ok(VideoInfo {
                            name: row.get(0)?,
                            path: row.get(1)?,
                            r#type: row.get(2)?,
                            children: None,
                            thumbnail: row.get(3)?,
                            duration: row.get(4)?,
                            size: row.get(5)?,
                            resolution: row.get(6)?,
                            bitrate: row.get(7)?,
                            codec: row.get(8)?,
                            created_at: row.get(9)?,
                            subtitle: row.get(10)?,
                            width: row.get(11)?,
                            height: row.get(12)?,
                        })
                    },
                )?;
                for video in video_iter {
                    videos.push(video?);
                }
            }
            4 => {
                let mut video_iter = stmt.query_map(
                    [
                        params_with_pagination[0].as_str(),
                        params_with_pagination[1].as_str(),
                        params_with_pagination[2].as_str(),
                        params_with_pagination[3].as_str(),
                    ],
                    |row| {
                        Ok(VideoInfo {
                            name: row.get(0)?,
                            path: row.get(1)?,
                            r#type: row.get(2)?,
                            children: None,
                            thumbnail: row.get(3)?,
                            duration: row.get(4)?,
                            size: row.get(5)?,
                            resolution: row.get(6)?,
                            bitrate: row.get(7)?,
                            codec: row.get(8)?,
                            created_at: row.get(9)?,
                            subtitle: row.get(10)?,
                            width: row.get(11)?,
                            height: row.get(12)?,
                        })
                    },
                )?;
                for video in video_iter {
                    videos.push(video?);
                }
            }
            5 => {
                let mut video_iter = stmt.query_map(
                    [
                        params_with_pagination[0].as_str(),
                        params_with_pagination[1].as_str(),
                        params_with_pagination[2].as_str(),
                        params_with_pagination[3].as_str(),
                        params_with_pagination[4].as_str(),
                    ],
                    |row| {
                        Ok(VideoInfo {
                            name: row.get(0)?,
                            path: row.get(1)?,
                            r#type: row.get(2)?,
                            children: None,
                            thumbnail: row.get(3)?,
                            duration: row.get(4)?,
                            size: row.get(5)?,
                            resolution: row.get(6)?,
                            bitrate: row.get(7)?,
                            codec: row.get(8)?,
                            created_at: row.get(9)?,
                            subtitle: row.get(10)?,
                            width: row.get(11)?,
                            height: row.get(12)?,
                        })
                    },
                )?;
                for video in video_iter {
                    videos.push(video?);
                }
            }
            _ => {
                let mut video_iter = stmt.query_map(
                    [
                        params_with_pagination[0].as_str(),
                        params_with_pagination[1].as_str(),
                    ],
                    |row| {
                        Ok(VideoInfo {
                            name: row.get(0)?,
                            path: row.get(1)?,
                            r#type: row.get(2)?,
                            children: None,
                            thumbnail: row.get(3)?,
                            duration: row.get(4)?,
                            size: row.get(5)?,
                            resolution: row.get(6)?,
                            bitrate: row.get(7)?,
                            codec: row.get(8)?,
                            created_at: row.get(9)?,
                            subtitle: row.get(10)?,
                            width: row.get(11)?,
                            height: row.get(12)?,
                        })
                    },
                )?;
                for video in video_iter {
                    videos.push(video?);
                }
            }
        }

        // 计算分页信息
        let total_pages = ((total as f64) / (page_size as f64)).ceil() as u32;
        let has_next = page < total_pages;
        let has_prev = page > 1;

        Ok(PaginatedVideoList {
            videos,
            pagination: PaginationInfo {
                page,
                page_size,
                total,
                total_pages,
                has_next,
                has_prev,
            },
        })
    }
}
