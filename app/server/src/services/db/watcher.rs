use notify::{Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::mpsc;

use crate::services::db::connection::VideoDbManager;
use crate::services::db::sync::DirectorySync;

/// 文件监听器，用于自动同步数据库
pub struct FileWatcher {
    db_manager: Arc<Mutex<VideoDbManager>>,
    watcher: Option<RecommendedWatcher>,
    tx: Option<mpsc::Sender<Event>>,
    is_watching: Arc<Mutex<bool>>,
}

impl FileWatcher {
    /// 创建新的文件监听器
    pub fn new(db_manager: Arc<Mutex<VideoDbManager>>) -> Self {
        Self {
            db_manager,
            watcher: None,
            tx: None,
            is_watching: Arc::new(Mutex::new(false)),
        }
    }

    /// 启动文件监听（支持多个路径）
    pub fn start(&mut self, paths: &[String]) -> Result<(), String> {
        let is_watching = self.is_watching.clone();

        // 检查是否已经在监听
        {
            let guard = is_watching.lock().unwrap();
            if *guard {
                return Err("文件监听器已经在运行".to_string());
            }
        }

        // 验证所有路径都存在
        for path_str in paths {
            let path = PathBuf::from(path_str);
            if !path.exists() {
                return Err(format!("路径不存在: {}", path.display()));
            }
        }

        // 创建异步通道
        let (tx, mut rx) = mpsc::channel::<Event>(100);
        self.tx = Some(tx.clone());

        // 克隆数据库管理器用于回调
        let db_manager_clone = self.db_manager.clone();
        let is_watching_clone = is_watching.clone();
        let paths_clone = paths.to_vec();

        // 启动同步任务
        tokio::spawn(async move {
            let mut last_sync = std::time::Instant::now();
            let sync_interval = Duration::from_secs(5); // 5秒防抖

            while let Some(event) = rx.recv().await {
                // 检查是否应该停止
                {
                    let guard = is_watching_clone.lock().unwrap();
                    if !*guard {
                        break;
                    }
                }

                // 防抖处理：避免频繁同步
                let now = std::time::Instant::now();
                if now.duration_since(last_sync) < sync_interval {
                    continue;
                }
                last_sync = now;

                println!("检测到文件变化: {:?}", event);

                // 执行同步
                let db_manager = db_manager_clone.lock().unwrap();
                let sync = DirectorySync::new(&db_manager);

                match sync.initialize_from_directory(&paths_clone, false) {
                    Ok(_) => println!("自动同步完成"),
                    Err(e) => eprintln!("自动同步失败: {}", e),
                }
            }

            println!("文件监听任务已停止");
        });

        // 创建监听器并监听所有路径
        let tx_clone = tx.clone();
        let mut watcher = RecommendedWatcher::new(
            move |res: Result<Event, notify::Error>| {
                if let Ok(event) = res {
                    // 过滤掉元数据变化，只关注内容变化
                    if is_content_change(&event) {
                        let tx = tx_clone.clone();
                        tokio::spawn(async move {
                            let _ = tx.send(event).await;
                        });
                    }
                }
            },
            notify::Config::default().with_poll_interval(Duration::from_millis(500)),
        )
        .map_err(|e| format!("创建监听器失败: {}", e))?;

        // 为每个路径开始监听
        for path_str in paths {
            let path = PathBuf::from(path_str);
            watcher
                .watch(&path, RecursiveMode::Recursive)
                .map_err(|e| format!("开始监听失败 {}: {}", path.display(), e))?;
            println!("文件监听器已启动，监控路径: {}", path.display());
        }

        self.watcher = Some(watcher);

        // 标记为正在监听
        {
            let mut guard = self.is_watching.lock().unwrap();
            *guard = true;
        }

        Ok(())
    }

    /// 停止文件监听
    pub fn stop(&mut self) -> Result<(), String> {
        {
            let mut guard = self.is_watching.lock().unwrap();
            *guard = false;
        }

        // 清理监听器
        self.watcher = None;
        self.tx = None;

        println!("文件监听器已停止");
        Ok(())
    }

    /// 检查监听器状态
    pub fn is_watching(&self) -> bool {
        let guard = self.is_watching.lock().unwrap();
        *guard
    }
}

/// 判断是否为内容变化（而非元数据变化）
fn is_content_change(event: &Event) -> bool {
    // 过滤掉仅元数据变化的事件
    match event.kind {
        notify::EventKind::Create(_)
        | notify::EventKind::Modify(_)
        | notify::EventKind::Remove(_) => {
            // 检查路径是否为视频相关文件
            for path in &event.paths {
                if is_video_related_path(path) {
                    return true;
                }
            }
            false
        }
        _ => false,
    }
}

/// 判断路径是否为视频相关文件
fn is_video_related_path(path: &Path) -> bool {
    if path.is_dir() {
        return true; // 目录变化也需要关注
    }

    if let Some(ext) = path.extension() {
        let ext_str = ext.to_string_lossy().to_lowercase();
        matches!(
            ext_str.as_str(),
            "mp4" | "vtt" | "srt" | "jpg" | "png" | "gif"
        )
    } else {
        false
    }
}
