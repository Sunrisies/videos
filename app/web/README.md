# 多媒体播放解决方案

一个完整的前端多媒体播放系统，支持视频、音频和流媒体格式的自动识别和播放。

## 核心特性

### 1. 自动类型识别
系统根据后端返回的 `type` 字段自动识别媒体类型：
- **视频格式**: MP4, WebM, OGG
- **音频格式**: MP3, WAV, AAC, FLAC, OGG
- **流媒体**: HLS (m3u8)

### 2. 智能播放器选择
- 普通视频/音频 → 原生 HTML5 `<video>` / `<audio>` 标签
- HLS流媒体 → 动态加载 HLS.js 库处理

### 3. 完整的播放控制
- 播放/暂停
- 进度条拖动
- 音量控制和静音
- 全屏模式（视频）
- 时间显示
- 下载功能

## 数据结构

### 当前支持的结构
```typescript
interface MediaItem {
  name: string      // 文件名
  path: string      // 文件路径
  type: string      // 媒体类型（mp4, hls_directory, mp3等）
}
```

### 建议的增强结构
为了提供更好的用户体验，建议后端添加以下可选字段：

```typescript
interface EnhancedMediaItem {
  name: string              // ✅ 必需
  path: string              // ✅ 必需
  type: string              // ✅ 必需
  
  // 建议新增字段：
  thumbnail?: string        // 缩略图URL（视频预览）
  duration?: number         // 时长（秒）
  size?: string            // 文件大小（字节）
  resolution?: string      // 视频分辨率（如 "1920x1080"）
  bitrate?: string         // 比特率（如 "2000kbps"）
  codec?: string           // 编码格式（如 "H.264"）
  createdAt?: string       // 创建时间（ISO格式）
  subtitle?: string        // 字幕文件路径
}
```

## 使用方法

### 1. 环境配置

首先，创建 `.env.local` 文件配置 API 地址：

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:3000
```

如果没有配置，默认使用 `http://localhost:3000` 作为 API 地址。

### 2. 基础集成

```tsx
import { MediaPlayer } from "@/components/media-player"

const media = {
  name: "示例视频.mp4",
  path: "/videos/example.mp4",
  type: "mp4"
}

<MediaPlayer media={media} autoPlay={false} />
```

### 3. 与API集成

```tsx
"use client"

import { useEffect, useState } from "react"
import { MediaPlayer } from "@/components/media-player"

export default function MediaPage() {
  const [media, setMedia] = useState(null)

  useEffect(() => {
    // 从后端获取媒体数据
    fetch("/api/media")
      .then(res => res.json())
      .then(data => setMedia(data.videos[0]))
  }, [])

  if (!media) return <div>加载中...</div>

  return <MediaPlayer media={media} />
}
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd d:\project\project\videos\app\web
npm install
# 或
pnpm install
# 或
yarn install
```

### 2. 配置环境变量

创建 `.env.local` 文件：

```bash
# Server API 地址
NEXT_PUBLIC_API_URL=http://localhost:3000
```

### 3. 启动开发服务器

```bash
npm run dev
# 或
pnpm dev
# 或
yarn dev
```

应用将在 `http://localhost:3001` 启动（端口可能不同）。

### 4. 构建生产版本

```bash
npm run build
npm start
```

## 🔗 与 Server 集成

### API 调用示例

前端通过环境变量配置的 API 地址访问 Server：

```typescript
// lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000'

export async function getVideos() {
  const response = await fetch(`${API_URL}/api/videos`)
  if (!response.ok) throw new Error('Failed to fetch videos')
  return response.json()
}

export async function getVideoDetail(path: string) {
  const response = await fetch(`${API_URL}/api/videos/${path}`)
  if (!response.ok) throw new Error('Failed to fetch video detail')
  return response.json()
}
```

### 完整工作流程

1. **Downloader 下载** → 视频保存到 `server/public`
2. **Server 提供 API** → 扫描 public 目录并提供 RESTful API
3. **Web 获取列表** → 从 Server API 获取视频列表
4. **播放视频** → 使用 MediaPlayer 组件播放

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `NEXT_PUBLIC_API_URL` | Server API 地址 | `http://localhost:3000` |

## 技术实现

### 媒体类型判断逻辑

```typescript
function getMediaType(type: string): "video" | "audio" | "hls" {
  const lowerType = type.toLowerCase()

  // HLS流媒体
  if (lowerType.includes("hls") || lowerType === "m3u8") {
    return "hls"
  }

  // 音频格式
  if (["mp3", "wav", "aac", "flac", "ogg"].includes(lowerType)) {
    return "audio"
  }

  // 默认为视频
  return "video"
}
```

### HLS支持

系统自动检测浏览器对HLS的支持：
- 现代浏览器 → 使用 hls.js
- Safari → 使用原生HLS支持

## 项目结构

```
├── app/
│   ├── page.tsx              # 主页面，展示媒体库和播放器
│   ├── api/
│   │   └── media/
│   │       └── route.ts      # API路由（可选）
│   └── globals.css           # 全局样式
├── components/
│   ├── media-player.tsx      # 核心播放器组件
│   └── media-library.tsx     # 媒体库列表组件
├── types/
│   └── media.ts              # TypeScript类型定义
└── lib/
    └── media-utils.ts        # 工具函数
```

## 优势

1. **零配置启动** - 开箱即用，无需复杂配置
2. **自动适配** - 根据媒体类型自动选择最佳播放方案
3. **原生性能** - 充分利用浏览器原生能力
4. **扩展友好** - 清晰的组件结构，易于自定义和扩展
5. **响应式设计** - 完美支持移动端和桌面端

## 浏览器兼容性

- Chrome/Edge: ✅ 完全支持
- Firefox: ✅ 完全支持
- Safari: ✅ 完全支持（原生HLS）
- 移动浏览器: ✅ 完全支持
