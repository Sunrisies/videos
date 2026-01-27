"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { VideoListItem } from "@/components/video-list-item"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search, Grid3x3, List, RefreshCw } from "lucide-react"
import type { MediaItem } from "@/types/media"
import { useScrollPosition } from "@/hooks/useScrollPosition"
import { useAuth } from "@/hooks/useAuth"
import { useDataCache } from "@/hooks/useDataCache"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

// API返回的视频数据接口
interface ApiVideoItem {
  id?: string | number
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
  parent_path?: string
}

// 分页响应接口
// 分页响应接口
interface PaginatedResponse {
  videos: ApiVideoItem[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}


const fetchVideosFromApi = async (page: number = 1, pageSize: number = 20): Promise<{ videos: MediaItem[], total: number, totalPages: number }> => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_APP_IP}:3003/api/videos/paginated?page_size=${pageSize}&page=${page}`)
  if (!response.ok) {
    throw new Error("Failed to fetch videos")
  }
  const data: PaginatedResponse = await response.json()
  console.log(data, 'data')
  // 转换字段名以匹配类型定义
  const videos = data.videos.map((video: ApiVideoItem) => ({
    id: video.id,
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
    parent_path: video.parent_path || ""
  }))

  return {
    videos,
    total: data.pagination.total,
    totalPages: data.pagination.total_pages
  }
}

export default function VideosPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading: authLoading, requireAuth } = useAuth()
  const [searchQuery, setSearchQuery] = useState("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [filterType, setFilterType] = useState<string>("all")
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [totalVideos, setTotalVideos] = useState(0)
  const pageSize = 20
  const [video, setVideo] = useState<MediaItem | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)


  // 使用自定义Hook来保存和恢复滚动位置
  const { saveScrollPosition, restoreScrollPosition } = useScrollPosition({ key: "videosPageScrollPosition" })

  // 从 URL 查询参数中获取当前页码
  useEffect(() => {
    const pageParam = searchParams.get("page")
    if (pageParam) {
      const page = parseInt(pageParam, 10)
      console.log(page, 'page')
      if (page >= 1) {
        setCurrentPage(page)
      }
    }
  }, [searchParams])

  // 使用缓存 Hook 获取视频数据
  const {
    data: paginatedData,
    loading,
    error,
    refresh,
    fromCache
  } = useDataCache<{ videos: MediaItem[], total: number, totalPages: number }>(
    () => fetchVideosFromApi(currentPage, pageSize),
    {
      cacheKey: `videos-list-${currentPage}`,
      maxAge: 5 * 60 * 1000, // 5分钟缓存
      backgroundRefresh: true,
    }
  )

  // 从分页数据中提取视频列表和分页信息
  const videos = paginatedData?.videos || []

  // 更新分页信息
  useEffect(() => {
    if (paginatedData) {
      setTotalPages(paginatedData.totalPages)
      setTotalVideos(paginatedData.total)
    }
  }, [paginatedData])

  // 保存上一次的筛选条件，用于检测是否真正改变
  const prevFilterTypeRef = useRef(filterType)
  const prevSearchQueryRef = useRef(searchQuery)

  // 当筛选条件改变时，重置到第一页并更新 URL
  useEffect(() => {
    // 检查筛选条件是否真正改变（而不是组件重新挂载）
    const filterTypeChanged = prevFilterTypeRef.current !== filterType
    const searchQueryChanged = prevSearchQueryRef.current !== searchQuery

    if (filterTypeChanged || searchQueryChanged) {
      const params = new URLSearchParams(searchParams.toString())
      params.set("page", "1")
      router.push(`/videos?${params.toString()}`, { scroll: false })
      setCurrentPage(1)
    }

    // 更新引用
    prevFilterTypeRef.current = filterType
    prevSearchQueryRef.current = searchQuery
  }, [filterType, searchQuery, searchParams, router])

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
      // 检查是否需要刷新视频列表
      const shouldRefreshVideos = sessionStorage.getItem("shouldRefreshVideos") === "true"

      if (isReturningFromPlay) {
        // 清除标记
        sessionStorage.removeItem("returningFromPlay")

        // 如果需要刷新，清除缓存并重新获取数据
        if (shouldRefreshVideos) {
          sessionStorage.removeItem("shouldRefreshVideos")
          refresh()
        }

        // 使用多种方式确保滚动位置恢复
        const restoreScroll = () => {
          const savedPosition = sessionStorage.getItem("videosPageScrollPosition")
          if (savedPosition) {
            const position = parseInt(savedPosition, 10)

            // 立即设置滚动位置
            window.scrollTo(0, position)

            // 移动端可能需要多次尝试
            setTimeout(() => {
              window.scrollTo(0, position)
            }, 50)

            setTimeout(() => {
              window.scrollTo(0, position)
            }, 100)

            setTimeout(() => {
              window.scrollTo(0, position)
              // 清除保存的位置
              sessionStorage.removeItem("videosPageScrollPosition")
            }, 200)
          }
        }

        // 等待页面完全渲染
        if (document.readyState === 'complete') {
          restoreScroll()
        } else {
          window.addEventListener('load', restoreScroll, { once: true })
          // 额外的延迟作为后备
          setTimeout(restoreScroll, 300)
        }
      }
    }
  }, [loading, videos, refresh])

  const filteredVideos = (videos || []).filter((video) => {
    const matchesSearch = video.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === "all" || video.type === filterType
    return matchesSearch && matchesType
  })

  // 处理分页变化
  const handlePageChange = (newPage: number) => {
    console.log(newPage, 'newPage')
    if (newPage >= 1 && newPage <= totalPages) {
      // 更新 URL 查询参数
      const params = new URLSearchParams(searchParams.toString())
      params.set("page", newPage.toString())
      router.push(`/videos?${params.toString()}`, { scroll: false })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  // 生成页码数组
  const getPageNumbers = () => {
    const pages: (number | string)[] = []

    // 从当前页开始显示
    let startPage = currentPage
    console.log(currentPage, ';----------')
    let endPage = startPage + 4

    // 如果结束页超过总页数，调整起始页
    if (endPage > totalPages) {
      endPage = totalPages
      startPage = Math.max(1, endPage - 4)
    }

    // 生成页码数组
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i)
    }

    return pages
  }
  const handleDelete = async () => {
    if (!video) return

    // 关闭对话框
    setShowDeleteDialog(false)
    setIsDeleting(true)

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_APP_IP}:3003/api/videos/delete?id=${video.id}`,
        {
          method: 'DELETE',
          headers: {
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'Accept': '*/*',
            'Connection': 'keep-alive',
          },
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()

      if (result.success) {
        const params = new URLSearchParams()
        // if (pageFromUrl > 1) {
        //   params.set("page", pageFromUrl.toString())
        // }
        // 刷新当前页面数据
        console.log('刷新页面')
        refresh()
        const url = params.toString() ? `/videos?${params.toString()}` : "/videos"

        sessionStorage.setItem("returningFromPlay", "true")
      } else {
        throw new Error(result.message || "删除失败")
      }
    } catch (error) {
      console.error('删除失败:', error)
      alert(`删除失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setIsDeleting(false)
    }
  }




  const handleVideoClick = (video: MediaItem) => {
    // 保存当前滚动位置到sessionStorage
    const scrollPosition = window.scrollY
    sessionStorage.setItem("videosPageScrollPosition", scrollPosition.toString())

    // 将视频数据存储到 sessionStorage
    sessionStorage.setItem("currentVideo", JSON.stringify(video))
    // 构建播放页面的 URL，包含当前页码参数
    const playUrl = `/videos/play?page=${currentPage}`
    router.push(playUrl)
  }
  // 打开删除确认对话框的状态
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const handleDeleteInfo = (video: MediaItem) => {
    console.log(video, '1212ohj12gy3fg123f1yu')
    setShowDeleteDialog(true)
    setVideo(video)
  }

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* 顶部导航栏 */ }
      <header className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-2xl font-bold">视频库</h1>
            <Button
              size="icon"
              variant="ghost"
              onClick={ refresh }
              disabled={ loading }
              title="刷新列表"
            >
              <RefreshCw className={ `w-5 h-5 ${loading ? 'animate-spin' : ''}` } />
            </Button>
          </div>

          {/* 搜索栏 */ }
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="搜索视频..."
              value={ searchQuery }
              onChange={ (e) => setSearchQuery(e.target.value) }
              className="pl-10 h-12"
            />
          </div>

          {/* 筛选和视图切换 */ }
          <div className="flex items-center justify-between mt-3 gap-2">
            <div className="flex gap-2 overflow-x-auto pb-1">
              <Button
                size="sm"
                variant={ filterType === "all" ? "default" : "secondary" }
                onClick={ () => setFilterType("all") }
              >
                全部
              </Button>
              <Button
                size="sm"
                variant={ filterType === "mp4" ? "default" : "secondary" }
                onClick={ () => setFilterType("mp4") }
              >
                MP4
              </Button>
              <Button
                size="sm"
                variant={ filterType === "webm" ? "default" : "secondary" }
                onClick={ () => setFilterType("webm") }
              >
                WebM
              </Button>
              <Button
                size="sm"
                variant={ filterType === "hls_directory" ? "default" : "secondary" }
                onClick={ () => setFilterType("hls_directory") }
              >
                HLS
              </Button>
            </div>

            <div className="flex gap-1 shrink-0">
              <Button
                size="icon"
                variant={ viewMode === "grid" ? "default" : "ghost" }
                onClick={ () => setViewMode("grid") }
              >
                <Grid3x3 className="w-5 h-5" />
              </Button>
              <Button
                size="icon"
                variant={ viewMode === "list" ? "default" : "ghost" }
                onClick={ () => setViewMode("list") }
              >
                <List className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 视频列表 */ }
      <main className="container mx-auto px-4 py-6">
        { loading && !videos ? (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3"></div>
            <p className="text-lg text-muted-foreground">正在加载视频...</p>
          </div>
        ) : error && !videos ? (
          <div className="text-center py-20">
            <p className="text-lg text-red-600 mb-2">错误</p>
            <p className="text-sm text-muted-foreground">{ error }</p>
            <Button
              className="mt-4"
              onClick={ refresh }
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
              <span>找到 { totalVideos } 个视频</span>
              { fromCache && (
                <span className="text-xs px-2 py-0.5 bg-secondary rounded-full">缓存</span>
              ) }
            </div>
            <div className={ viewMode === "grid" ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" : "space-y-4" }>
              { filteredVideos.map((video, index) => (
                <VideoListItem key={ index } video={ video } onClick={ () => handleVideoClick(video) } onDelete={ (item) => handleDeleteInfo(item) } />

              )) }
            </div>

            {/* 分页控件 */ }
            { totalPages > 1 && (
              <>
                <div className="mt-6 flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={ () => handlePageChange(currentPage - 1) }
                    disabled={ currentPage === 1 }
                  >
                    上一页
                  </Button>

                  { getPageNumbers().map((page, index) => (
                    <Button
                      key={ index }
                      variant={ page === currentPage ? "default" : "outline" }
                      size="sm"
                      className={ page === "..." ? "cursor-default" : "" }
                      onClick={ () => typeof page === "number" && handlePageChange(page) }
                      disabled={ page === "..." }
                    >
                      { page }
                    </Button>
                  )) }

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={ () => handlePageChange(currentPage + 1) }
                    disabled={ currentPage === totalPages }
                  >
                    下一页
                  </Button>
                </div>

                {/* 跳转功能单独一行 */ }
                <div className="mt-3 flex items-center justify-center gap-2">
                  <span className="text-sm text-muted-foreground">跳转到</span>
                  <Input
                    type="number"
                    min={ 1 }
                    max={ totalPages }
                    className="w-20 h-8 text-center"
                    placeholder="页码"
                    // 移动端建议使用 inputMode="numeric" 优化键盘类型
                    inputMode="numeric"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-3"
                    onClick={ () => {
                      const input = document.querySelector('input[type="number"]') as HTMLInputElement
                      const page = parseInt(input?.value || '0', 10)
                      if (page >= 1 && page <= totalPages) {
                        handlePageChange(page)
                        input.value = '' // 可选：清空输入框
                      }
                      if (page >= totalPages) {
                        handlePageChange(totalPages)
                        input.value = '' // 可选：清空输入框
                      }
                    } }
                  >
                    前往
                  </Button>
                  <span className="text-sm text-muted-foreground">/ { totalPages } 页</span>
                </div>

              </>
            ) }

          </>
        ) }
      </main>
      {/* 删除确认对话框 */ }
      <Dialog open={ showDeleteDialog } onOpenChange={ setShowDeleteDialog }>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除视频 "{ video?.name }" 吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={ () => setShowDeleteDialog(false) }
              disabled={ isDeleting }
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={ handleDelete }
              disabled={ isDeleting }
            >
              { isDeleting ? "删除中..." : "删除" }
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
