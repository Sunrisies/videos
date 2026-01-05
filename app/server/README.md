# 视频文件服务器

一个基于 Axum 框架的高性能视频文件服务器，支持 MP4 和 HLS 格式的视频文件。

## 功能特性

- 🎯 **自动视频发现**: 自动扫描 `public` 目录下的视频文件和目录
- 📹 **多格式支持**: 支持 MP4 直播视频和 HLS (m3u8) 流媒体格式
- 🔍 **智能目录识别**: 自动识别包含视频文件的目录结构
- 📱 **RESTful API**: 提供简洁的 API 接口获取视频列表和详情
- 🚀 **高性能**: 基于 Axum 和 Tokio 的异步高性能架构
- 📂 **静态文件服务**: 直接通过 URL 访问视频文件
- 📊 **丰富元数据**: 提供视频文件的详细信息（大小、创建时间、缩略图等）

## 项目结构

```
public/
├── video1.mp4              # MP4 视频文件
├── video2.mp4
├── hls_stream/             # HLS 流媒体目录
│   ├── index.m3u8
│   ├── segment_000.ts
│   ├── segment_001.ts
│   └── ...
├── video3.mp4
└── subtitles/              # 字幕文件目录
    ├── video3.vtt
    └── video3.srt
```

## API 接口

### 1. 获取视频列表
```
GET /api/videos
```

返回第一层所有视频文件和目录：

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
      "name": "hls_stream",
      "path": "/public/hls_stream",
      "type": "hls_directory",
      "created_at": "2025-09-20 10:59:49",
      "children": [...]
    }
  ]
}
```

### 2. 获取视频详情
```
GET /api/videos/{path}
```

获取指定路径的详细信息，包括子文件（最多递归2层）：

```json
{
  "name": "hls_stream",
  "path": "/public/hls_stream",
  "type": "hls_directory",
  "created_at": "2025-09-20 10:59:49",
  "children": [
    {
      "name": "index.m3u8",
      "path": "/public/hls_stream/index.m3u8",
      "type": "m3u8",
      "size": "2.50 KB"
    },
    {
      "name": "segment_000.ts",
      "path": "/public/hls_stream/segment_000.ts",
      "type": "ts",
      "size": "1.20 MB"
    }
  ]
}
```

### 3. 访问静态视频文件
```
GET /public/{filename}
```

直接访问 public 目录下的视频文件，例如：
- `GET /public/video1.mp4`
- `GET /public/hls_stream/index.m3u8`
- `GET /public/subtitles/video3.vtt`

## 视频类型说明

| 类型 | 说明 |
|------|------|
| `mp4` | MP4 视频文件 |
| `m3u8` | HLS 播放列表文件 |
| `ts` | HLS 视频分片文件 |
| `subtitle` | 字幕文件（vtt/srt） |
| `hls_directory` | 包含 m3u8 文件的目录（HLS 流媒体） |
| `directory` | 包含视频文件的普通目录 |
| `unknown` | 其他文件类型 |

## 视频元数据字段

每个视频信息对象包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 文件/目录名称 |
| `path` | string | 访问路径（以 /public/ 开头） |
| `type` | string | 视频类型 |
| `children` | array | 子文件/目录（仅目录有效） |
| `thumbnail` | string | 缩略图路径（仅 MP4 有效） |
| `duration` | number | 视频时长（秒，暂未实现） |
| `size` | string | 文件大小（格式化显示） |
| `resolution` | string | 视频分辨率（如 "1920x1080"，暂未实现） |
| `bitrate` | string | 比特率（如 "2000kbps"，暂未实现） |
| `codec` | string | 编码格式（如 "H.264"，暂未实现） |
| `created_at` | string | 创建时间（格式：YYYY-MM-DD HH:MM:SS） |
| `subtitle` | string | 字幕文件路径（仅字幕文件有效） |

## 运行方式

### 1. 安装依赖
```bash
cargo build
```

### 2. 运行服务器
```bash
cargo run
```

服务器将在 `0.0.0.0:3000` 启动。

### 3. 访问服务
- API 列表: `http://localhost:3000/api/videos`
- 视频详情: `http://localhost:3000/api/videos/{path}`
- 静态文件: `http://localhost:3000/public/{filename}`

## 依赖说明

- **axum**: 高性能 Web 框架
- **tokio**: 异步运行时
- **tower-http**: HTTP 服务中间件（静态文件服务）
- **walkdir**: 目录遍历
- **serde**: JSON 序列化

## 优化亮点

1. **代码结构清晰**: 模块化设计，函数职责单一
2. **错误处理完善**: 使用 Result 类型和适当的 HTTP 状态码
3. **性能优化**: 使用 walkdir 高效遍历目录，支持深度控制
4. **类型安全**: 完整的类型定义和编译时检查
5. **扩展性强**: 易于添加新的视频格式或功能
6. **丰富元数据**: 提供文件大小、创建时间等详细信息

## 使用示例

### 前端调用示例
```javascript
// 获取视频列表
const response = await fetch('/api/videos');
const data = await response.json();

// 显示视频列表
data.videos.forEach(video => {
  if (video.type === 'mp4') {
    // 播放 MP4 视频
    const videoElement = document.createElement('video');
    videoElement.src = video.path;
    videoElement.controls = true;
    
    // 显示元数据
    console.log(`视频: ${video.name}`);
    console.log(`大小: ${video.size}`);
    console.log(`创建时间: ${video.created_at}`);
    
    if (video.thumbnail) {
      // 显示缩略图
      const img = document.createElement('img');
      img.src = video.thumbnail;
      img.alt = video.name;
      document.body.appendChild(img);
    }
    
    document.body.appendChild(videoElement);
  } else if (video.type === 'hls_directory') {
    // 处理 HLS 流媒体
    console.log('HLS stream:', video.name);
    console.log('子文件数量:', video.children?.length || 0);
  }
});

// 获取视频详情
const detailResponse = await fetch('/api/videos/1221');
const detailData = await detailResponse.json();
console.log('视频详情:', detailData);
```

### 字幕文件处理
```javascript
// 检查是否有字幕
if (video.subtitle) {
  // 使用 WebVTT 字幕
  const track = document.createElement('track');
  track.kind = 'subtitles';
  track.label = '中文';
  track.srclang = 'zh';
  track.src = video.subtitle;
  track.default = true;
  videoElement.appendChild(track);
}
```

## 注意事项

1. 确保 `public` 目录存在且有适当的读取权限
2. 服务器监听在所有网络接口（0.0.0.0），可根据需要修改
3. 目前支持的视频格式：MP4, M3U8, TS, VTT, SRT
4. 目录扫描深度可通过参数调整
5. MP4 文件的详细元数据（时长、分辨率、编码）需要集成 ffprobe 等工具
6. 缩略图功能需要预先生成同名的 .jpg 文件

## 扩展建议

1. **视频分析**: 集成 ffprobe 获取完整的视频元数据
2. **缩略图生成**: 使用 ffmpeg 自动生成视频缩略图
3. **视频转码**: 支持自动转码不同格式
4. **分页支持**: 大量视频时的分页处理
5. **搜索功能**: 按名称、类型、时间搜索视频
6. **权限控制**: 添加用户认证和访问控制
7. **缓存机制**: 缓存目录扫描结果提升性能