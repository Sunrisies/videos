"use client"

import { useState } from "react"
import { MediaPlayer } from "@/components/media-player"
import { Card } from "@/components/ui/card"

// 模拟后端返回的数据
const mockMediaData = {
  videos: [
    {
      name: "示例视频 1",
      path: "/videos/sample1.mp4",
      type: "mp4",
      thumbnail: "/video-thumbnail.png",
      duration: 120,
      size: "25MB",
    },
    {
      name: "HLS流媒体示例",
      path: "/public/1221",
      type: "hls_directory",
      thumbnail: "/streaming-video.jpg",
      duration: 180,
    },
    {
      name: "示例视频 2",
      path: "/videos/sample2.mp4",
      type: "mp4",
    },
  ],
  audios: [
    {
      name: "示例音频 1.mp3",
      path: "/audios/sample1.mp3",
      type: "mp3",
      duration: 240,
      size: "5MB",
    },
    {
      name: "示例音频 2.wav",
      path: "/audios/sample2.wav",
      type: "wav",
      duration: 180,
    },
  ],
}

export default function MediaPage() {
  const [selectedMedia, setSelectedMedia] = useState(mockMediaData.videos[0])

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div>
        <h1 className="text-4xl font-bold mb-2">多媒体播放器</h1>
        <p className="text-muted-foreground">支持 MP4、WebM、HLS流媒体、MP3、WAV等多种格式</p>
      </div>

      {/* 播放器区域 */}
      <div className="max-w-4xl mx-auto">
        <MediaPlayer media={selectedMedia} />
      </div>

      {/* 媒体列表 */}
      <div className="grid gap-6">
        {/* 视频列表 */}
        <div>
          <h2 className="text-2xl font-semibold mb-4">视频列表</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {mockMediaData.videos.map((video, index) => (
              <Card
                key={index}
                className="cursor-pointer hover:shadow-lg transition-shadow overflow-hidden"
                onClick={() => setSelectedMedia(video)}
              >
                <div className="aspect-video bg-muted relative">
                  {video.thumbnail ? (
                    <img
                      src={video.thumbnail || "/placeholder.svg"}
                      alt={video.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground">无缩略图</div>
                  )}
                  <div className="absolute top-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                    {video.type.toUpperCase()}
                  </div>
                </div>
                <div className="p-4">
                  <p className="font-medium truncate">{video.name}</p>
                  <div className="flex justify-between text-sm text-muted-foreground mt-1">
                    {video.duration && <span>{Math.floor(video.duration / 60)}分钟</span>}
                    {video.size && <span>{video.size}</span>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* 音频列表 */}
        <div>
          <h2 className="text-2xl font-semibold mb-4">音频列表</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {mockMediaData.audios.map((audio, index) => (
              <Card
                key={index}
                className="cursor-pointer hover:shadow-lg transition-shadow overflow-hidden"
                onClick={() => setSelectedMedia(audio)}
              >
                <div className="aspect-video bg-muted flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center mb-2">
                      <span className="text-2xl">🎵</span>
                    </div>
                    <div className="text-xs text-muted-foreground">{audio.type.toUpperCase()}</div>
                  </div>
                </div>
                <div className="p-4">
                  <p className="font-medium truncate">{audio.name}</p>
                  <div className="flex justify-between text-sm text-muted-foreground mt-1">
                    {audio.duration && <span>{Math.floor(audio.duration / 60)}分钟</span>}
                    {audio.size && <span>{audio.size}</span>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* 使用说明 */}
      <Card className="p-6 bg-muted/50">
        <h3 className="text-lg font-semibold mb-3">实现说明</h3>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li>✅ 支持MP4、WebM等常规视频格式（使用原生HTML5 video标签）</li>
          <li>✅ 支持HLS流媒体播放（使用HLS.js库，Safari原生支持）</li>
          <li>✅ 支持MP3、WAV等音频格式（使用原生HTML5 audio标签）</li>
          <li>✅ 统一的播放控制界面（播放/暂停、音量、进度条、全屏）</li>
          <li>✅ 根据type字段自动识别并选择合适的播放器</li>
          <li>✅ 响应式设计，支持移动端</li>
        </ul>
      </Card>
    </div>
  )
}
