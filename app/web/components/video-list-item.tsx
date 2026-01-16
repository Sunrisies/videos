"use client"

import { Play, Clock } from "lucide-react"
import { Card } from "@/components/ui/card"
import type { MediaItem } from "@/types/media"
import Image from "next/image"
interface VideoListItemProps {
  video: MediaItem
  onClick: () => void
}

export function VideoListItem({ video, onClick }: VideoListItemProps) {
  const formatDuration = (seconds?: number) => {
    if (!seconds) return ""
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const getVideoTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      mp4: "MP4",
      webm: "WebM",
      ogv: "OGV",
      hls_directory: "HLS",
      m3u8: "HLS",
    }
    return typeMap[type.toLowerCase()] || type.toUpperCase()
  }

  return (
    <Card
      className="group overflow-hidden cursor-pointer p-0 transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-xl active:scale-95"
      onClick={onClick}
    >
      {/* 缩略图区域 */}
      <div className="relative aspect-video bg-muted overflow-hidden">
        {video.thumbnail ? (
          <div className="relative w-full h-full transition-transform duration-500 group-hover:scale-105">
            <Image
              src={`http://192.168.10.4:3003\\${video.thumbnail}`}
              alt={video.name}
              fill={true}
              unoptimized={true}
              className="object-cover"
            />
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-accent/20 to-accent/5">
            <Play className="w-12 h-12 text-accent/40" />
          </div>
        )}

        {/* 悬浮时的播放覆盖层 - 优化动画 */}
        <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-colors duration-300 flex items-center justify-center">
          <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center opacity-0 scale-50 group-hover:opacity-100 group-hover:scale-100 transition-all duration-300 ease-out shadow-lg backdrop-blur-sm">
            <Play className="w-6 h-6 text-black fill-black ml-1" />
          </div>
        </div>

        {/* 时长标签 - 添加悬浮上移效果 */}
        {video.duration && (
          <div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded flex items-center gap-1 transition-transform duration-300 group-hover:translate-y-[-2px]">
            <Clock className="w-3 h-3" />
            {video.duration}
          </div>
        )}

        {/* 格式标签 - 添加悬浮上移效果 */}
        <div className="absolute top-2 left-2 bg-accent text-accent-foreground text-xs font-semibold px-2 py-1 rounded transition-transform duration-300 group-hover:translate-y-[-2px]">
          {getVideoTypeLabel(video.type)}
        </div>
      </div>

      {/* 信息区域 */}
      <div className="p-4 space-y-2">
        <h3 className="font-semibold text-base line-clamp-2 leading-snug transition-colors duration-200 group-hover:text-primary">
          {video.name}
        </h3>

        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {video.resolution && <span className="bg-secondary px-2 py-1 rounded transition-colors group-hover:bg-secondary/80">{video.resolution}</span>}
          {video.size && <span className="bg-secondary px-2 py-1 rounded transition-colors group-hover:bg-secondary/80">{video.size}</span>}
          {video.bitrate && <span className="bg-secondary px-2 py-1 rounded transition-colors group-hover:bg-secondary/80">{video.bitrate}</span>}
        </div>

        {video.createdAt && <p className="text-xs text-muted-foreground">{video.createdAt}</p>}
      </div>
    </Card>

  )
}
