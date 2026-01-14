"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { MobileVideoPlayer } from "@/components/mobile-video-player"
import { Button } from "@/components/ui/button"
import { ChevronLeft, Share2, Clock, FileVideo, Download, Fullscreen } from "lucide-react"
import type { MediaItem } from "@/types/media"
import { useAuth } from "@/hooks/useAuth"

// 判断是否为竖屏视频
function isVerticalVideo(width?: number, height?: number): boolean {
  if (!width || !height) return false
  return height > width
}

// 视频信息卡片组件
function VideoInfoCard({ video }: { video: MediaItem }) {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
      <div className="p-4 space-y-3">
        {/* 标签和元数据 */}
        <div className="flex flex-wrap items-center gap-2">
          {video.width && video.height && (
            <span className="px-2.5 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full">
              {video.width}x{video.height}
            </span>
          )}
          {video.type && (
            <span className="px-2.5 py-1 bg-secondary text-secondary-foreground text-xs font-medium rounded-full uppercase">
              {video.type}
            </span>
          )}
          {video.size && (
            <span className="px-2.5 py-1 bg-muted text-muted-foreground text-xs font-medium rounded-full">
              {video.size}
            </span>
          )}
        </div>

        {/* 详细信息 */}
        <div className="flex flex-col gap-2 text-sm">
          {video.duration && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">时长:</span>
              <span className="font-medium">{video.duration}</span>
            </div>
          )}
          {video.createdAt && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">上传时间:</span>
              <span className="font-medium truncate">{video.createdAt}</span>
            </div>
          )}
        </div>

        {/* 文件信息 */}
        <div className="pt-3 border-t border-border/50">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <FileVideo className="w-3.5 h-3.5" />
            <span className="font-mono truncate">{video.path.split('\\').pop() || video.name}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function VideoPlayPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, requireAuth } = useAuth()
  const [video, setVideo] = useState<MediaItem | null>(null)

  // 路由守卫：检查授权状态
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      requireAuth("/videos/play")
    }
  }, [authLoading, isAuthenticated, requireAuth])

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

  // 页面卸载时确保设置返回标记
  useEffect(() => {
    return () => {
      // 在组件卸载时设置返回标记，确保移动端也能正确处理
      sessionStorage.setItem("returningFromPlay", "true")
    }
  }, [])

  const handleBack = () => {
    // 先设置标记，再导航
    sessionStorage.setItem("returningFromPlay", "true")
    // 使用 replace 而不是 push，避免在播放页面历史记录堆积
    router.replace("/videos")
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
    <div className="min-h-screen bg-background">
      {/* 顶部导航栏 - 优化为毛玻璃效果 */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-lg border-b border-border/50">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between safe-area-top">
          <Button
            size="icon"
            variant="ghost"
            onClick={handleBack}
            className="h-10 w-10 hover:bg-accent transition-colors"
          >
            <ChevronLeft className="w-6 h-6" />
          </Button>

          {/* 标题 - 支持滚动和截断 */}
          <div className="flex-1 mx-3 overflow-hidden">
            <h1 className="text-base font-semibold text-foreground truncate text-center">
              {video.name}
            </h1>
          </div>

          <div className="flex gap-1">
            <Button
              size="icon"
              variant="ghost"
              onClick={handleShare}
              className="h-10 w-10 hover:bg-accent transition-colors"
            >
              <Share2 className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <div className="pt-[60px] pb-[80px]">
        {/* 根据视频方向选择不同布局 */}
        {isVerticalVideo(video.width, video.height) ? (
          // 竖屏视频布局：大屏并排，小屏堆叠
          <div className="container mx-auto px-4 py-4">
            <div className="flex flex-col md:flex-row gap-4 md:gap-6 items-start justify-center">
              {/* 竖屏视频播放器 */}
              <div className="w-full md:w-auto flex justify-center">
                <div
                  className="relative rounded-xl overflow-hidden shadow-lg border border-border/50 bg-black w-full"
                  style={{ maxWidth: '400px' }}
                >
                  <MobileVideoPlayer media={video} autoPlay />
                </div>
              </div>

              {/* 竖屏视频信息卡片 */}
              <div className="w-full md:flex-1 md:max-w-sm">
                <VideoInfoCard video={video} />
              </div>
            </div>
          </div>
        ) : (
          // 横屏视频布局：标准堆叠布局
          <div className="container mx-auto px-4 py-4">
            <div className="relative rounded-xl overflow-hidden shadow-lg border border-border/50">
              <MobileVideoPlayer media={video} autoPlay />
            </div>
            <div className="mt-4">
              <VideoInfoCard video={video} />
            </div>
          </div>
        )}
      </div>

      {/* 底部安全区域 */}
      <div className="fixed bottom-0 left-0 right-0 h-[env(safe-area-inset-bottom)] bg-background" />
    </div>
  )
}
