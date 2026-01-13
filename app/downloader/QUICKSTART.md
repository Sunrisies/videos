# M3U8 下载器使用指南

## 安装依赖

首先，确保安装了必要的依赖：

```bash
cd d:\project\project\videos\app\downloader
pip install -r requirements.txt
```

或使用 uv：

```bash
cd d:\project\project\videos\app\downloader
uv pip install -r requirements.txt
```

## 正确的运行方式

由于 Python 模块导入机制的限制，必须从 **app 目录** 运行命令，而不是从 downloader 目录。

### ✅ 正确方式一：使用模块路径（推荐）

```bash
# 切换到 app 目录
cd d:\project\project\videos\app

# 运行基础 CLI
uv run -m downloader.cli.cli https://example.com/video.m3u8 -o output.mp4

# 运行高级 CLI（单个下载）
uv run -m downloader.cli.advanced_cli https://example.com/video.m3u8 -o output.mp4

# 运行高级 CLI（JSON批量下载）
uv run -m downloader.cli.advanced_cli --json downloader/examples/tasks.example.json --max-concurrent 4
```

### ✅ 正确方式二：使用便捷脚本

```bash
# 切换到 downloader 目录
cd d:\project\project\videos\app\downloader

# 运行基础 CLI
python run_cli.py https://example.com/video.m3u8 -o output.mp4

# 运行高级 CLI
python run_advanced_cli.py --json examples/tasks.example.json --max-concurrent 4
```

### ❌ 错误方式

```bash
# ❌ 不要在 downloader 目录下直接运行模块
cd d:\project\project\videos\app\downloader
uv run -m cli.advanced_cli  # 会报错！

# ❌ 不要使用相对的模块路径
uv run -m cli.cli  # 会报错！
```

## 命令示例

### 基础命令行工具

#### 单个视频下载
```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.cli https://example.com/video.m3u8
```

#### 指定输出文件
```bash
uv run -m downloader.cli.cli https://example.com/video.m3u8 -o myvideo.mp4
```

#### 指定线程数
```bash
uv run -m downloader.cli.cli https://example.com/video.m3u8 -t 16
```

#### 使用配置模板
```bash
# 快速模式（高并发）
uv run -m downloader.cli.cli https://example.com/video.m3u8 --profile fast

# 稳定模式（推荐）
uv run -m downloader.cli.cli https://example.com/video.m3u8 --profile stable

# 低带宽模式
uv run -m downloader.cli.cli https://example.com/video.m3u8 --profile low_bandwidth
```

#### 交互模式
```bash
uv run -m downloader.cli.cli -i
```

### 高级命令行工具

#### 单个视频下载（流式）
```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli https://example.com/video.m3u8 -o output.mp4
```

#### JSON批量下载
```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli --json downloader/examples/tasks.example.json
```

#### 指定并发任务数
```bash
uv run -m downloader.cli.advanced_cli --json downloader/examples/tasks.example.json --max-concurrent 4
```

#### 指定输出目录
```bash
uv run -m downloader.cli.advanced_cli --json downloader/examples/tasks.example.json --output-dir ./downloads
```

#### 使用配置模板 + 并发控制
```bash
uv run -m downloader.cli.advanced_cli --json downloader/examples/tasks.example.json --profile fast --max-concurrent 4
```

## 编程接口使用

### 基础下载器

```python
import sys
sys.path.insert(0, r'd:\project\project\videos\app')

from downloader.core.downloader import M3U8Downloader
from downloader.core.config import DownloadConfig

# 使用默认配置
downloader = M3U8Downloader("https://example.com/video.m3u8")
success = downloader.download("output.mp4")

# 使用自定义配置
config = DownloadConfig(
    num_threads=16,
    max_retries=5,
    temp_dir="./temp",
    output_dir="./output"
)
downloader = M3U8Downloader("https://example.com/video.m3u8", config)
success = downloader.download("output.mp4")
```

### 高级下载器

```python
import sys
sys.path.insert(0, r'd:\project\project\videos\app')

from downloader.core.advanced_downloader import AdvancedM3U8Downloader
from downloader.core.config import ConfigTemplates

# 创建下载器
config = ConfigTemplates.stable()
downloader = AdvancedM3U8Downloader(config)

# 单个下载（流式）
success = downloader.download_single(
    name="my_video",
    url="https://example.com/video.m3u8",
    output_dir="./output"
)

# JSON批量下载
success = downloader.download_from_json(
    json_file="tasks.json",
    base_output_dir="./output",
    max_concurrent=3
)
```

### 使用配置模板

```python
from downloader.core.config import ConfigTemplates

# 快速模式（高并发，适合带宽充足）
config = ConfigTemplates.fast()

# 稳定模式（推荐，平衡配置）
config = ConfigTemplates.stable()

# 低带宽模式（低并发，适合网络较差）
config = ConfigTemplates.low_bandwidth()
```

## JSON配置文件格式

创建一个 `tasks.json` 文件：

```json
[
  {
    "name": "video1",
    "url": "https://example.com/video1.m3u8",
    "output_dir": "./output/video1",
    "params": {
      "quality": "1080p",
      "language": "chinese"
    }
  },
  {
    "name": "video2",
    "url": "https://example.com/video2.m3u8",
    "output_dir": "./output/video2",
    "params": {
      "quality": "720p"
    }
  }
]
```

## 常见问题

### Q: 为什么不能直接在 downloader 目录运行？

**A**: 因为 Python 的相对导入机制要求模块必须作为包的一部分被导入。当你在 downloader 目录运行 `-m cli.advanced_cli` 时，Python 会把 downloader 当作顶层包，此时 `..core` 的相对导入会超出包边界。

### Q: ModuleNotFoundError: No module named 'cli.config'

**A**: 这个错误说明你在错误的目录运行了命令。请确保：
1. 从 `d:\project\project\videos\app` 目录运行
2. 使用完整的模块路径 `downloader.cli.advanced_cli`

### Q: 如何安装依赖？

**A**: 
```bash
cd d:\project\project\videos\app\downloader
pip install -r requirements.txt
```

或使用 uv：
```bash
uv pip install -r requirements.txt
```

### Q: 下载速度慢怎么办？

**A**: 使用快速模式：
```bash
uv run -m downloader.cli.cli https://example.com/video.m3u8 --profile fast
```

或增加线程数：
```bash
uv run -m downloader.cli.cli https://example.com/video.m3u8 -t 16
```

### Q: 下载失败怎么办？

**A**: 下载器支持断点续传，直接重新运行相同的命令即可继续下载。

## 技术说明

### 目录结构
```
app/
└── downloader/
    ├── core/           # 核心功能模块
    ├── cli/            # 命令行工具
    ├── tests/          # 测试文件
    ├── examples/       # 示例代码
    ├── docs/           # 文档
    ├── run_cli.py      # 便捷启动脚本
    └── run_advanced_cli.py
```

### 导入机制
- 从 app 目录运行时，完整路径为 `downloader.cli.advanced_cli`
- CLI 模块通过相对导入 `..core` 访问核心模块
- 便捷脚本通过 `sys.path.insert()` 解决路径问题

## 更多信息

- 详细文档：`docs/README.md`
- 使用指南：`docs/USAGE.md`
- 示例代码：`examples/`
