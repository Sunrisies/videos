# App 目录下三个项目概览

## 项目列表

本工作空间在 `app` 目录下包含三个独立项目，分别负责不同的功能模块：

### 1. Downloader - M3U8 视频下载器

**项目路径**: `app/downloader`

**技术栈**: Python

**核心功能**:
- 高性能 M3U8 视频下载器
- 模块化设计，支持多线程下载
- 断点续传和错误重试机制
- 智能解析 M3U8 文件，提取 TS 片段
- 支持流式下载和实时进度显示
- JSON 批量下载配置
- 可控并发任务管理

**关键特性**:
- 提供命令行接口（CLI）和交互式模式
- 支持配置模板（快速模式、稳定模式、低带宽模式）
- 自定义请求头和代理设置
- 详细的日志记录和进度条显示

**主要模块**:
- `core/`: 核心下载逻辑（解析器、下载器、配置管理）
- `cli/`: 命令行接口（基础版和高级版）
- `tests/`: 测试套件
- `examples/`: 使用示例和演示代码

---

### 2. Server - 视频文件服务器

**项目路径**: `app/server`

**技术栈**: Rust (Axum + Tokio)

**核心功能**:
- 基于 Axum 框架的高性能视频文件服务器
- 自动扫描和发现视频文件
- 支持 MP4 和 HLS（m3u8）格式
- RESTful API 提供视频列表和详情
- 静态文件服务
- 文件监控和数据库同步

**API 端点**:
- `GET /api/videos` - 获取视频列表
- `GET /api/videos/{path}` - 获取视频详情
- `GET /api/refresh` - 刷新数据库
- `GET /api/stats` - 查看统计信息
- `GET /public/{filename}` - 访问静态视频文件
- `GET /thumbnails/{filename}` - 访问缩略图

**关键特性**:
- 智能目录识别和多级文件树结构
- 自动缩略图生成
- 丰富的元数据信息（大小、创建时间、分辨率等）
- 异步并发处理，高性能架构
- 数据库持久化（文件扫描结果）

**主要模块**:
- `routes/`: 路由处理（视频、监控）
- `services/`: 服务层（数据库、文件系统、监控）
- `utils/`: 工具函数（日志、缩略图、时长提取）
- `static/`: 静态前端页面

---

### 3. Web - 多媒体播放前端应用

**项目路径**: `app/web`

**技术栈**: Next.js + React + TypeScript

**核心功能**:
- 完整的多媒体播放系统
- 自动识别媒体类型（视频、音频、流媒体）
- 智能播放器选择和适配
- 响应式设计，支持移动端和桌面端
- 用户认证和权限管理

**支持的媒体格式**:
- 视频：MP4, WebM, OGG
- 音频：MP3, WAV, AAC, FLAC, OGG
- 流媒体：HLS (m3u8)

**关键特性**:
- 完整的播放控制（播放/暂停、进度条、音量、全屏）
- HLS.js 集成，支持流媒体播放
- 原生 HTML5 播放器性能优化
- 媒体库列表和播放器组件
- 时间显示和下载功能

**主要模块**:
- `app/`: 页面和路由（首页、视频列表、播放页面、认证）
- `components/`: UI 组件（播放器、媒体库、列表项）
- `hooks/`: 自定义 Hooks（认证、滚动位置）
- `lib/`: 工具函数和媒体处理
- `types/`: TypeScript 类型定义

---

## 项目关系和工作流程

### 数据流向

```
Downloader (下载视频)
    ↓
Server (扫描、存储、提供 API)
    ↓
Web (获取数据、展示、播放)
```

### 交互关系

| 项目 | 角色 | 输出 | 消费者 |
|------|------|------|---------|
| Downloader | 内容生产者 | 下载的视频文件 | Server |
| Server | 数据服务层 | RESTful API + 静态文件 | Web |
| Web | 用户界面层 | 交互式播放界面 | 最终用户 |

### 部署架构

- **Downloader**: 独立运行的 Python 命令行工具，按需执行下载任务
- **Server**: 后端服务，监听 3000 端口，提供 API 和静态文件服务
- **Web**: 前端应用，通过 Next.js 运行，调用 Server 的 API

---

## 技术栈总结

| 层级 | 项目 | 主要技术 |
|------|------|----------|
| 数据获取层 | Downloader | Python, requests, tqdm, 多线程 |
| 服务层 | Server | Rust, Axum, Tokio, SQLite, walkdir |
| 展示层 | Web | Next.js, React, TypeScript, HLS.js |

---

## 文档更新需求分析

### 需要更新的 README 文件清单

#### 1. 项目根目录 README.md
**当前问题**:
- 缺少三个子项目的整体介绍
- 缺少项目间集成配置说明
- 缺少快速启动的完整流程
- Downloader 输出路径配置未说明

**更新内容**:
- 添加项目架构总览(Downloader → Server → Web)
- 说明三个子项目的职责和关系
- 集成配置:Downloader 输出到 Server public 目录
- 完整的从零启动教程
- 数据流向和工作流程图

#### 2. app/server/README.md
**当前问题**:
- 文档重复内容较多(启动命令重复出现)
- 缺少与 Downloader 集成的说明
- API 文档描述完整但需要补充刷新机制

**更新内容**:
- 清理重复的启动命令说明
- 添加"与 Downloader 集成"章节
- 说明 public 目录的作用和权限要求
- 补充手动刷新数据库的 API 使用

#### 3. app/downloader/docs/README.md
**当前问题**:
- 缺少输出目录配置到 Server 的说明
- JSON 配置示例未包含 output_dir 字段
- 命令行使用示例路径不正确(应从 app 目录运行)

**更新内容**:
- 添加"集成到 Server"章节
- 更新 JSON 配置示例,包含正确的 output_dir
- 修正命令行运行示例(使用正确的工作目录)
- 添加"文件路径最佳实践"说明

#### 4. app/web/README.md
**当前问题**:
- 缺少与 Server API 集成的配置说明
- 缺少环境变量配置示例

**更新内容**:
- 添加 API 端点配置说明
- 补充环境变量(.env)配置示例
- 说明如何连接到本地或远程 Server

### README 更新优先级

| 优先级 | 文件 | 原因 |
|--------|------|------|
| P0 | 项目根 README.md | 新用户首次接触,需要完整的入门指南 |
| P1 | app/downloader/docs/README.md | 命令运行方式和输出路径配置最关键 |
| P2 | app/server/README.md | 清理重复内容,补充集成说明 |
| P3 | app/web/README.md | 前端配置相对简单,优先级较低 |

---

## Python 代码重复问题分析

### 识别的重复代码模式

#### 1. 日志配置重复
**位置**:
- `downloader.py` 中的 `DownloadManager._setup_logging()`
- `advanced_downloader.py` 中的 `StreamDownloadManager._setup_logging()`

**重复代码**:
```python
# 两处完全相同的日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
self.logger = logging.getLogger(__name__)
```

**改进方案**:
提取到 `utils.py` 中的独立函数:
```python
def setup_logger(name: str, log_file: str = 'download.log') -> logging.Logger:
    """配置并返回日志记录器"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(name)
```

#### 2. 重试处理器重复定义
**位置**:
- `downloader.py` 中的 `RetryHandler` 类
- `advanced_downloader.py` 中缺少该类,但需要导入使用

**重复代码**:
`RetryHandler` 类在基础版中定义,高级版中应该复用但未明确声明

**改进方案**:
将 `RetryHandler` 移动到 `utils.py` 作为通用工具类:
```python
# utils.py
class RetryHandler:
    """重试处理器 - 支持指数退避策略"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs):
        """执行函数,失败时重试"""
        # ...实现代码...
```

#### 3. 信号处理重复
**位置**:
- `DownloadManager._signal_handler()`
- `StreamDownloadManager._signal_handler()`

**重复代码**:
```python
def _signal_handler(self, signum, frame):
    """信号处理"""
    if self.logger:
        self.logger.info("收到中断信号,正在停止下载...")
    self.stop_flag = True
```

**改进方案**:
提取为基类或 Mixin:
```python
class DownloadManagerBase:
    """下载管理器基类"""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.stop_flag = False
        self.logger = None
        self._register_signal_handlers()
    
    def _register_signal_handlers(self):
        """注册信号处理"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """统一的信号处理"""
        if self.logger:
            self.logger.info("收到中断信号,正在停止下载...")
        self.stop_flag = True
```

#### 4. 文件名提取逻辑重复
**位置**:
- `DownloadManager._extract_filename()`
- 可能在多处使用 URL 提取文件名的逻辑

**重复代码**:
```python
def _extract_filename(self, url: str) -> str:
    """从URL提取文件名"""
    clean_url = url.split('?')[0]
    filename = clean_url.split('/')[-1]
    if '#' in filename:
        filename = filename.split('#')[0]
    return filename
```

**改进方案**:
移动到 `utils.py` 作为通用函数:
```python
def extract_filename_from_url(url: str) -> str:
    """从URL提取文件名,移除查询参数和片段标识"""
    clean_url = url.split('?')[0].split('#')[0]
    return clean_url.split('/')[-1]
```

#### 5. Session 配置重复
**位置**:
- `DownloadManager.__init__()`
- `StreamDownloadManager.__init__()`
- `M3U8Parser.__init__()`

**重复代码**:
```python
self.session = requests.Session()
self.session.verify = self.config.verify_ssl
if not self.config.verify_ssl:
    warnings.filterwarnings('ignore', category=InsecureRequestWarning)
self.session.headers.update(self.config.headers)
```

**改进方案**:
提取会话创建逻辑:
```python
def create_session(config: DownloadConfig) -> requests.Session:
    """创建配置好的 HTTP 会话"""
    session = requests.Session()
    session.verify = config.verify_ssl
    
    if not config.verify_ssl:
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)
    
    session.headers.update(config.headers)
    return session
```

#### 6. 进度显示逻辑部分重复
**位置**:
- `DownloadManager.download_batch()` 中的状态更新
- `StreamDownloadManager.download_file_stream()` 中的进度显示

**问题**:
虽然显示方式不同(批量 vs 流式),但都涉及进度计算和格式化

**改进方案**:
提取进度格式化工具:
```python
def format_progress(completed: int, total: int, failed: int = 0) -> str:
    """格式化进度字符串"""
    return f"{completed}/{total} 完成, {failed} 失败"

def format_file_size(bytes_count: int) -> str:
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} TB"
```

### 代码重构建议架构

#### 重构后的模块结构

```
app/downloader/core/
├── __init__.py
├── config.py              # 配置类和模板(保持不变)
├── parser.py              # M3U8解析器(保持不变)
├── base.py                # 新增:基类和共享逻辑
│   ├── DownloadManagerBase
│   ├── RetryHandler (从 downloader.py 移入)
│   └── 共享的初始化逻辑
├── downloader.py          # 基础下载器(继承 base)
│   └── M3U8Downloader
├── advanced_downloader.py # 高级下载器(继承 base)
│   ├── StreamDownloadManager
│   └── AdvancedM3U8Downloader
└── utils.py               # 工具函数(扩充)
    ├── setup_logger()
    ├── create_session()
    ├── extract_filename_from_url()
    ├── format_progress()
    ├── format_file_size()
    └── 其他通用函数
```

#### 重构策略

**阶段一:提取通用工具** (不影响现有功能)
1. 创建 `utils.py` 中的新函数
2. 在原有代码中调用新函数,保持兼容
3. 测试验证功能不变

**阶段二:创建基类** (渐进式重构)
1. 创建 `base.py` 定义 `DownloadManagerBase`
2. 让 `DownloadManager` 和 `StreamDownloadManager` 继承基类
3. 移动共享方法到基类
4. 测试验证

**阶段三:清理冗余代码** (优化阶段)
1. 删除重复的方法实现
2. 统一使用基类和工具函数
3. 完整回归测试

### 代码复用设计原则

**保持现有下载方式不变的约束**:
- ✅ `M3U8Downloader.download()` 接口保持不变
- ✅ `AdvancedM3U8Downloader` 的 JSON 批量下载保持不变
- ✅ CLI 命令行参数和交互流程保持不变
- ✅ 下载逻辑(并发策略、重试机制)保持不变

**只重构内部实现**:
- 提取重复的工具函数
- 创建基类共享初始化逻辑
- 统一日志、Session、信号处理等基础设施代码

### 重构收益估算

| 指标 | 重构前 | 重构后 | 改进 |
|------|--------|--------|------|
| 重复代码行数 | ~150 行 | ~20 行 | -87% |
| 维护成本 | 高(多处修改) | 低(单点修改) | 显著降低 |
| 测试覆盖 | 需要测试多个副本 | 测试一次复用 | 提高效率 |
| 代码可读性 | 中等(重复干扰) | 高(结构清晰) | 提升 |

---

## 项目集成配置

### Downloader 输出目录配置

为了让 Downloader 下载的视频文件直接被 Server 识别和提供服务，需要配置 Downloader 的输出目录指向 Server 的 public 目录。

#### 配置方式

**方式一：命令行参数指定**

在运行 Downloader 时，通过 `--output-dir` 参数指定输出目录为 Server 的 public 目录：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  https://example.com/video.m3u8 \
  -o video.mp4 \
  --output-dir ../server/public
```

或使用 JSON 批量下载配置文件：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  --json downloader/examples/tasks.example.json \
  --output-dir ../server/public \
  --max-concurrent 3
```

**方式二：修改 JSON 配置文件**

编辑下载任务配置文件（如 `downloader/examples/tasks.example.json`），将每个任务的 `output_dir` 字段设置为 Server 的 public 目录：

```json
[
    {
        "name": "video1",
        "url": "https://example.com/video1.m3u8",
        "output_dir": "../server/public",
        "params": {
            "quality": "1080p"
        }
    },
    {
        "name": "video2",
        "url": "https://example.com/video2.m3u8",
        "output_dir": "../server/public",
        "params": {
            "quality": "720p"
        }
    }
]
```

**方式三：修改默认配置**

编辑 `downloader/core/config.py` 文件，修改 `DownloadConfig` 类的 `output_dir` 默认值：

```python
@dataclass
class DownloadConfig:
    # ...
    output_dir: str = "../server/public"  # 修改默认输出目录
    # ...
```

#### 输出文件路径规范

下载完成后，文件将保存在以下位置：

```
app/server/public/
├── video1.mp4           # 单个视频文件
├── video2.mp4
├── video1/              # HLS 目录（如果是 m3u8 格式）
│   ├── video1.mp4       # 合并后的 MP4 文件
│   ├── index.m3u8
│   └── segments/
└── video2/
    └── video2.mp4
```

#### Server 自动识别机制

Server 会在启动时自动扫描 `public` 目录：
- 自动发现新增的视频文件
- 提取元数据信息（大小、创建时间）
- 生成缩略图（如果配置了 ffmpeg）
- 将信息存储到数据库

下载完成后，可以通过以下 API 访问：
- 视频列表：`http://localhost:3000/api/videos`
- 视频文件：`http://localhost:3000/public/video1.mp4`
- 刷新数据库：`http://localhost:3000/api/refresh`（手动触发扫描）

---

## 项目快速启动指南

### 前置要求

| 组件 | 要求 |
|------|------|
| Python | 3.8+ |
| Rust | 1.70+ |
| Node.js | 16+ |
| 包管理器 | uv (推荐) / pip / cargo / npm |

### 第一步：安装依赖

#### 1. Downloader 依赖安装

```bash
cd d:\project\project\videos\app\downloader
pip install -r requirements.txt
# 或使用 uv（推荐）
uv pip install -r requirements.txt
```

**依赖包**：
- `requests>=2.25.0` - HTTP 请求库
- `tqdm>=4.60.0` - 进度条显示

#### 2. Server 依赖构建

```bash
cd d:\project\project\videos\app\server
cargo build --release
```

**依赖项**（自动管理）：
- `axum` - Web 框架
- `tokio` - 异步运行时
- `tower-http` - HTTP 中间件
- `serde` - 序列化/反序列化
- `walkdir` - 目录遍历

#### 3. Web 依赖安装

```bash
cd d:\project\project\videos\app\web
npm install
# 或使用 pnpm
pnpm install
```

**主要依赖**：
- `next` - Next.js 框架
- `react` - React 库
- `hls.js` - HLS 流媒体播放

---

### 第二步：配置项目

#### 1. 确保 Server public 目录存在

```bash
mkdir -p d:\project\project\videos\app\server\public
```

#### 2. 配置 Downloader 输出目录

根据上述「Downloader 输出目录配置」章节，选择合适的配置方式。

#### 3. 配置 Web API 端点（如果需要）

编辑 `app/web/next.config.ts`，确保 API 代理指向 Server 地址：

```typescript
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:3000/api/:path*',
      },
    ];
  },
};
```

---

### 第三步：启动服务

#### 启动顺序建议

```mermaid
graph LR
    A[1. 启动 Server] --> B[2. 运行 Downloader]
    B --> C[3. 启动 Web]
    C --> D[用户访问]
```

#### 1. 启动 Server（后端服务）

```bash
cd d:\project\project\videos\app\server
cargo run --release
```

**启动成功标志**：
```
[INFO] Server listening on 0.0.0.0:3000
[INFO] Scanning public directory...
[INFO] Found X videos
```

**服务地址**：
- API：`http://localhost:3000/api/videos`
- 静态文件：`http://localhost:3000/public/*`

#### 2. 运行 Downloader（下载视频）

**交互式模式**（推荐新手）：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli -i
```

**单个视频下载**：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  https://example.com/video.m3u8 \
  -o myvideo.mp4 \
  --output-dir server/public
```

**批量下载（JSON 配置）**：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  --json downloader/examples/tasks.example.json \
  --output-dir server/public \
  --max-concurrent 3
```

**下载完成后刷新 Server 数据库**：

```bash
curl http://localhost:3000/api/refresh
```

或在浏览器访问：`http://localhost:3000/api/refresh`

#### 3. 启动 Web（前端应用）

**开发模式**：

```bash
cd d:\project\project\videos\app\web
npm run dev
```

**生产模式**：

```bash
cd d:\project\project\videos\app\web
npm run build
npm run start
```

**访问地址**：
- 开发环境：`http://localhost:3001`（或 Next.js 分配的端口）
- 生产环境：`http://localhost:3000`

---

### 第四步：验证集成

#### 验证流程

1. **验证 Server 是否正常运行**

```bash
curl http://localhost:3000/api/videos
```

预期返回：
```json
{
  "videos": [
    {
      "name": "video1.mp4",
      "path": "/public/video1.mp4",
      "type": "mp4",
      "size": "15.50 MB",
      "created_at": "2025-01-13 10:30:00"
    }
  ]
}
```

2. **验证下载的视频是否可访问**

在浏览器访问：`http://localhost:3000/public/video1.mp4`

预期：视频正常播放或下载

3. **验证 Web 应用是否连接成功**

访问 Web 应用首页，检查视频列表是否显示

点击视频，检查播放器是否正常工作

---

## 完整工作流示例

### 场景：下载并播放一个视频

```bash
# 1. 启动 Server
cd d:\project\project\videos\app\server
cargo run --release &

# 等待 Server 启动完成（约 5-10 秒）
sleep 10

# 2. 下载视频到 Server 的 public 目录
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  https://example.com/test-video.m3u8 \
  -o test-video.mp4 \
  --output-dir server/public \
  --profile stable

# 3. 刷新 Server 数据库（让 Server 识别新文件）
curl http://localhost:3000/api/refresh

# 4. 验证视频已被识别
curl http://localhost:3000/api/videos | grep "test-video.mp4"

# 5. 启动 Web 应用
cd d:\project\project\videos\app\web
npm run dev

# 6. 在浏览器访问 http://localhost:3001，找到并播放 test-video.mp4
```

---

## 常见问题处理

### 问题 1：Downloader 找不到模块

**错误信息**：
```
ModuleNotFoundError: No module named 'downloader.core'
```

**解决方案**：
确保从 `app` 目录运行，而不是 `app/downloader` 目录：

```bash
cd d:\project\project\videos\app  # 正确的工作目录
uv run -m downloader.cli.advanced_cli -i
```

### 问题 2：Server 未识别下载的视频

**症状**：
视频下载完成，但 API 返回的列表中没有该视频

**解决方案**：
1. 确认文件已保存到 `server/public` 目录
2. 手动触发刷新：`curl http://localhost:3000/api/refresh`
3. 重启 Server

### 问题 3：Web 应用无法访问 Server API

**症状**：
前端页面显示「加载中」或「无法获取视频列表」

**解决方案**：
1. 确认 Server 已启动：`curl http://localhost:3000/api/videos`
2. 检查 Next.js 配置中的 API 代理设置
3. 检查浏览器控制台的网络请求错误

### 问题 4：视频下载后格式不正确

**症状**：
Server 识别为 `unknown` 类型，或浏览器无法播放

**解决方案**：
1. 确保 Downloader 成功合并 TS 文件为 MP4
2. 检查下载日志中是否有错误信息
3. 手动验证文件完整性：`ffprobe server/public/video.mp4`

---

## 生产部署建议

### 目录结构优化

```
/var/www/video-platform/
├── server/
│   ├── bin/
│   │   └── video-server        # Rust 编译后的二进制文件
│   └── public/                  # 视频文件目录（大容量磁盘挂载点）
│       ├── video1.mp4
│       └── video2.mp4
├── web/
│   └── .next/                   # Next.js 构建产物
└── downloader/
    ├── venv/                    # Python 虚拟环境
    └── config/
        └── tasks.json           # 下载任务配置
```

### 配置建议

| 配置项 | 开发环境 | 生产环境 |
|--------|---------|----------|
| Downloader output_dir | `../server/public` | `/var/www/video-platform/server/public` |
| Server public 目录 | 项目内相对路径 | 独立磁盘挂载 |
| Server 端口 | 3000 | 8080（Nginx 反向代理） |
| Web 端口 | 3001 | 3000（Nginx 反向代理） |
| 日志级别 | DEBUG | INFO |

### 自动化脚本

**一键启动脚本**（`start-all.sh`）：

```bash
#!/bin/bash

# 启动 Server
cd /var/www/video-platform/server
./bin/video-server &
SERVER_PID=$!

# 等待 Server 就绪
sleep 5

# 启动 Web
cd /var/www/video-platform/web
npm run start &
WEB_PID=$!

echo "Server PID: $SERVER_PID"
echo "Web PID: $WEB_PID"
echo "Services started successfully"
```

**定时下载脚本**（`cron-download.sh`）：

```bash
#!/bin/bash

cd /var/www/video-platform/downloader
source venv/bin/activate

# 执行批量下载
python -m downloader.cli.advanced_cli \
  --json config/tasks.json \
  --output-dir /var/www/video-platform/server/public \
  --max-concurrent 2 \
  --profile stable

# 刷新 Server 数据库
curl http://localhost:8080/api/refresh

echo "Download and refresh completed at $(date)"
```

添加到 crontab：
```bash
# 每天凌晨 2 点执行下载任务
0 2 * * * /var/www/video-platform/downloader/cron-download.sh >> /var/log/video-download.log 2>&1
```
```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  --json downloader/examples/tasks.example.json \
  --output-dir ../server/public \
  --max-concurrent 3
```

**方式二：修改 JSON 配置文件**

编辑下载任务配置文件（如 `downloader/examples/tasks.example.json`），将每个任务的 `output_dir` 字段设置为 Server 的 public 目录：

```json
[
    {
        "name": "video1",
        "url": "https://example.com/video1.m3u8",
        "output_dir": "../server/public",
        "params": {
            "quality": "1080p"
        }
    },
    {
        "name": "video2",
        "url": "https://example.com/video2.m3u8",
        "output_dir": "../server/public",
        "params": {
            "quality": "720p"
        }
    }
]
```

**方式三：修改默认配置**

编辑 `downloader/core/config.py` 文件，修改 `DownloadConfig` 类的 `output_dir` 默认值：

```python
@dataclass
class DownloadConfig:
    # ...
    output_dir: str = "../server/public"  # 修改默认输出目录
    # ...
```

#### 输出文件路径规范

下载完成后，文件将保存在以下位置：

```
app/server/public/
├── video1.mp4           # 单个视频文件
├── video2.mp4
├── video1/              # HLS 目录（如果是 m3u8 格式）
│   ├── video1.mp4       # 合并后的 MP4 文件
│   ├── index.m3u8
│   └── segments/
└── video2/
    └── video2.mp4
```

#### Server 自动识别机制

Server 会在启动时自动扫描 `public` 目录：
- 自动发现新增的视频文件
- 提取元数据信息（大小、创建时间）
- 生成缩略图（如果配置了 ffmpeg）
- 将信息存储到数据库

下载完成后，可以通过以下 API 访问：
- 视频列表：`http://localhost:3000/api/videos`
- 视频文件：`http://localhost:3000/public/video1.mp4`
- 刷新数据库：`http://localhost:3000/api/refresh`（手动触发扫描）

---

## 项目快速启动指南

### 前置要求

| 组件 | 要求 |
|------|------|
| Python | 3.8+ |
| Rust | 1.70+ |
| Node.js | 16+ |
| 包管理器 | uv (推荐) / pip / cargo / npm |

### 第一步：安装依赖

#### 1. Downloader 依赖安装

```bash
cd d:\project\project\videos\app\downloader
pip install -r requirements.txt
# 或使用 uv（推荐）
uv pip install -r requirements.txt
```

**依赖包**：
- `requests>=2.25.0` - HTTP 请求库
- `tqdm>=4.60.0` - 进度条显示

#### 2. Server 依赖构建

```bash
cd d:\project\project\videos\app\server
cargo build --release
```

**依赖项**（自动管理）：
- `axum` - Web 框架
- `tokio` - 异步运行时
- `tower-http` - HTTP 中间件
- `serde` - 序列化/反序列化
- `walkdir` - 目录遍历

#### 3. Web 依赖安装

```bash
cd d:\project\project\videos\app\web
npm install
# 或使用 pnpm
pnpm install
```

**主要依赖**：
- `next` - Next.js 框架
- `react` - React 库
- `hls.js` - HLS 流媒体播放

---

### 第二步：配置项目

#### 1. 确保 Server public 目录存在

```bash
mkdir -p d:\project\project\videos\app\server\public
```

#### 2. 配置 Downloader 输出目录

根据上述「Downloader 输出目录配置」章节，选择合适的配置方式。

#### 3. 配置 Web API 端点（如果需要）

编辑 `app/web/next.config.ts`，确保 API 代理指向 Server 地址：

```typescript
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:3000/api/:path*',
      },
    ];
  },
};
```

---

### 第三步：启动服务

#### 启动顺序建议

```mermaid
graph LR
    A[1. 启动 Server] --> B[2. 运行 Downloader]
    B --> C[3. 启动 Web]
    C --> D[用户访问]
```

#### 1. 启动 Server（后端服务）

```bash
cd d:\project\project\videos\app\server
cargo run --release
```

**启动成功标志**：
```
[INFO] Server listening on 0.0.0.0:3000
[INFO] Scanning public directory...
[INFO] Found X videos
```

**服务地址**：
- API：`http://localhost:3000/api/videos`
- 静态文件：`http://localhost:3000/public/*`

#### 2. 运行 Downloader（下载视频）

**交互式模式**（推荐新手）：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli -i
```

**单个视频下载**：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  https://example.com/video.m3u8 \
  -o myvideo.mp4 \
  --output-dir server/public
```

**批量下载（JSON 配置）**：

```bash
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  --json downloader/examples/tasks.example.json \
  --output-dir server/public \
  --max-concurrent 3
```

**下载完成后刷新 Server 数据库**：

```bash
curl http://localhost:3000/api/refresh
```

或在浏览器访问：`http://localhost:3000/api/refresh`

#### 3. 启动 Web（前端应用）

**开发模式**：

```bash
cd d:\project\project\videos\app\web
npm run dev
```

**生产模式**：

```bash
cd d:\project\project\videos\app\web
npm run build
npm run start
```

**访问地址**：
- 开发环境：`http://localhost:3001`（或 Next.js 分配的端口）
- 生产环境：`http://localhost:3000`

---

### 第四步：验证集成

#### 验证流程

1. **验证 Server 是否正常运行**

```bash
curl http://localhost:3000/api/videos
```

预期返回：
```json
{
  "videos": [
    {
      "name": "video1.mp4",
      "path": "/public/video1.mp4",
      "type": "mp4",
      "size": "15.50 MB",
      "created_at": "2025-01-13 10:30:00"
    }
  ]
}
```

2. **验证下载的视频是否可访问**

在浏览器访问：`http://localhost:3000/public/video1.mp4`

预期：视频正常播放或下载

3. **验证 Web 应用是否连接成功**

访问 Web 应用首页，检查视频列表是否显示

点击视频，检查播放器是否正常工作

---

## 完整工作流示例

### 场景：下载并播放一个视频

```bash
# 1. 启动 Server
cd d:\project\project\videos\app\server
cargo run --release &

# 等待 Server 启动完成（约 5-10 秒）
sleep 10

# 2. 下载视频到 Server 的 public 目录
cd d:\project\project\videos\app
uv run -m downloader.cli.advanced_cli \
  https://example.com/test-video.m3u8 \
  -o test-video.mp4 \
  --output-dir server/public \
  --profile stable

# 3. 刷新 Server 数据库（让 Server 识别新文件）
curl http://localhost:3000/api/refresh

# 4. 验证视频已被识别
curl http://localhost:3000/api/videos | grep "test-video.mp4"

# 5. 启动 Web 应用
cd d:\project\project\videos\app\web
npm run dev

# 6. 在浏览器访问 http://localhost:3001，找到并播放 test-video.mp4
```

---

## 常见问题处理

### 问题 1：Downloader 找不到模块

**错误信息**：
```
ModuleNotFoundError: No module named 'downloader.core'
```

**解决方案**：
确保从 `app` 目录运行，而不是 `app/downloader` 目录：

```bash
cd d:\project\project\videos\app  # 正确的工作目录
uv run -m downloader.cli.advanced_cli -i
```

### 问题 2：Server 未识别下载的视频

**症状**：
视频下载完成，但 API 返回的列表中没有该视频

**解决方案**：
1. 确认文件已保存到 `server/public` 目录
2. 手动触发刷新：`curl http://localhost:3000/api/refresh`
3. 重启 Server

### 问题 3：Web 应用无法访问 Server API

**症状**：
前端页面显示「加载中」或「无法获取视频列表」

**解决方案**：
1. 确认 Server 已启动：`curl http://localhost:3000/api/videos`
2. 检查 Next.js 配置中的 API 代理设置
3. 检查浏览器控制台的网络请求错误

### 问题 4：视频下载后格式不正确

**症状**：
Server 识别为 `unknown` 类型，或浏览器无法播放

**解决方案**：
1. 确保 Downloader 成功合并 TS 文件为 MP4
2. 检查下载日志中是否有错误信息
3. 手动验证文件完整性：`ffprobe server/public/video.mp4`

---

## 生产部署建议

### 目录结构优化

```
/var/www/video-platform/
├── server/
│   ├── bin/
│   │   └── video-server        # Rust 编译后的二进制文件
│   └── public/                  # 视频文件目录（大容量磁盘挂载点）
│       ├── video1.mp4
│       └── video2.mp4
├── web/
│   └── .next/                   # Next.js 构建产物
└── downloader/
    ├── venv/                    # Python 虚拟环境
    └── config/
        └── tasks.json           # 下载任务配置
```

### 配置建议

| 配置项 | 开发环境 | 生产环境 |
|--------|---------|----------|
| Downloader output_dir | `../server/public` | `/var/www/video-platform/server/public` |
| Server public 目录 | 项目内相对路径 | 独立磁盘挂载 |
| Server 端口 | 3000 | 8080（Nginx 反向代理） |
| Web 端口 | 3001 | 3000（Nginx 反向代理） |
| 日志级别 | DEBUG | INFO |

### 自动化脚本

**一键启动脚本**（`start-all.sh`）：

```bash
#!/bin/bash

# 启动 Server
cd /var/www/video-platform/server
./bin/video-server &
SERVER_PID=$!

# 等待 Server 就绪
sleep 5

# 启动 Web
cd /var/www/video-platform/web
npm run start &
WEB_PID=$!

echo "Server PID: $SERVER_PID"
echo "Web PID: $WEB_PID"
echo "Services started successfully"
```

**定时下载脚本**（`cron-download.sh`）：

```bash
#!/bin/bash

cd /var/www/video-platform/downloader
source venv/bin/activate

# 执行批量下载
python -m downloader.cli.advanced_cli \
  --json config/tasks.json \
  --output-dir /var/www/video-platform/server/public \
  --max-concurrent 2 \
  --profile stable

# 刷新 Server 数据库
curl http://localhost:8080/api/refresh

echo "Download and refresh completed at $(date)"
```

添加到 crontab：
```bash
# 每天凌晨 2 点执行下载任务
0 2 * * * /var/www/video-platform/downloader/cron-download.sh >> /var/log/video-download.log 2>&1
```
