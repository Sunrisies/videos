# FFmpeg 并发合并视频问题深度分析与解决方案

## 问题概述

在多线程视频下载和合并场景中，只有第一个视频能成功合并，后续合并失败。这是一个典型的并发资源竞争问题。

## 根本原因分析

### 1. **文件锁定冲突**
```python
# 问题代码示例
def merge_files(self, file_list, output_file, temp_dir):
    list_file = os.path.join(temp_dir, 'file_list.txt')  # ⚠️ 固定文件名
    # 多个并发任务使用相同的临时文件名，导致冲突
```

**问题表现：**
- 所有并发任务共享相同的临时文件名 `file_list.txt`
- 第一个任务创建文件后，第二个任务会覆盖它
- FFmpeg 读取时可能文件内容不完整或已被删除

### 2. **临时目录污染**
```python
# 问题代码
task_temp_dir = os.path.join(self.config.temp_dir, task.name)
# 如果多个任务使用相同名称，会共享临时目录
```

**问题表现：**
- TS 文件互相覆盖
- 清理时误删其他任务的文件
- 文件列表混乱

### 3. **FFmpeg 进程资源竞争**
```rust
// Rust 服务中的问题
pub struct FFmpegService {
    semaphore: Arc<Semaphore>,  // 限制并发数，但未隔离工作空间
}
```

**问题表现：**
- 多个 FFmpeg 进程同时读写相同路径
- 磁盘 I/O 竞争导致读取失败
- 临时文件被提前删除

### 4. **Python GIL 与线程安全**
```python
class StreamDownloadManager:
    def __init__(self):
        self.lock = threading.Lock()  # ⚠️ 只保护部分操作
        self.file_merger = FileMerger()  # 共享状态
```

**问题表现：**
- `FileMerger` 实例被共享，状态混乱
- 静默模式标志被并发修改
- 进度显示错乱

## 解决方案

### 1. **完全隔离的临时工作空间**

```python
import os
import uuid
from pathlib import Path

class IsolatedTaskWorkspace:
    """为每个任务创建完全隔离的工作空间"""
    
    def __init__(self, base_temp_dir: str, task_name: str):
        # 使用 UUID 确保绝对唯一性
        self.task_id = f"{task_name}_{uuid.uuid4().hex[:8]}"
        self.workspace = os.path.join(base_temp_dir, self.task_id)
        
        # 创建隔离目录
        os.makedirs(self.workspace, exist_ok=True)
        
        # 生成唯一文件名
        self.file_list_path = os.path.join(self.workspace, f"file_list_{self.task_id}.txt")
        self.output_temp = os.path.join(self.workspace, f"output_{self.task_id}.mp4")
    
    def cleanup(self):
        """安全清理，只删除自己的文件"""
        try:
            if os.path.exists(self.workspace):
                import shutil
                shutil.rmtree(self.workspace)
        except Exception as e:
            print(f"清理失败: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
```

### 2. **线程安全的文件合并器**

```python
import threading
import subprocess
from typing import List, Optional
import logging

class ThreadSafeFileMerger:
    """线程安全的文件合并器，每个实例完全独立"""
    
    def __init__(self, task_id: str, logger: Optional[logging.Logger] = None):
        self.task_id = task_id
        self.logger = logger
        self._lock = threading.Lock()  # 保护实例状态
        self._stop_flag = False
        
    def merge_with_ffmpeg(
        self, 
        file_list: List[str], 
        output_file: str,
        workspace: IsolatedTaskWorkspace
    ) -> bool:
        """使用完全隔离的临时文件进行合并"""
        
        with self._lock:
            if self._stop_flag:
                return False
            
            try:
                # 1. 创建唯一的文件列表
                self._create_file_list(file_list, workspace.file_list_path)
                
                # 2. 构建 FFmpeg 命令
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', workspace.file_list_path,
                    '-c', 'copy',
                    '-bsf:a', 'aac_adtstoasc',
                    '-y',  # 覆盖输出文件
                    output_file
                ]
                
                # 3. 执行合并（使用独立进程）
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,  # 5分钟超时
                    check=False
                )
                
                if result.returncode != 0:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    if self.logger:
                        self.logger.error(f"FFmpeg 合并失败: {stderr}")
                    return False
                
                # 4. 验证输出文件
                if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                    if self.logger:
                        self.logger.error("输出文件不存在或为空")
                    return False
                
                return True
                
            except subprocess.TimeoutExpired:
                if self.logger:
                    self.logger.error("FFmpeg 执行超时")
                return False
            except Exception as e:
                if self.logger:
                    self.logger.error(f"合并异常: {e}")
                return False
    
    def _create_file_list(self, file_list: List[str], list_file_path: str):
        """创建文件列表，使用绝对路径"""
        with open(list_file_path, 'w', encoding='utf-8') as f:
            for file_path in file_list:
                abs_path = os.path.abspath(file_path)
                # 转义路径中的特殊字符
                escaped_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
    
    def stop(self):
        """停止当前合并"""
        self._stop_flag = True
```

### 3. **增强的下载管理器**

```python
import os
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

class EnhancedDownloadManager:
    """增强的下载管理器，支持完全隔离的并发操作"""
    
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._stop_flag = False
        self._active_tasks = {}  # task_id -> workspace
        
    def download_task(self, task) -> bool:
        """下载单个任务，使用完全隔离的工作空间"""
        
        # 1. 创建隔离工作空间
        workspace = IsolatedTaskWorkspace(
            base_temp_dir=self.config.temp_dir,
            task_name=task.name
        )
        
        # 记录活跃任务
        task_id = workspace.task_id
        self._active_tasks[task_id] = workspace
        
        try:
            self.logger.info(f"开始任务 {task.name} (ID: {task_id})")
            
            # 2. 解析 M3U8
            parser = M3U8Parser(verify_ssl=self.config.verify_ssl)
            ts_files, parse_info = parser.parse_m3u8(task.url, self.config.headers)
            
            if not ts_files:
                self.logger.error(f"任务 {task.name}: 未找到TS文件")
                return False
            
            # 3. 下载 TS 文件到隔离目录
            downloaded_files = self._download_segments(
                ts_files, workspace.workspace, task.name
            )
            
            if not downloaded_files:
                self.logger.error(f"任务 {task.name}: 下载失败")
                return False
            
            # 4. 创建输出目录
            os.makedirs(task.output_dir, exist_ok=True)
            output_file = os.path.join(task.output_dir, f"{task.name}.mp4")
            
            # 5. 使用隔离的合并器
            merger = ThreadSafeFileMerger(task_id, self.logger)
            success = merger.merge_with_ffmpeg(
                downloaded_files,
                output_file,
                workspace
            )
            
            if success:
                self.logger.info(f"任务 {task.name} 完成: {output_file}")
                return True
            else:
                self.logger.error(f"任务 {task.name} 合并失败")
                return False
                
        except Exception as e:
            self.logger.error(f"任务 {task.name} 异常: {e}")
            return False
        finally:
            # 6. 清理隔离空间
            workspace.cleanup()
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
    
    def _download_segments(self, ts_files: List[str], temp_dir: str, task_name: str) -> List[str]:
        """下载所有 TS 片段，返回本地文件路径列表"""
        local_files = []
        
        with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
            futures = {}
            
            for i, url in enumerate(ts_files):
                if self._stop_flag:
                    break
                
                filename = f"segment_{i:05d}.ts"
                filepath = os.path.join(temp_dir, filename)
                
                future = executor.submit(
                    self._download_single_segment,
                    url,
                    filepath,
                    task_name
                )
                futures[future] = filepath
            
            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    success = future.result()
                    if success:
                        local_files.append(filepath)
                except Exception as e:
                    self.logger.error(f"下载片段失败 {filepath}: {e}")
        
        # 按文件名排序
        return sorted(local_files)
    
    def _download_single_segment(self, url: str, filepath: str, task_name: str) -> bool:
        """下载单个片段"""
        if os.path.exists(filepath):
            return True
        
        try:
            response = self.config.session.get(
                url,
                timeout=(self.config.connect_timeout, self.config.read_timeout),
                stream=True
            )
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                    if self._stop_flag:
                        return False
                    if chunk:
                        f.write(chunk)
            
            return True
        except Exception as e:
            self.logger.error(f"下载失败 {url}: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return False
    
    def stop(self):
        """停止所有任务"""
        self._stop_flag = True
        # 清理所有活跃的工作空间
        for workspace in self._active_tasks.values():
            workspace.cleanup()
```

### 4. **Rust 服务层改进**

```rust
//! 改进的 FFmpeg 服务，支持工作空间隔离

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;
use tokio::sync::Semaphore;
use uuid::Uuid;

/// 隔离的工作空间
pub struct IsolatedWorkspace {
    pub id: String,
    pub path: PathBuf,
    pub file_list_path: PathBuf,
}

impl IsolatedWorkspace {
    pub fn new(base_dir: &Path, task_name: &str) -> Self {
        let id = format!("{}_{}", task_name, Uuid::new_v4().as_simple().to_string()[..8]);
        let path = base_dir.join(&id);
        let file_list_path = path.join(format!("file_list_{}.txt", id));
        
        // 创建目录
        std::fs::create_dir_all(&path).ok();
        
        Self {
            id,
            path,
            file_list_path,
        }
    }
    
    pub fn cleanup(&self) {
        if self.path.exists() {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }
}

/// 改进的 FFmpeg 服务
pub struct FFmpegService {
    config: FFmpegConfig,
    semaphore: Arc<Semaphore>,
    base_workspace: PathBuf,
}

impl FFmpegService {
    pub fn new(config: FFmpegConfig, base_workspace: PathBuf) -> Self {
        let semaphore = Arc::new(Semaphore::new(config.max_concurrent));
        
        // 确保基础目录存在
        std::fs::create_dir_all(&base_workspace).ok();
        
        Self {
            config,
            semaphore,
            base_workspace,
        }
    }
    
    /// 合并 M3U8 到 MP4，使用隔离工作空间
    pub async fn merge_m3u8_isolated(
        &self,
        m3u8_path: &Path,
        output_path: &Path,
        task_name: &str,
    ) -> Result<PathBuf, String> {
        let _permit = self.semaphore.acquire().await.unwrap();
        
        // 创建隔离工作空间
        let workspace = IsolatedWorkspace::new(&self.base_workspace, task_name);
        
        // 创建文件列表
        let file_list_content = format!("file '{}'\n", m3u8_path.display());
        std::fs::write(&workspace.file_list_path, file_list_content)
            .map_err(|e| format!("无法创建文件列表: {}", e))?;
        
        // 执行 FFmpeg
        let output = Command::new("ffmpeg")
            .args([
                "-f", "concat",
                "-safe", "0",
                "-i", workspace.file_list_path.to_string_lossy().as_ref(),
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-y",
                output_path.to_string_lossy().as_ref(),
            ])
            .output()
            .map_err(|e| format!("FFmpeg 执行失败: {}", e))?;
        
        // 清理工作空间
        workspace.cleanup();
        
        if output.status.success() && output_path.exists() {
            Ok(output_path.to_path_buf())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            Err(format!("合并失败: {}", stderr))
        }
    }
}
```

### 5. **配置最佳实践**

```python
# config.py 增强版

class DownloadConfig:
    def __init__(self):
        # 并发控制
        self.max_concurrent_downloads = 3  # 下载并发
        self.max_concurrent_merges = 2     # 合并并发（通常更少）
        
        # 隔离配置
        self.use_isolated_workspaces = True
        self.workspace_base = os.path.join(os.tempdir(), "video_downloader")
        
        # 超时配置
        self.download_timeout = 300       # 5分钟
        self.merge_timeout = 600          # 10分钟
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 5
        
        # 资源清理
        self.auto_cleanup = True
        self.cleanup_delay = 60           # 完成后60秒清理
```

## 完整的使用示例

```python
import logging
from concurrent.futures import ThreadPoolExecutor

def main():
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 配置
    config = DownloadConfig()
    config.max_concurrent_downloads = 3
    config.max_concurrent_merges = 2
    
    # 创建管理器
    manager = EnhancedDownloadManager(config)
    
    # 任务列表
    tasks = [
        DownloadTask("video1", "https://example.com/video1.m3u8", "/output/video1"),
        DownloadTask("video2", "https://example.com/video2.m3u8", "/output/video2"),
        DownloadTask("video3", "https://example.com/video3.m3u8", "/output/video3"),
    ]
    
    # 使用线程池控制并发
    results = {}
    with ThreadPoolExecutor(max_workers=config.max_concurrent_downloads) as executor:
        futures = {executor.submit(manager.download_task, task): task.name for task in tasks}
        
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                success = future.result()
                results[task_name] = success
                print(f"任务 {task_name}: {'成功' if success else '失败'}")
            except Exception as e:
                results[task_name] = False
                print(f"任务 {task_name} 异常: {e}")
    
    # 总结
    success_count = sum(1 for v in results.values() if v)
    print(f"\n完成: {success_count}/{len(tasks)} 成功")
    
    return all(results.values())

if __name__ == "__main__":
    main()
```

## 关键要点总结

### ✅ 必须做的
1. **完全隔离工作空间**：每个任务使用唯一临时目录
2. **唯一文件名**：避免任何文件名冲突
3. **线程安全**：每个合并器实例独立，不共享状态
4. **超时控制**：防止 FFmpeg 挂起
5. **清理机制**：确保临时文件被正确清理

### ❌ 避免的
1. 共享临时文件或目录
2. 共享可变状态
3. 使用固定文件名
4. 不清理临时文件
5. 忽略错误处理

### 🔧 调试技巧
```python
# 添加详细日志
def merge_with_debug(...):
    print(f"[{task_id}] 开始合并")
    print(f"[{task_id}] 文件列表: {file_list}")
    print(f"[{task_id}] 工作空间: {workspace.workspace}")
    print(f"[{task_id}] 输出文件: {output_file}")
    
    # 执行前检查
    for f in file_list:
        if not os.path.exists(f):
            print(f"[{task_id}] 错误: 文件不存在 {f}")
            return False
    
    # 执行 FFmpeg...
```

这个解决方案确保了每个并发任务的完全隔离，消除了资源竞争，是生产环境就绪的实现。