"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { MobileVideoPlayer } from "@/components/mobile-video-player"
import { Button } from "@/components/ui/button"
import { ChevronLeft, Share2, MoreVertical, HardDrive, Clock, FileVideo, Film } from "lucide-react"
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
    <div className="h-[90vh] bg-background flex flex-col">
      <header className="fixed top-0 left-0 right-0 z-20 bg-gradient-to-b from-black/90 to-black/60 backdrop-blur-md">
        <div className="flex items-center justify-between px-3 py-3 safe-area-top">
          <Button
            size="icon"
            variant="ghost"
            onClick={ handleBack }
            className="text-white hover:bg-white/10 active:bg-white/20 transition-colors h-10 w-10"
          >
            <ChevronLeft className="w-6 h-6" />
          </Button>

          <div className="flex gap-1">
            <Button
              size="icon"
              variant="ghost"
              onClick={ handleShare }
              className="text-white hover:bg-white/10 active:bg-white/20 transition-colors h-10 w-10"
            >
              <Share2 className="w-5 h-5" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="text-white hover:bg-white/10 active:bg-white/20 transition-colors h-10 w-10"
            >
              <MoreVertical className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center  ">
        <div className="w-full max-w-3xl">
          <MobileVideoPlayer media={ video } autoPlay />
        </div>
      </div>

      <div className="bg-gradient-to-t from-background to-muted/20 border-t overflow-y-auto max-h-[55vh]">
        <div className="px-4 py-6 space-y-6">
          <div className="space-y-3">
            <h1 className="text-2xl font-bold leading-tight text-balance">{ video.name }</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              { video.resolution && (
                <span className="px-2.5 py-1 bg-primary/10 text-primary rounded-full font-medium">
                  { video.resolution }
                </span>
              ) }
              { video.size && <span className="px-2.5 py-1 bg-muted rounded-full">{ video.size }</span> }
              { video.bitrate && <span className="px-2.5 py-1 bg-muted rounded-full">{ video.bitrate }</span> }
            </div>
          </div>

          { video.createdAt && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="w-4 h-4" />
              <span>上传时间：{ video.createdAt }</span>
            </div>
          ) }

          <div className="bg-card border rounded-xl overflow-hidden shadow-sm">
            <div className="px-4 py-3 border-b bg-muted/30">
              <h3 className="font-semibold flex items-center gap-2">
                <FileVideo className="w-4 h-4" />
                视频详情
              </h3>
            </div>
            <div className="divide-y">
              <div className="px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Film className="w-4 h-4" />
                  <span className="text-sm">格式</span>
                </div>
                <span className="font-semibold text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">
                  { video.type.toUpperCase() }
                </span>
              </div>
              { video.duration && (
                <div className="px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="w-4 h-4" />
                    <span className="text-sm">时长</span>
                  </div>
                  <span className="font-medium text-sm">
                    { Math.floor(video.duration / 60) }:{ (video.duration % 60).toString().padStart(2, "0") }
                  </span>
                </div>
              ) }
              { video.size && (
                <div className="px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <HardDrive className="w-4 h-4" />
                    <span className="text-sm">文件大小</span>
                  </div>
                  <span className="font-medium text-sm">{ video.size }</span>
                </div>
              ) }
            </div>
          </div>

          <div className="h-8" />
        </div>
      </div>
    </div>
  )
}
