# 视频文件服务器 (Video File Server)

## 项目名称
**视频文件服务器** - 基于 Rust 和 Axum 框架的高性能视频文件服务系统

## 项目简介

本项目是一个基于 Rust 语言和 Axum Web 框架开发的高性能视频文件服务器。它能够自动扫描指定目录下的视频文件，提供 RESTful API 接口进行视频管理和查询，并支持多种视频格式的在线播放，包括 MP4 直播视频和 HLS (HTTP Live Streaming) 流媒体格式。

服务器采用异步架构设计，具有高性能、低延迟、稳定可靠的特点，适用于个人视频库管理、在线视频播放、媒体资源服务等多种场景。

## 功能特性

### 🎯 核心功能
- **自动视频发现**: 自动扫描 `public` 目录下的视频文件和目录结构
- **多格式支持**: 完整支持 MP4、M3U8、TS 等视频格式，以及 VTT、SRT 字幕文件
- **智能目录识别**: 自动识别包含视频文件的目录，智能分类为 HLS 流媒体目录或普通视频目录
- **RESTful API**: 提供简洁、规范的 RESTful API 接口获取视频列表和详细信息
- **静态文件服务**: 直接通过 URL 访问所有静态资源文件

### 🚀 技术特性
- **高性能架构**: 基于 Axum 和 Tokio 的异步高性能架构，支持高并发访问
- **类型安全**: 完整的 Rust 类型系统保障，编译时检查，避免运行时错误
- **错误处理**: 完善的错误处理机制，适当的 HTTP 状态码和错误信息
- **CORS 支持**: 内置跨域资源共享支持，可从前端应用直接调用
- **模块化设计**: 代码结构清晰，模块职责单一，易于维护和扩展

### 📊 数据特性
- **丰富元数据**: 提供视频文件的详细信息（大小、创建时间、缩略图等）
- **目录结构**: 支持多层级目录结构展示，最多递归2层
- **文件类型识别**: 智能识别各种视频相关文件类型
- **大小格式化**: 自动格式化文件大小显示（B/KB/MB/GB）

## 安装与配置步骤

### 环境要求

#### 系统要求
- **操作系统**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **内存**: 建议 2GB 以上可用内存
- **存储**: 至少 100MB 可用磁盘空间（用于编译和日志）

#### 软件依赖
- **Rust 工具链**: 1.70.0 或更高版本
  - `rustc` (Rust 编译器)
  - `cargo` (Rust 包管理器)
- **Git**: 用于版本控制和代码管理
- **终端**: PowerShell (Windows), Bash/Linux Terminal (Linux/macOS)

### 依赖安装

#### 1. 安装 Rust 工具链

**Windows/Linux/macOS:**
```bash
# 通过官方安装脚本安装
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 或者下载独立安装程序
# Windows: 下载 rustup-init.exe 从 https://rustup.rs/
```

**验证安装:**
```bash
rustc --version
cargo --version
```

#### 2. 克隆项目代码

```bash
# 进入项目目录
cd d:/project/project/videos

# 如果项目未克隆，请使用以下命令
git clone <repository-url> videos
cd videos
```

#### 3. 安装项目依赖

```bash
# 进入服务器目录
cd app/server

# 安装 Rust 依赖（自动下载并编译）
cargo build

# 或者使用更快的构建方式（开发环境）
cargo build --release
```

#### 4. 配置环境

项目默认配置无需额外环境变量，但可以根据需要调整：

- **服务器端口**: 默认 3000（在 `main.rs` 中修改）
- **视频目录**: 默认 `public` 目录（在 `main.rs` 中修改）
- **CORS 设置**: 默认允许所有来源（可在代码中调整）

## 使用说明

### 启动服务

#### 开发模式启动
```bash
# 在 app/server 目录下执行
cargo run
```

#### 生产模式启动
```bash
# 编译优化版本
cargo build --release

# 运行优化版本
cargo run --release
```

#### 后台运行
```bash
# Linux/macOS 后台运行
nohup cargo run --release > server.log 2>&1 &

# Windows 后台运行
start /b cargo run --release > server.log 2>&1
```

### 访问服务

服务启动后，默认监听在 `0.0.0.0:3000`，可以通过以下方式访问：

#### 1. API 接口访问

**获取视频列表 (第一层):**
```bash
curl http://localhost:3000/api/videos
```

**获取视频详情:**
```bash
# 获取指定目录的详细信息
curl http://localhost:3000/api/videos/1221

# 获取特定视频文件信息
curl http://localhost:3000/api/videos/video1.mp4
```

#### 2. 静态文件访问

**直接访问视频文件:**
```bash
# MP4 视频
curl -O http://localhost:3000/public/video1.mp4

# HLS 流媒体
curl http://localhost:3000/public/1221/index.m3u8
```

**浏览器访问:**
- 静态页面: `http://localhost:3000/static/index.html`
- 视频文件: `http://localhost:3000/public/video1.mp4`
- HLS 播放列表: `http://localhost:3000/public/1221/index.m3u8`

### 主要功能演示

#### 1. 视频列表管理

**前端调用示例 (JavaScript):**
```javascript
// 获取视频列表
async function getVideoList() {
    const response = await fetch('http://localhost:3000/api/videos');
    const data = await response.json();
    
    console.log('视频列表:', data.videos);
    
    // 渲染视频列表
    data.videos.forEach(video => {
        if (video.type === 'mp4') {
            // 显示 MP4 视频
            console.log(`视频: ${video.name}`);
            console.log(`大小: ${video.size}`);
            console.log(`创建时间: ${video.created_at}`);
            
            // 播放视频
            const videoElement = document.createElement('video');
            videoElement.src = video.path;
            videoElement.controls = true;
            videoElement.style.width = '100%';
            document.body.appendChild(videoElement);
        } else if (video.type === 'hls_directory') {
            // 处理 HLS 流媒体
            console.log(`HLS 流媒体: ${video.name}`);
            console.log(`子文件数: ${video.children?.length || 0}`);
        }
    });
}
```

#### 2. 视频详情查询

**获取详细信息:**
```javascript
async function getVideoDetails(path) {
    const response = await fetch(`http://localhost:3000/api/videos/${path}`);
    const detail = await response.json();
    
    console.log('视频详情:', detail);
    
    // 显示子文件
    if (detail.children) {
        detail.children.forEach(child => {
            console.log(`  - ${child.name} (${child.type})`);
        });
    }
}
```

#### 3. 字幕文件处理

**添加字幕到视频:**
```javascript
function addSubtitles(videoElement, videoInfo) {
    if (videoInfo.subtitle) {
        const track = document.createElement('track');
        track.kind = 'subtitles';
        track.label = '中文';
        track.srclang = 'zh';
        track.src = videoInfo.subtitle;
        track.default = true;
        videoElement.appendChild(track);
    }
}
```

#### 4. HLS 流媒体播放

**使用 hls.js 播放 HLS:**
```javascript
// 需要引入 hls.js 库
if (Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource('http://localhost:3000/public/1221/index.m3u8');
    hls.attachMedia(videoElement);
    hls.on(Hls.Events.MANIFEST_PARSED, function() {
        videoElement.play();
    });
}
```

## 项目结构说明

### 目录结构

```
videos/
├── app/
│   └── server/                    # Rust 服务器项目
│       ├── src/
│       │   └── main.rs           # 主程序文件
│       ├── public/               # 视频文件存储目录
│       │   ├── video1.mp4        # MP4 视频文件
│       │   ├── video2.mp4
│       │   ├── 1221/             # HLS 流媒体目录
│       │   │   ├── index.m3u8
│       │   │   ├── segment_000.ts
│       │   │   └── ...
│       │   └── subtitles/        # 字幕文件目录
│       │       └── video1.vtt
│       ├── static/               # 静态网页文件
│       │   ├── index.html        # 示例页面
│       │   ├── style.css         # 样式文件
│       │   └── script.js         # 脚本文件
│       ├── Cargo.toml            # Rust 项目配置
│       ├── Cargo.lock            # 依赖锁定文件
│       └── README.md             # 服务器说明文档
├── .gitignore                    # Git 忽略配置
└── README.md                     # 项目总说明文档（本文件）
```

### 核心文件说明

#### `app/server/src/main.rs`
- **Axum 路由配置**: 定义 API 路由和静态文件服务
- **视频扫描逻辑**: 使用 `walkdir` 高效遍历目录
- **元数据提取**: 文件大小、创建时间、类型识别
- **错误处理**: 完善的错误处理和 HTTP 状态码

#### `app/server/Cargo.toml`
- **依赖管理**: 定义项目依赖和版本
- **特性配置**: 启用必要的 Tokio 特性

#### `app/server/public/`
- **视频存储**: 存放所有视频文件和目录
- **自动发现**: 服务器自动扫描此目录
- **访问权限**: 通过 `/public/` 前缀访问

#### `app/server/static/`
- **静态资源**: HTML、CSS、JS 等静态文件
- **示例页面**: 提供功能演示和测试界面
- **访问路径**: 通过 `/static/` 前缀访问

### API 结构

#### 视频列表接口
```json
{
  "videos": [
    {
      "name": "video1.mp4",
      "path": "/public/video1.mp4",
      "type": "mp4",
      "size": "15.50 MB",
      "created_at": "2025-08-21 17:05:42",
      "thumbnail": "/public/video1.jpg"
    },
    {
      "name": "1221",
      "path": "/public/1221",
      "type": "hls_directory",
      "created_at": "2025-09-20 10:59:49",
      "children": [...]
    }
  ]
}
```

#### 视频详情接口
```json
{
  "name": "1221",
  "path": "/public/1221",
  "type": "hls_directory",
  "created_at": "2025-09-20 10:59:49",
  "children": [
    {
      "name": "index.m3u8",
      "path": "/public/1221/index.m3u8",
      "type": "m3u8",
      "size": "2.50 KB"
    },
    {
      "name": "segment_000.ts",
      "path": "/public/1221/segment_000.ts",
      "type": "ts",
      "size": "1.20 MB"
    }
  ]
}
```

## 贡献指南

### 代码规范

#### Rust 代码风格
- 遵循 Rust 官方代码风格指南
- 使用 `cargo fmt` 自动格式化代码
- 使用 `cargo clippy` 进行代码质量检查
- 保持函数职责单一，避免过长函数
- 使用有意义的变量和函数命名

#### 注释要求
- 公共 API 必须有文档注释 (`///` 或 `/** */`)
- 复杂逻辑需要添加行内注释
- 函数参数和返回值需要说明
- 错误处理逻辑需要清晰注释

### 开发流程

#### 1. 分支管理
```bash
# 创建功能分支
git checkout -b feature/your-feature-name

# 提交代码
git add .
git commit -m "feat: add your feature"

# 推送分支
git push origin feature/your-feature-name
```

#### 2. 提交信息规范
使用语义化提交信息格式：
```
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建/工具相关
```

#### 3. 代码审查
- 所有代码必须经过审查才能合并
- 确保所有测试通过
- 更新相关文档
- 保持向后兼容性

### 功能扩展建议

#### 短期目标
1. **视频元数据增强**: 集成 ffprobe 获取完整视频信息（时长、分辨率、编码）
2. **缩略图生成**: 使用 ffmpeg 自动生成视频缩略图
3. **搜索功能**: 按名称、类型、时间搜索视频
4. **分页支持**: 大量视频时的分页处理

#### 中期目标
1. **视频转码**: 支持自动转码不同格式
2. **缓存机制**: 缓存目录扫描结果提升性能
3. **用户认证**: 添加用户登录和权限控制
4. **上传功能**: 支持视频文件上传

#### 长期目标
1. **视频编辑**: 在线视频剪辑和处理
2. **直播推流**: 支持实时视频流
3. **分布式部署**: 支持多节点部署
4. **Web 管理界面**: 完整的 Web 管理后台

### 报告问题

如果您在使用过程中遇到问题，请通过以下方式报告：

1. **错误日志**: 提供完整的错误信息和日志
2. **复现步骤**: 详细描述问题复现步骤
3. **环境信息**: 操作系统、Rust 版本等
4. **预期行为**: 说明期望的结果
5. **实际行为**: 说明实际发生的情况

## 许可证信息

本项目采用 **MIT License** 开源许可证。

### MIT License 内容

```
MIT License

Copyright (c) [年份] [版权持有人]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### 使用条款

1. **商业使用**: 允许免费用于商业项目
2. **修改**: 允许自由修改源代码
3. **分发**: 允许分发修改后的版本
4. **私有使用**: 允许私有使用和修改
5. **免责声明**: 不提供任何担保，使用风险自负

### 依赖许可证

本项目依赖的第三方库均采用兼容的开源许可证：

- **Axum**: MIT License
- **Tokio**: MIT License
- **Tower-HTTP**: MIT License
- **Serde**: MIT/Apache-2.0 Dual License
- **WalkDir**: MIT License

## 常见问题

### Q: 服务器启动失败怎么办？
A: 检查端口是否被占用，确保 `public` 目录存在且有读取权限。

### Q: 如何修改服务器端口？
A: 在 `main.rs` 中修改 `SocketAddr` 的端口号，重新编译运行。

### Q: 支持哪些视频格式？
A: 目前支持 MP4、M3U8、TS 格式，以及 VTT、SRT 字幕文件。

### Q: 如何添加视频文件？
A: 直接将视频文件复制到 `public` 目录下，服务器会自动扫描。

### Q: HLS 流媒体如何使用？
A: 将 HLS 相关文件（m3u8、ts）放入单独目录，服务器会自动识别为 HLS 目录。

### Q: 如何提高性能？
A: 使用 `cargo run --release` 运行优化版本，或考虑使用 CDN 加速静态文件。

## 联系与支持

如有技术问题或建议，请通过以下方式联系：

- **项目地址**: 查看项目仓库
- **问题反馈**: 通过 Issue 系统提交
- **技术讨论**: 欢迎提交 Pull Request

---

**版本**: 1.0.0  
**最后更新**: 2026-01-05  
**状态**: ✅ 生产环境就绪