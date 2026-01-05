"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { MobileVideoPlayer } from "@/components/mobile-video-player"
import { Button } from "@/components/ui/button"
import { ChevronLeft, Share2, MoreVertical } from "lucide-react"
import type { MediaItem } from "@/types/media"

export default function VideoPlayPage() {
  const router = useRouter()
  const [video, setVideo] = useState<MediaItem | null>(null)

  useEffect(() => {
    // 从 sessionStorage 获取视频数据
    const storedVideo = sessionStorage.getItem("currentVideo")
    if (storedVideo) {
      setVideo(JSON.parse(storedVideo))
    } else {
      // 如果没有数据，返回列表页
      router.push("/videos")
    }
  }, [router])

  const handleBack = () => {
    router.back()
  }

  const handleShare = () => {
    if (navigator.share && video) {
      navigator.share({
        title: video.name,
        text: `观看视频：${video.name}`,
        url: window.location.href,
      })
    }
  }

  if (!video) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-lg text-muted-foreground">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black">
      {/* 顶部导航栏 */}
      <header className="fixed top-0 left-0 right-0 z-20 bg-black/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <Button size="icon" variant="ghost" onClick={handleBack} className="text-white">
            <ChevronLeft className="w-6 h-6" />
          </Button>

          <div className="flex gap-2">
            <Button size="icon" variant="ghost" onClick={handleShare} className="text-white">
              <Share2 className="w-5 h-5" />
            </Button>
            <Button size="icon" variant="ghost" className="text-white">
              <MoreVertical className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      {/* 视频播放器 */}
      <div className="pt-12">
        <MobileVideoPlayer media={video} autoPlay />
      </div>

      {/* 视频信息 */}
      <div className="bg-background">
        <div className="px-4 py-6 space-y-4">
          <div>
            <h1 className="text-xl font-bold mb-2">{video.name}</h1>
            <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
              {video.resolution && <span>{video.resolution}</span>}
              {video.size && (
                <>
                  <span>·</span>
                  <span>{video.size}</span>
                </>
              )}
              {video.bitrate && (
                <>
                  <span>·</span>
                  <span>{video.bitrate}</span>
                </>
              )}
            </div>
          </div>

          {video.createdAt && <div className="text-sm text-muted-foreground">上传时间：{video.createdAt}</div>}

          {/* 视频描述区域（可扩展） */}
          <div className="border-t pt-4">
            <h3 className="font-semibold mb-2">视频详情</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">格式</span>
                <span className="font-medium">{video.type.toUpperCase()}</span>
              </div>
              {video.duration && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">时长</span>
                  <span className="font-medium">
                    {Math.floor(video.duration / 60)}分{video.duration % 60}秒
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
