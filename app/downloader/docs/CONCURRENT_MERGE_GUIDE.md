# 并发FFmpeg合并使用指南

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 使用新的线程安全合并器

#### 方法一：直接使用新模块

```python
from app.downloader.core.thread_safe_merge import ThreadSafeFileMerger
from app.downloader.core.config import DownloadConfig

# 创建配置
config = DownloadConfig()
config.temp_dir = "./temp"
config.merge_timeout = 600  # 10分钟超时

# 创建合并器
merger = ThreadSafeFileMerger(config)

# 合并文件
success = merger.merge_files(
    file_list=["segment1.ts", "segment2.ts", "segment3.ts"],
    output_file="./output/video.mp4",
    task_name="my_video"
)
```

#### 方法二：使用兼容性包装器（推荐）

只需修改导入，无需改动其他代码：

```python
# 原代码
# from .merge_files import FileMerger

# 新代码 - 只需修改这一行
from .thread_safe_merge import CompatibleFileMerger as FileMerger

# 其余代码完全不变
merger = FileMerger(config, logger, quiet_mode=False)
success = merger.merge_files(file_list, output_file, temp_dir)
```

### 3. 在并发下载中使用

```python
from concurrent.futures import ThreadPoolExecutor
from app.downloader.core.advanced_downloader import StreamDownloadManager
from app.downloader.core.thread_safe_merge import CompatibleFileMerger

# 创建下载器
config = DownloadConfig()
config.num_threads = 3  # 下载并发数

manager = StreamDownloadManager(config)

# 替换原有的合并器
manager.file_merger = CompatibleFileMerger(
    config=config,
    logger=manager.logger,
    quiet_mode=manager._quiet_mode
)

# 现在可以安全地并发下载和合并
tasks = [...]  # 任务列表
results = manager.download_batch_tasks(tasks, max_concurrent=3)
```

## 关键改进说明

### 1. 隔离工作空间

**问题**：所有任务共享相同的临时目录和文件名

**解决**：每个任务创建唯一的工作空间

```python
# 旧代码 - 问题
list_file = os.path.join(temp_dir, 'file_list.txt')  # 所有任务共享

# 新代码 - 解决
workspace = IsolatedMergeWorkspace(base_temp_dir, task_name)
list_file = workspace.file_list_path  # 唯一文件名
```

### 2. 线程安全

**问题**：共享状态导致竞态条件

**解决**：每个合并器实例独立，使用锁保护

```python
class ThreadSafeFileMerger:
    def __init__(self, config, logger):
        self._lock = threading.Lock()  # 保护实例状态
        self._stop_flag = False  # 每个实例独立
    
    def merge_files(self, file_list, output_file, task_name):
        with self._lock:  # 确保线程安全
            # 执行合并
            pass
```

### 3. 完整的错误处理

**问题**：错误处理不完整，导致资源泄漏

**解决**：使用上下文管理器确保清理

```python
# 使用上下文管理器自动清理
with IsolatedMergeWorkspace(base_temp_dir, task_name) as workspace:
    # 执行合并
    success = merger.merge_files(file_list, output_file, workspace)
# 自动清理工作空间
```

### 4. 超时控制

**问题**：FFmpeg可能无限挂起

**解决**：设置超时

```python
result = subprocess.run(
    cmd,
    timeout=600,  # 10分钟超时
    check=False
)
```

## 配置建议

### 并发配置

```python
config = DownloadConfig()

# 下载并发数（通常可以较高）
config.num_threads = 4

# 合并并发数（建议较低，避免磁盘I/O竞争）
# 在 DownloadManager 中使用 max_concurrent 参数控制
# 例如：manager.download_batch_tasks(tasks, max_concurrent=2)
```

### 临时目录配置

```python
# 使用独立的临时目录
config.temp_dir = "/path/to/temp/video_downloader"

# 确保有足够的磁盘空间
# 每个任务需要的空间 = 所有TS文件大小 + 临时输出文件
```

### 超时配置

```python
# 下载超时（秒）
config.connect_timeout = 30
config.read_timeout = 300

# 合并超时（秒）
config.merge_timeout = 600  # 10分钟
```

## 调试技巧

### 1. 启用详细日志

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'
)

# 在合并器中会输出详细信息
# [task_id] 创建隔离工作空间
# [task_id] 文件列表创建成功
# [task_id] 执行FFmpeg
# [task_id] 合并成功
```

### 2. 检查工作空间

```python
# 手动检查工作空间
import os

workspace_path = "./temp/merge_workspaces"
if os.path.exists(workspace_path):
    for item in os.listdir(workspace_path):
        print(f"工作空间: {item}")
        # 每个子目录对应一个任务
```

### 3. 验证输出

```python
def verify_output(output_file: str) -> bool:
    """验证输出文件"""
    if not os.path.exists(output_file):
        print(f"❌ 文件不存在: {output_file}")
        return False
    
    size = os.path.getsize(output_file)
    if size == 0:
        print(f"❌ 文件为空: {output_file}")
        return False
    
    print(f"✅ 文件有效: {output_file} ({size:,} bytes)")
    return True
```

## 常见问题

### Q1: 仍然只有第一个任务成功？

**可能原因**：
1. 临时目录权限问题
2. 磁盘空间不足
3. FFmpeg版本问题

**解决方案**：
```python
# 检查权限
import os
temp_dir = "./temp"
os.makedirs(temp_dir, exist_ok=True)
print(f"临时目录权限: {oct(os.stat(temp_dir).st_mode)}")

# 检查磁盘空间
import shutil
total, used, free = shutil.disk_usage(temp_dir)
print(f"可用空间: {free // (1024**3)} GB")
```

### Q2: 内存使用过高？

**解决方案**：
```python
# 降低并发数
max_concurrent = 1  # 串行执行

# 使用二进制合并（不使用FFmpeg）
merger = ThreadSafeFileMerger(config)
success = merger.merge_files_binary(files, output, task_name)
```

### Q3: 合并速度慢？

**优化建议**：
1. 使用SSD存储临时文件
2. 增加合并并发数（但不要超过CPU核心数）
3. 使用更快的FFmpeg版本（如编译优化版本）

## 性能优化

### 1. 使用内存盘（RAM Disk）

```bash
# Linux/Mac
mkdir -p /tmp/ramdisk
sudo mount -t tmpfs -o size=2G tmpfs /tmp/ramdisk

# Windows (使用RAMDisk软件)
```

```python
config.temp_dir = "/tmp/ramdisk/video_downloader"
```

### 2. 预分配磁盘空间

```python
def preallocate_file(filepath: str, size: int):
    """预分配文件空间，减少碎片"""
    with open(filepath, 'wb') as f:
        f.seek(size - 1)
        f.write(b'\0')
```

### 3. 使用更快的FFmpeg参数

```python
# 原命令
cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, 
       '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', output_file]

# 优化命令（添加线程数）
cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file,
       '-c', 'copy', '-bsf:a', 'aac_adtstoasc',
       '-threads', '4',  # 使用4个线程
       '-y', output_file]
```

## 测试

### 运行示例代码

```bash
# 运行并发合并示例
python app/downloader/examples/concurrent_merge_example.py
```

### 单元测试

```python
import unittest
from app.downloader.core.thread_safe_merge import ThreadSafeFileMerger
from app.downloader.core.config import DownloadConfig

class TestConcurrentMerge(unittest.TestCase):
    def test_isolated_workspace(self):
        """测试隔离工作空间"""
        config = DownloadConfig()
        merger = ThreadSafeFileMerger(config)
        
        # 创建测试文件
        test_files = ["test1.ts", "test2.ts"]
        for f in test_files:
            with open(f, 'wb') as file:
                file.write(b'test data')
        
        # 执行合并
        success = merger.merge_files(
            test_files,
            "test_output.mp4",
            "test_task"
        )
        
        # 清理
        for f in test_files:
            if os.path.exists(f):
                os.remove(f)
        
        self.assertTrue(success)
```

## 部署建议

### 1. Docker部署

```dockerfile
FROM python:3.9-slim

# 安装FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制代码
COPY . /app
WORKDIR /app

# 创建临时目录
RUN mkdir -p /tmp/video_downloader

CMD ["python", "app/downloader/examples/concurrent_merge_example.py"]
```

### 2. 系统服务配置

```ini
# /etc/systemd/system/video-downloader.service
[Unit]
Description=Video Downloader Service
After=network.target

[Service]
Type=simple
User=video
WorkingDirectory=/opt/video-downloader
ExecStart=/usr/bin/python3 -m app.downloader.cli.advanced_cli
Environment=TEMP_DIR=/tmp/video_downloader
Environment=MAX_CONCURRENT=2
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 总结

使用新的线程安全合并器可以解决99%的并发合并问题。关键要点：

1. ✅ **隔离工作空间**：每个任务独立临时目录
2. ✅ **线程安全**：每个合并器实例独立，使用锁保护
3. ✅ **完整清理**：使用上下文管理器确保资源释放
4. ✅ **超时控制**：防止FFmpeg无限挂起
5. ✅ **错误处理**：完整的异常捕获和日志记录

如果仍有问题，请检查：
- 磁盘空间和权限
- FFmpeg版本和配置
- 系统资源限制（ulimit）
- 网络连接稳定性