"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { VideoListItem } from "@/components/video-list-item"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search, Grid3x3, List, RefreshCw } from "lucide-react"
import type { MediaItem } from "@/types/media"
import { useScrollPosition } from "@/hooks/useScrollPosition"
import { useAuth } from "@/hooks/useAuth"
import { useDataCache } from "@/hooks/useDataCache"

// API返回的视频数据接口
interface ApiVideoItem {
  name: string
  path: string
  type: string
  size?: string
  created_at: string
  thumbnail?: string
  duration?: number
  resolution?: string
  bitrate?: string
  width?: number
  height?: number
}

const fetchVideosFromApi = async (): Promise<MediaItem[]> => {
  const response = await fetch("http://192.168.1.5:3003/api/videos")
  if (!response.ok) {
    throw new Error("Failed to fetch videos")
  }
  const data = await response.json()
  // API返回的数据结构是 { videos: [...] }，需要提取数组
  const videos = data.videos || []
  // 转换字段名以匹配类型定义
  return videos.map((video: ApiVideoItem) => ({
    name: video.name,
    path: video.path,
    type: video.type,
    size: video.size,
    createdAt: video.created_at, // 转换 created_at 到 createdAt
    // 提供默认值，因为API可能不返回这些字段
    thumbnail: video.thumbnail || "/video-thumbnail.png",
    duration: video.duration || 0,
    resolution: video.resolution || "未知",
    bitrate: video.bitrate || "未知",
    width: video.width,
    height: video.height,
  }))
}

export default function VideosPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, requireAuth } = useAuth()
  const [searchQuery, setSearchQuery] = useState("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [filterType, setFilterType] = useState<string>("all")

  // 使用自定义Hook来保存和恢复滚动位置
  const { saveScrollPosition, restoreScrollPosition } = useScrollPosition({ key: "videosPageScrollPosition" })

  // 使用缓存 Hook 获取视频数据
  const {
    data: videos,
    loading,
    error,
    refresh,
    fromCache
  } = useDataCache<MediaItem[]>(
    fetchVideosFromApi,
    {
      cacheKey: "videos-list",
      maxAge: 5 * 60 * 1000, // 5分钟缓存
      backgroundRefresh: true,
    }
  )

  // 路由守卫：检查授权状态
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      requireAuth("/videos")
    }
  }, [authLoading, isAuthenticated, requireAuth])

  // 单独处理滚动位置恢复 - 针对移动端优化
  useEffect(() => {
    if (!loading && videos && videos.length > 0) {
      // 检查是否从播放页面返回
      const isReturningFromPlay = sessionStorage.getItem("returningFromPlay") === "true"

      if (isReturningFromPlay) {
        // 清除标记
        sessionStorage.removeItem("returningFromPlay")

        // 使用多种方式确保滚动位置恢复
        const restoreScroll = () => {
          const savedPosition = sessionStorage.getItem("videosPageScrollPosition");
          if (savedPosition) {
            const position = parseInt(savedPosition, 10);

            // 立即设置滚动位置
            window.scrollTo(0, position);

            // 移动端可能需要多次尝试
            setTimeout(() => {
              window.scrollTo(0, position);
            }, 50);

            setTimeout(() => {
              window.scrollTo(0, position);
            }, 100);

            setTimeout(() => {
              window.scrollTo(0, position);
              // 清除保存的位置
              sessionStorage.removeItem("videosPageScrollPosition");
            }, 200);
          }
        };

        // 等待页面完全渲染
        if (document.readyState === 'complete') {
          restoreScroll();
        } else {
          window.addEventListener('load', restoreScroll, { once: true });
          // 额外的延迟作为后备
          setTimeout(restoreScroll, 300);
        }
      }
    }
  }, [loading, videos])

  const filteredVideos = (videos || []).filter((video) => {
    const matchesSearch = video.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === "all" || video.type === filterType
    return matchesSearch && matchesType
  })

  const handleVideoClick = (video: MediaItem) => {
    // 保存当前滚动位置到sessionStorage
    const scrollPosition = window.scrollY;
    sessionStorage.setItem("videosPageScrollPosition", scrollPosition.toString());

    // 将视频数据存储到 sessionStorage
    sessionStorage.setItem("currentVideo", JSON.stringify(video))
    router.push("/videos/play")
  }

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* 顶部导航栏 */}
      <header className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-2xl font-bold">视频库</h1>
            <Button
              size="icon"
              variant="ghost"
              onClick={refresh}
              disabled={loading}
              title="刷新列表"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* 搜索栏 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="搜索视频..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 h-12"
            />
          </div>

          {/* 筛选和视图切换 */}
          <div className="flex items-center justify-between mt-3 gap-2">
            <div className="flex gap-2 overflow-x-auto pb-1">
              <Button
                size="sm"
                variant={filterType === "all" ? "default" : "secondary"}
                onClick={() => setFilterType("all")}
              >
                全部
              </Button>
              <Button
                size="sm"
                variant={filterType === "mp4" ? "default" : "secondary"}
                onClick={() => setFilterType("mp4")}
              >
                MP4
              </Button>
              <Button
                size="sm"
                variant={filterType === "webm" ? "default" : "secondary"}
                onClick={() => setFilterType("webm")}
              >
                WebM
              </Button>
              <Button
                size="sm"
                variant={filterType === "hls_directory" ? "default" : "secondary"}
                onClick={() => setFilterType("hls_directory")}
              >
                HLS
              </Button>
            </div>

            <div className="flex gap-1 shrink-0">
              <Button
                size="icon"
                variant={viewMode === "grid" ? "default" : "ghost"}
                onClick={() => setViewMode("grid")}
              >
                <Grid3x3 className="w-5 h-5" />
              </Button>
              <Button
                size="icon"
                variant={viewMode === "list" ? "default" : "ghost"}
                onClick={() => setViewMode("list")}
              >
                <List className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 视频列表 */}
      <main className="container mx-auto px-4 py-6">
        {loading && !videos ? (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3"></div>
            <p className="text-lg text-muted-foreground">正在加载视频...</p>
          </div>
        ) : error && !videos ? (
          <div className="text-center py-20">
            <p className="text-lg text-red-600 mb-2">错误</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button
              className="mt-4"
              onClick={refresh}
            >
              重试
            </Button>
          </div>
        ) : filteredVideos.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-lg text-muted-foreground mb-2">未找到视频</p>
            <p className="text-sm text-muted-foreground">尝试调整搜索条件或筛选器</p>
          </div>
        ) : (
          <>
            <div className="mb-4 text-sm text-muted-foreground flex items-center gap-2">
              <span>找到 {filteredVideos.length} 个视频</span>
              {fromCache && (
                <span className="text-xs px-2 py-0.5 bg-secondary rounded-full">缓存</span>
              )}
            </div>
            <div className={viewMode === "grid" ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" : "space-y-4"}>
              {filteredVideos.map((video, index) => (
                <VideoListItem key={index} video={video} onClick={() => handleVideoClick(video)} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
