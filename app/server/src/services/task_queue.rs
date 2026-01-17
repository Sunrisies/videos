//! 异步后台任务系统
//!
//! 提供异步任务队列管理，支持：
//! - 任务优先级排队
//! - 并发数控制
//! - 任务状态监控
//! - 错误处理和重试

use log::{debug, error, info, warn};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use tokio::sync::{mpsc, Mutex, Semaphore};

use crate::services::ffmpeg::{get_ffmpeg_service, VideoMetadata};

/// 任务类型
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub enum TaskType {
    /// 生成视频缩略图
    GenerateThumbnail {
        video_path: PathBuf,
        thumbnail_path: PathBuf,
    },
    /// 提取视频元数据
    ExtractMetadata {
        video_path: PathBuf,
        thumbnail_path: PathBuf,
    },
}

/// 任务优先级
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[allow(dead_code)]
pub enum TaskPriority {
    Low = 0,
    Normal = 1,
    High = 2,
}

/// 任务状态
#[derive(Debug, Clone, PartialEq, Eq)]
#[allow(dead_code)]
pub enum TaskStatus {
    Pending,
    Running,
    Completed,
    Failed(String),
}

/// 后台任务
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct BackgroundTask {
    pub id: u64,
    pub task_type: TaskType,
    pub priority: TaskPriority,
    pub status: TaskStatus,
    pub created_at: std::time::Instant,
}

/// 任务结果
#[derive(Debug)]
#[allow(dead_code)]
pub enum TaskResult {
    ThumbnailGenerated(PathBuf),
    MetadataExtracted(VideoMetadata),
    Failed(String),
}

/// 任务执行器消息
enum ExecutorMessage {
    NewTask(BackgroundTask),
    Shutdown,
}

/// 任务队列统计信息
#[derive(Debug, Clone, Default)]
pub struct QueueStats {
    pub pending_count: usize,
    pub running_count: usize,
    pub completed_count: u64,
    pub failed_count: u64,
}

/// 后台任务队列管理器
pub struct TaskQueue {
    /// 任务发送通道
    sender: mpsc::Sender<ExecutorMessage>,
    /// 任务ID计数器
    task_id_counter: AtomicU64,
    /// 运行中的任务数
    running_count: Arc<AtomicUsize>,
    /// 完成的任务数
    completed_count: Arc<AtomicU64>,
    /// 失败的任务数
    failed_count: Arc<AtomicU64>,
    /// 待处理任务队列（用于统计）
    pending_queue: Arc<Mutex<VecDeque<BackgroundTask>>>,
}

impl TaskQueue {
    /// 创建新的任务队列
    pub fn new(max_concurrent: usize) -> Self {
        let (sender, receiver) = mpsc::channel::<ExecutorMessage>(1000);
        let running_count = Arc::new(AtomicUsize::new(0));
        let completed_count = Arc::new(AtomicU64::new(0));
        let failed_count = Arc::new(AtomicU64::new(0));
        let pending_queue = Arc::new(Mutex::new(VecDeque::new()));

        // 启动任务执行器
        Self::start_executor(
            receiver,
            max_concurrent,
            running_count.clone(),
            completed_count.clone(),
            failed_count.clone(),
            pending_queue.clone(),
        );

        Self {
            sender,
            task_id_counter: AtomicU64::new(0),
            running_count,
            completed_count,
            failed_count,
            pending_queue,
        }
    }

    /// 启动任务执行器
    fn start_executor(
        mut receiver: mpsc::Receiver<ExecutorMessage>,
        max_concurrent: usize,
        running_count: Arc<AtomicUsize>,
        completed_count: Arc<AtomicU64>,
        failed_count: Arc<AtomicU64>,
        pending_queue: Arc<Mutex<VecDeque<BackgroundTask>>>,
    ) {
        let semaphore = Arc::new(Semaphore::new(max_concurrent));

        tokio::spawn(async move {
            info!("任务执行器已启动，最大并发数: {}", max_concurrent);

            while let Some(msg) = receiver.recv().await {
                match msg {
                    ExecutorMessage::NewTask(task) => {
                        // 从待处理队列移除
                        {
                            let mut queue = pending_queue.lock().await;
                            queue.retain(|t| t.id != task.id);
                        }

                        let sem = semaphore.clone();
                        let running = running_count.clone();
                        let completed = completed_count.clone();
                        let failed = failed_count.clone();

                        // 在新的 tokio 任务中执行
                        tokio::spawn(async move {
                            // 获取信号量许可
                            let _permit = sem.acquire().await.unwrap();
                            running.fetch_add(1, Ordering::SeqCst);

                            debug!("开始执行任务 #{}: {:?}", task.id, task.task_type);

                            let result = execute_task(&task).await;

                            running.fetch_sub(1, Ordering::SeqCst);

                            match result {
                                Ok(_) => {
                                    completed.fetch_add(1, Ordering::SeqCst);
                                    debug!("任务 #{} 完成", task.id);
                                }
                                Err(e) => {
                                    failed.fetch_add(1, Ordering::SeqCst);
                                    warn!("任务 #{} 失败: {}", task.id, e);
                                }
                            }
                        });
                    }
                    ExecutorMessage::Shutdown => {
                        info!("任务执行器收到关闭信号");
                        break;
                    }
                }
            }

            info!("任务执行器已停止");
        });
    }

    /// 添加任务到队列
    pub async fn enqueue(&self, task_type: TaskType, priority: TaskPriority) -> u64 {
        let task_id = self.task_id_counter.fetch_add(1, Ordering::SeqCst);

        let task = BackgroundTask {
            id: task_id,
            task_type,
            priority,
            status: TaskStatus::Pending,
            created_at: std::time::Instant::now(),
        };

        // 添加到待处理队列（用于统计）
        {
            let mut queue = self.pending_queue.lock().await;
            queue.push_back(task.clone());
        }

        // 发送到执行器
        if let Err(e) = self.sender.send(ExecutorMessage::NewTask(task)).await {
            error!("发送任务失败: {}", e);
        }

        task_id
    }

    /// 批量添加缩略图生成任务
    #[allow(dead_code)]
    pub async fn enqueue_thumbnail_batch(&self, tasks: Vec<(PathBuf, PathBuf)>) -> Vec<u64> {
        let mut task_ids = Vec::with_capacity(tasks.len());

        for (video_path, thumbnail_path) in tasks {
            let task_type = TaskType::GenerateThumbnail {
                video_path,
                thumbnail_path,
            };
            let id = self.enqueue(task_type, TaskPriority::Normal).await;
            task_ids.push(id);
        }

        task_ids
    }

    /// 获取队列统计信息
    pub async fn get_stats(&self) -> QueueStats {
        let pending = self.pending_queue.lock().await.len();

        QueueStats {
            pending_count: pending,
            running_count: self.running_count.load(Ordering::SeqCst),
            completed_count: self.completed_count.load(Ordering::SeqCst),
            failed_count: self.failed_count.load(Ordering::SeqCst),
        }
    }

    /// 关闭任务队列
    #[allow(dead_code)]
    pub async fn shutdown(&self) {
        let _ = self.sender.send(ExecutorMessage::Shutdown).await;
    }
}

/// 执行单个任务
async fn execute_task(task: &BackgroundTask) -> std::result::Result<TaskResult, String> {
    let ffmpeg = get_ffmpeg_service();

    match &task.task_type {
        TaskType::GenerateThumbnail {
            video_path,
            thumbnail_path,
        } => {
            if ffmpeg.generate_thumbnail(video_path, thumbnail_path) {
                Ok(TaskResult::ThumbnailGenerated(thumbnail_path.clone()))
            } else {
                Err("缩略图生成失败".to_string())
            }
        }
        TaskType::ExtractMetadata {
            video_path,
            thumbnail_path,
        } => {
            let metadata = ffmpeg.extract_video_info(video_path, thumbnail_path);
            Ok(TaskResult::MetadataExtracted(metadata))
        }
    }
}

/// 全局任务队列实例
static TASK_QUEUE: std::sync::OnceLock<TaskQueue> = std::sync::OnceLock::new();

/// 获取全局任务队列实例
pub fn get_task_queue() -> &'static TaskQueue {
    TASK_QUEUE.get_or_init(|| TaskQueue::new(4))
}

/// 初始化任务队列（可自定义并发数）
pub fn init_task_queue(max_concurrent: usize) {
    let _ = TASK_QUEUE.set(TaskQueue::new(max_concurrent));
}
