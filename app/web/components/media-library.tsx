"use client"

import { useState } from "react"
import { Play, Video, Music, Radio } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { MediaItem } from "@/types/media"
import { getMediaType, formatFileSize } from "@/lib/media-utils"

interface MediaLibraryProps {
  items: MediaItem[]
  onSelect: (item: MediaItem) => void
  selectedItem?: MediaItem
}

export function MediaLibrary({ items, onSelect, selectedItem }: MediaLibraryProps) {
  const [filter, setFilter] = useState<"all" | "video" | "audio" | "hls">("all")

  const filteredItems = items.filter((item) => {
    if (filter === "all") return true
    return getMediaType(item.type) === filter
  })

  const getIcon = (type: string) => {
    const mediaType = getMediaType(type)
    switch (mediaType) {
      case "hls":
        return <Radio className="h-5 w-5" />
      case "audio":
        return <Music className="h-5 w-5" />
      default:
        return <Video className="h-5 w-5" />
    }
  }

  const getTypeColor = (type: string) => {
    const mediaType = getMediaType(type)
    switch (mediaType) {
      case "hls":
        return "bg-chart-3 text-white"
      case "audio":
        return "bg-chart-2 text-white"
      default:
        return "bg-chart-1 text-white"
    }
  }

  return (
    <div className="space-y-4">
      {/* 过滤器 */}
      <div className="flex gap-2">
        <Badge
          variant={filter === "all" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setFilter("all")}
        >
          全部 ({items.length})
        </Badge>
        <Badge
          variant={filter === "video" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setFilter("video")}
        >
          视频 ({items.filter((i) => getMediaType(i.type) === "video").length})
        </Badge>
        <Badge
          variant={filter === "audio" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setFilter("audio")}
        >
          音频 ({items.filter((i) => getMediaType(i.type) === "audio").length})
        </Badge>
        <Badge
          variant={filter === "hls" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setFilter("hls")}
        >
          流媒体 ({items.filter((i) => getMediaType(i.type) === "hls").length})
        </Badge>
      </div>

      {/* 媒体网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredItems.map((item, index) => (
          <Card
            key={index}
            className={`cursor-pointer transition-all hover:shadow-lg ${
              selectedItem?.path === item.path ? "ring-2 ring-primary" : ""
            }`}
            onClick={() => onSelect(item)}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className={`p-3 rounded-lg ${getTypeColor(item.type)}`}>{getIcon(item.type)}</div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm truncate" title={item.name}>
                    {item.name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {item.type.toUpperCase()}
                    {item.size && ` • ${formatFileSize(item.size)}`}
                  </p>
                  {item.resolution && <p className="text-xs text-muted-foreground">{item.resolution}</p>}
                </div>
                <Play className="h-5 w-5 text-muted-foreground flex-shrink-0" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredItems.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>暂无媒体文件</p>
        </div>
      )}
    </div>
  )
}
