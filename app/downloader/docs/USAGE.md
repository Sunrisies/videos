# M3U8 Downloader Pro 使用指南

## 🚀 新功能特性 (v2.1.0+)

### 1. 流式下载和实时进度显示
- **逐个下载**：每个任务内部的TS文件逐个下载，避免同时启动过多线程
- **实时进度**：每个文件的下载进度实时显示百分比和字节数
- **剩余数量**：实时显示剩余文件数量
- **清晰状态**：显示下载中、完成、失败等状态

### 2. JSON配置文件支持
支持从JSON文件批量下载多个视频，配置格式如下：

```json
[
    {
        "name": "video1",
        "url": "https://example.com/video1.m3u8",
        "output_dir": "./output/video1",
        "params": {
            "quality": "1080p",
            "language": "chinese",
            "priority": 1
        }
    },
    {
        "name": "video2",
        "url": "https://example.com/video2.m3u8",
        "output_dir": "./output/video2",
        "params": {
            "quality": "720p",
            "language": "english"
        }
    }
]
```

### 3. 可控并发下载
- **多任务并发**：支持同时下载多个任务（默认3个，可自定义）
- **任务独立**：每个任务独立管理，互不影响
- **资源优化**：避免同时启动过多线程导致资源耗尽

### 4. 优化的目录结构
```
temp/
├── video1/           # 每个任务独立子目录
│   ├── seg-001.ts
│   ├── seg-002.ts
│   └── ...
├── video2/
│   ├── seg-001.ts
│   └── ...
└── ...

output/
├── video1/
│   └── video1.mp4    # 合并后的最终文件
├── video2/
│   └── video2.mp4
└── ...
```

### 5. 自动清理
- 下载完成后自动清理临时子目录
- 保持文件系统整洁

## 📖 使用方法

### 方式一：命令行使用

#### 1. 单个下载
```bash
# 基本使用
python -m m3u8.advanced_cli https://example.com/video.m3u8

# 指定输出文件
python -m m3u8.advanced_cli https://example.com/video.m3u8 -o myvideo.mp4

# 使用快速配置
python -m m3u8.advanced_cli https://example.com/video.m3u8 --profile fast

# 自定义线程数
python -m m3u8.advanced_cli https://example.com/video.m3u8 --threads 16
```

#### 2. JSON批量下载
```bash
# 批量下载 (默认3个并发)
python -m m3u8.advanced_cli --json tasks.json

# 指定输出目录
python -m m3u8.advanced_cli --json tasks.json --output-dir ./videos

# 使用配置模板
python -m m3u8.advanced_cli --json tasks.json --profile fast

# 自定义并发数 (例如4个)
python -m m3u8.advanced_cli --json tasks.json --max-concurrent 4

# 组合使用
python -m m3u8.advanced_cli --json tasks.json --profile fast --max-concurrent 4
```

#### 3. 交互模式
```bash
python -m m3u8.advanced_cli -i
```

### 方式二：编程使用

#### 1. 单个任务下载
```python
from m3u8.advanced_downloader import AdvancedM3U8Downloader
from m3u8.config import ConfigTemplates

# 创建下载器
config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

# 下载单个视频
success = downloader.download_single(
    name="my_video",
    url="https://example.com/video.m3u8",
    output_dir="./output/my_video",
    params={"quality": "1080p"}
)
```

#### 2. JSON批量下载
```python
from m3u8.advanced_downloader import AdvancedM3U8Downloader
from m3u8.config import ConfigTemplates

config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

# 从JSON文件下载 (默认3个并发)
success = downloader.download_from_json(
    json_file="tasks.json",
    base_output_dir="./output"
)

# 自定义并发数
success = downloader.download_from_json(
    json_file="tasks.json",
    base_output_dir="./output",
    max_concurrent=4
)
```

#### 3. 自定义任务列表
```python
from m3u8.advanced_downloader import AdvancedM3U8Downloader, DownloadTask
from m3u8.config import DownloadConfig

# 创建配置
config = DownloadConfig(
    num_threads=8,
    max_retries=5,
    retry_delay=2.0
)

# 创建任务列表
tasks = [
    DownloadTask("video1", "https://example.com/v1.m3u8", "./output/v1"),
    DownloadTask("video2", "https://example.com/v2.m3u8", "./output/v2"),
    DownloadTask("video3", "https://example.com/v3.m3u8", "./output/v3"),
]

# 下载 (3个并发)
downloader = AdvancedM3U8Downloader(config)
results = downloader.manager.download_batch_tasks(tasks, max_concurrent=3)
```

### 方式三：创建JSON配置文件

#### 交互式创建
```bash
python -m m3u8.advanced_cli -i
# 选择 "3. 创建JSON配置文件"
```

#### 手动创建
创建 `tasks.json` 文件：
```json
[
    {
        "name": "lesson1",
        "url": "https://course.com/lesson1.m3u8",
        "output_dir": "./courses/lesson1",
        "params": {
            "quality": "1080p",
            "chapter": "第一章"
        }
    },
    {
        "name": "lesson2",
        "url": "https://course.com/lesson2.m3u8",
        "output_dir": "./courses/lesson2",
        "params": {
            "quality": "720p",
            "chapter": "第二章"
        }
    }
]
```

## ⚙️ 配置参数

### DownloadConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `num_threads` | int | CPU核心数*2 | 下载线程数 |
| `connect_timeout` | int | 10 | 连接超时(秒) |
| `read_timeout` | int | 30 | 读取超时(秒) |
| `max_retries` | int | 3 | 最大重试次数 |
| `retry_delay` | float | 1.0 | 重试延迟(秒) |
| `chunk_size` | int | 8192 | 下载块大小(字节) |
| `buffer_size` | int | 1048576 | 文件缓冲区大小(字节) |
| `temp_dir` | str | "temp" | 临时目录 |
| `output_dir` | str | "." | 输出目录 |
| `verify_ssl` | bool | False | SSL验证 |
| `show_progress` | bool | True | 显示进度条 |
| `enable_logging` | bool | True | 启用日志 |

### 配置模板

- **快速模式**: `ConfigTemplates.fast()` - 高并发，适合带宽充足
- **稳定模式**: `ConfigTemplates.stable()` - 平衡配置，推荐使用
- **低带宽模式**: `ConfigTemplates.low_bandwidth()` - 低并发，适合网络差

## 🎯 进度显示说明

### 流式下载显示 (带剩余数量)
```
开始任务: video1
URL: https://example.com/video1.m3u8
输出目录: ./output/video1

找到 141 个TS文件
📺 分辨率: 1920x1080
💾 带宽: 5000000

⬇️  开始下载 141 个文件...

[1/141] 剩余: 140 → video1: seg-001.ts [100.0%] 100000/100000 bytes
✅ 成功! 剩余: 139

[2/141] 剩余: 138 → video1: seg-002.ts [100.0%] 100000/100000 bytes
✅ 成功! 剩余: 137

[3/141] 剩余: 136 → video1: seg-003.ts [100.0%] 100000/100000 bytes
✅ 成功! 剩余: 135
...
📊 下载结果: 141 成功, 0 失败
🔄 开始合并文件到: ./output/video1
✅ 任务 video1 完成！输出: ./output/video1/video1.mp4
🗑️  已清理临时目录: temp/video1
```

### 批量下载显示 (并发控制)
```
🚀 开始批量处理 3 个任务
📊 最大并发数: 3

============================================================
开始任务: video1
URL: https://example.com/video1.m3u8
输出目录: ./output/video1
============================================================

找到 50 个TS文件
📺 分辨率: 1920x1080
💾 带宽: 5000000

⬇️  开始下载 50 个文件...

[1/50] 剩余: 49 → video1: seg-001.ts [100.0%] 100000/100000 bytes
✅ 成功! 剩余: 48
...
📊 下载结果: 50 成功, 0 失败
🔄 开始合并文件到: ./output/video1
✅ 任务 video1 完成！输出: ./output/video1/video1.mp4
🗑️  已清理临时目录: temp/video1

📊 批量下载完成
✅ 成功: 3/3
❌ 失败: 0
```

## 🔧 高级功能

### 1. 并发控制说明
- **任务并发**: 多个任务可以同时下载（通过 `--max-concurrent` 控制）
- **文件串行**: 每个任务内部的TS文件逐个下载
- **资源优化**: 避免同时启动过多线程

**示例**: 3个任务并发，每个任务下载141个TS文件
```
任务1: seg-001.ts → seg-002.ts → ... → seg-141.ts (串行)
任务2: seg-001.ts → seg-002.ts → ... → seg-141.ts (串行)  
任务3: seg-001.ts → seg-002.ts → ... → seg-141.ts (串行)

三个任务同时进行 (并发)
```

### 2. 断点续传
自动检查已下载的文件，跳过已完成的片段。

### 3. 错误重试
- 自动重试失败的下载
- 指数退避策略
- 详细的错误日志

### 4. 信号处理
支持 `Ctrl+C` 中断下载，会保存已下载的内容。

### 5. 日志记录
所有操作记录到 `download.log` 文件。

## 📝 常见问题

### Q: 如何解决下载速度慢？
A: 使用 `--profile fast` 或增加线程数 `--threads 16`

### Q: 下载中断后如何继续？
A: 重新运行相同命令，下载器会自动跳过已下载的文件

### Q: 如何设置代理？
A: 通过环境变量设置 HTTP_PROXY/HTTPS_PROXY

### Q: SSL证书错误？
A: 使用 `--no-ssl-verify` 参数

### Q: 如何批量下载多个视频？
A: 创建JSON配置文件，使用 `--json tasks.json`

### Q: 如何控制并发任务数？
A: 使用 `--max-concurrent 4` 参数（默认3个）

## 🎬 示例命令汇总

```bash
# 单个下载
python -m m3u8.advanced_cli https://example.com/video.m3u8 -o output.mp4

# JSON批量下载 (默认3个并发)
python -m m3u8.advanced_cli --json tasks.json --profile fast

# JSON批量下载 (自定义4个并发)
python -m m3u8.advanced_cli --json tasks.json --profile fast --max-concurrent 4

# 交互模式
python -m m3u8.advanced_cli -i

# 自定义配置
python -m m3u8.advanced_cli https://example.com/video.m3u8 --threads 16 --max-retries 5

# 创建JSON配置
python -m m3u8.advanced_cli -i
# 选择 "3. 创建JSON配置文件"
```

## 📚 编程示例

```python
from m3u8.advanced_downloader import AdvancedM3U8Downloader
from m3u8.config import ConfigTemplates

# 批量下载示例
config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

# 从JSON下载 (默认3个并发)
success = downloader.download_from_json("tasks.json", "./output")

# 从JSON下载 (自定义4个并发)
success = downloader.download_from_json(
    "tasks.json", 
    "./output",
    max_concurrent=4
)

# 单个下载
success = downloader.download_single(
    name="my_video",
    url="https://example.com/video.m3u8",
    output_dir="./output/my_video"
)

# 自定义任务列表
from m3u8.advanced_downloader import DownloadTask

tasks = [
    DownloadTask("video1", "https://example.com/v1.m3u8", "./output/v1"),
    DownloadTask("video2", "https://example.com/v2.m3u8", "./output/v2"),
    DownloadTask("video3", "https://example.com/v3.m3u8", "./output/v3"),
]

results = downloader.manager.download_batch_tasks(tasks, max_concurrent=3)
```

## 🔄 版本历史

### v2.1.0 (最新)
- ✅ 流式下载和实时进度显示
- ✅ JSON配置文件支持
- ✅ 可控并发下载 (支持自定义并发数)
- ✅ 实时显示剩余文件数量
- ✅ 优化的目录结构
- ✅ 自动清理临时目录
- ✅ 增强CLI工具

### v2.0.0
- ✅ 模块化架构
- ✅ 配置模板系统
- ✅ 错误处理和重试机制
- ✅ CLI交互模式

---

**提示**: 建议使用高级版 (`advanced_cli`) 以获得更好的下载体验！
