"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { VideoListItem } from "@/components/video-list-item"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search, Grid3x3, List } from "lucide-react"
import type { MediaItem } from "@/types/media"

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
}

const getVideos = async (): Promise<MediaItem[]> => {
  const response = await fetch("http://192.168.31.236:3003/api/videos")
  if (!response.ok) {
    throw new Error("Failed to fetch videos")
  }
  const data = await response.json()
  console.log("Fetched videos:", data)
  // API返回的数据结构是 { videos: [...] }，需要提取数组
  const videos = data.videos || []
  console.log('videos', videos)
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
  }))
}

export default function VideosPage() {

  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [filterType, setFilterType] = useState<string>("all")
  const [videos, setVideos] = useState<MediaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        setLoading(true)
        const data = await getVideos()
        setVideos(data)
        setError(null)
      } catch (err) {
        console.error("Error fetching videos:", err)
        setError("无法加载视频数据，请检查服务器连接")
      } finally {
        setLoading(false)
      }
    }

    fetchVideos()
  }, [])

  const filteredVideos = videos.filter((video) => {
    const matchesSearch = video.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === "all" || video.type === filterType
    return matchesSearch && matchesType
  })

  const handleVideoClick = (video: MediaItem) => {
    // 将视频数据存储到 sessionStorage
    sessionStorage.setItem("currentVideo", JSON.stringify(video))
    router.push("/videos/play")
  }

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* 顶部导航栏 */}
      <header className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold mb-3">视频库</h1>

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
        {loading ? (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3"></div>
            <p className="text-lg text-muted-foreground">正在加载视频...</p>
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-lg text-red-600 mb-2">错误</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button
              className="mt-4"
              onClick={() => {
                setLoading(true)
                getVideos().then(setVideos).catch(() => {
                  setError("无法加载视频数据，请检查服务器连接")
                }).finally(() => setLoading(false))
              }}
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
            <div className="mb-4 text-sm text-muted-foreground">找到 {filteredVideos.length} 个视频</div>
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
