"use client"

import { Play, Clock } from "lucide-react"
import { Card } from "@/components/ui/card"
import type { MediaItem } from "@/types/media"

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
      className="overflow-hidden cursor-pointer hover:ring-2 hover:ring-accent transition-all active:scale-98"
      onClick={onClick}
    >
      {/* 缩略图区域 */}
      <div className="relative aspect-video bg-muted">
        {video.thumbnail ? (
          <img src={video.thumbnail || "/placeholder.svg"} alt={video.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-accent/20 to-accent/5">
            <Play className="w-12 h-12 text-accent/40" />
          </div>
        )}

        {/* 时长标签 */}
        {video.duration && (
          <div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDuration(video.duration)}
          </div>
        )}

        {/* 格式标签 */}
        <div className="absolute top-2 left-2 bg-accent text-accent-foreground text-xs font-semibold px-2 py-1 rounded">
          {getVideoTypeLabel(video.type)}
        </div>

        {/* 播放覆盖层 */}
        <div className="absolute inset-0 bg-black/0 hover:bg-black/30 transition-colors flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
            <Play className="w-6 h-6 text-black fill-black ml-0.5" />
          </div>
        </div>
      </div>

      {/* 信息区域 */}
      <div className="p-4 space-y-2">
        <h3 className="font-semibold text-base line-clamp-2 leading-snug">{video.name}</h3>

        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {video.resolution && <span className="bg-secondary px-2 py-1 rounded">{video.resolution}</span>}
          {video.size && <span className="bg-secondary px-2 py-1 rounded">{video.size}</span>}
          {video.bitrate && <span className="bg-secondary px-2 py-1 rounded">{video.bitrate}</span>}
        </div>

        {video.createdAt && <p className="text-xs text-muted-foreground">{video.createdAt}</p>}
      </div>
    </Card>
  )
}
