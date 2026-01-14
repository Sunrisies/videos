//! 任务队列相关的 API 处理器

use axum::Json;
use serde::Serialize;

use crate::services::get_task_queue;

/// 任务队列状态响应
#[derive(Serialize)]
pub struct TaskQueueStatusResponse {
    pub pending: usize,
    pub running: usize,
    pub completed: u64,
    pub failed: u64,
}

/// 获取任务队列状态
pub async fn get_task_queue_status() -> Json<TaskQueueStatusResponse> {
    let queue = get_task_queue();
    let stats = queue.get_stats().await;

    Json(TaskQueueStatusResponse {
        pending: stats.pending_count,
        running: stats.running_count,
        completed: stats.completed_count,
        failed: stats.failed_count,
    })
}
