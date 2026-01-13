"use client"

import type React from "react"

import { useEffect, useRef, useState } from "react"
import { Play, Pause, Volume2, VolumeX, Maximize, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { MediaItem } from "@/types/media"

interface MobileVideoPlayerProps {
  media: MediaItem
  autoPlay?: boolean
}

export function MobileVideoPlayer({ media, autoPlay = false }: MobileVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const hlsRef = useRef<any>(null)

  // 拖动相关状态
  const [isDragging, setIsDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartTime, setDragStartTime] = useState(0)
  const [touchStartTime, setTouchStartTime] = useState(0)
  const [previewTime, setPreviewTime] = useState(0)
  const [showPreview, setShowPreview] = useState(false)

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const initPlayer = async () => {
      setIsLoading(true)
      setError(null)

      try {
        if (media.type === "hls_directory" || media.path.endsWith(".m3u8")) {
          // HLS 流媒体处理
          const hlsUrl = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

          if (video.canPlayType("application/vnd.apple.mpegurl")) {
            // 原生支持HLS（iOS Safari）
            video.src = hlsUrl
            setIsLoading(false)
          } else if (typeof window !== "undefined") {
            // 动态加载hls.js
            const script = document.createElement("script")
            script.src = "https://cdn.jsdelivr.net/npm/hls.js@latest"
            script.onload = () => {
              const Hls = (window as any).Hls
              if (Hls && Hls.isSupported()) {
                const hls = new Hls({
                  enableWorker: true,
                  lowLatencyMode: true,
                })
                hlsRef.current = hls
                hls.loadSource(hlsUrl)
                hls.attachMedia(video)
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                  setIsLoading(false)
                  console.log("[v0] HLS manifest loaded successfully")
                  if (autoPlay) {
                    video.play().catch((err) => {
                      console.log("[v0] Autoplay failed:", err)
                      setIsPlaying(false)
                    })
                  }
                })
                hls.on(Hls.Events.ERROR, (event: any, data: any) => {
                  console.log("[v0] HLS error:", data)
                  if (data.fatal) {
                    setError("视频加载失败")
                    setIsLoading(false)
                  }
                })
              } else {
                setError("您的浏览器不支持HLS视频播放")
                setIsLoading(false)
              }
            }
            script.onerror = () => {
              setError("HLS.js加载失败")
              setIsLoading(false)
            }
            document.head.appendChild(script)
          }
        } else {
          // 普通视频文件 - 使用传入的path路径
          let videoUrl = media.path
          console.log("Original video path:", videoUrl)
          // 如果path是以/public/开头，需要转换为实际的URL
          // 处理Windows路径分隔符
          if (videoUrl.includes("\\")) {
            // 将Windows路径转换为URL路径
            const pathParts = videoUrl.split("\\")
            const filename = pathParts[pathParts.length - 1]
            // 使用相对路径访问public目录下的文件
            videoUrl = `http://192.168.1.5:3003/public/${filename}`
          }

          // 如果是MP4文件，直接使用提供的路径
          if (media.type === "mp4") {
            // 确保URL格式正确
            if (!videoUrl.startsWith("http") && !videoUrl.startsWith("/")) {
              videoUrl = "/" + videoUrl
            }
          }

          video.src = videoUrl
          console.log("[v0] Loading video from:", videoUrl)
          setIsLoading(false)

          if (autoPlay) {
            video.play().catch((err) => {
              console.log("[v0] Autoplay failed:", err)
              setIsPlaying(false)
            })
          }
        }
      } catch (err) {
        console.log("[v0] Video initialization error:", err)
        setError("视频初始化失败")
        setIsLoading(false)
      }
    }

    initPlayer()

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
      }
    }
  }, [media, autoPlay])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleLoadedMetadata = () => {
      setDuration(video.duration)
      setIsLoading(false)
    }

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime)
    }

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)
    const handleEnded = () => setIsPlaying(false)
    const handleWaiting = () => setIsLoading(true)
    const handleCanPlay = () => setIsLoading(false)

    video.addEventListener("loadedmetadata", handleLoadedMetadata)
    video.addEventListener("timeupdate", handleTimeUpdate)
    video.addEventListener("play", handlePlay)
    video.addEventListener("pause", handlePause)
    video.addEventListener("ended", handleEnded)
    video.addEventListener("waiting", handleWaiting)
    video.addEventListener("canplay", handleCanPlay)

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata)
      video.removeEventListener("timeupdate", handleTimeUpdate)
      video.removeEventListener("play", handlePlay)
      video.removeEventListener("pause", handlePause)
      video.removeEventListener("ended", handleEnded)
      video.removeEventListener("waiting", handleWaiting)
      video.removeEventListener("canplay", handleCanPlay)
    }
  }, [])

  const resetControlsTimeout = () => {
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current)
    }
    setShowControls(true)
    if (isPlaying && !isDragging) {
      controlsTimeoutRef.current = setTimeout(() => {
        setShowControls(false)
      }, 3000)
    }
  }

  useEffect(() => {
    resetControlsTimeout()
    return () => {
      if (controlsTimeoutRef.current) {
        clearTimeout(controlsTimeoutRef.current)
      }
    }
  }, [isPlaying])

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return

    if (isPlaying) {
      video.pause()
    } else {
      video.play().catch((err) => {
        console.log("[v0] Play error:", err)
        setError("播放失败，请检查视频源")
      })
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current
    if (!video) return

    const newTime = Number.parseFloat(e.target.value)
    video.currentTime = newTime
    setCurrentTime(newTime)
  }

  // 触摸事件处理：单击切换控制栏和拖动调整进度
  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    if (isLoading || error) return

    const touch = e.touches[0]
    setDragStartX(touch.clientX)
    setTouchStartTime(Date.now())
    setDragStartTime(currentTime)
  }

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    if (isLoading || error) return

    const touch = e.touches[0]
    const deltaX = touch.clientX - dragStartX

    // 判断是否达到拖动阈值 (10px)
    if (Math.abs(deltaX) > 10 && !isDragging) {
      setIsDragging(true)
      setShowControls(true)
    }

    if (isDragging) {
      // 计算进度变化：每像素移动对应的时间变化
      const screenWidth = window.innerWidth
      const deltaTime = (deltaX / screenWidth) * duration
      const newTime = Math.max(0, Math.min(duration, dragStartTime + deltaTime))

      setPreviewTime(newTime)
      setShowPreview(true)

      // 防止默认滚动行为
      e.preventDefault()
    }
  }

  const handleTouchEnd = (e: React.TouchEvent<HTMLDivElement>) => {
    if (isLoading || error) return

    const touchDuration = Date.now() - touchStartTime
    const touch = e.changedTouches[0]
    const deltaX = touch.clientX - dragStartX

    if (isDragging) {
      // 应用拖动后的进度
      const video = videoRef.current
      if (video) {
        video.currentTime = previewTime
        setCurrentTime(previewTime)
      }

      // 延迟隐藏预览气泡
      setTimeout(() => {
        setShowPreview(false)
      }, 300)

      setIsDragging(false)
      resetControlsTimeout()
    } else if (Math.abs(deltaX) < 10 && touchDuration < 300) {
      // 识别为单击事件：切换控制栏显示
      setShowControls((prev) => !prev)

      // 如果显示控制栏且正在播放，启动自动隐藏计时器
      if (!showControls && isPlaying) {
        resetControlsTimeout()
      }
    }
  }




  const toggleFullscreen = () => {
    const video = videoRef.current
    if (!video) return

    if (!document.fullscreenElement) {
      video.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }



  if (error) {
    return (
      <div className="relative w-full aspect-video bg-black rounded-lg flex items-center justify-center">
        <div className="text-center p-6">
          <p className="text-white text-lg mb-4">{error}</p>
          <Button onClick={() => window.location.reload()} variant="secondary">
            重新加载
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="relative w-full aspect-video bg-black overflow-hidden touch-none group"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        playsInline
        preload="metadata"
        poster={media.thumbnail ? `http://192.168.1.5:3003/${media.thumbnail}` : undefined}
        crossOrigin="anonymous"
      >
        <source type="video/mp4" />
        您的浏览器不支持视频播放
      </video>

      {/* 加载状态 - 优化为更现代的加载动画 */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-3 border-white/30 border-t-white rounded-full animate-spin" />
            <p className="text-white/90 text-sm font-medium">加载中...</p>
          </div>
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-md">
          <div className="text-center p-6 max-w-xs">
            <p className="text-white/90 text-lg mb-4">{error}</p>
            <Button
              onClick={() => window.location.reload()}
              variant="secondary"
              className="bg-white/20 hover:bg-white/30 text-white border-white/30"
            >
              重新加载
            </Button>
          </div>
        </div>
      )}

      {/* 拖动进度预览气泡 */}
      {showPreview && isDragging && (
        <div className="absolute top-1/3 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50">
          <div className="bg-black/80 backdrop-blur-sm px-4 py-2 rounded-lg shadow-lg">
            <p className="text-white text-base font-medium whitespace-nowrap">
              {formatTime(previewTime)} / {formatTime(duration)}
            </p>
          </div>
        </div>
      )}

      {/* 控制层 - 优化为渐变遮罩和更清晰的视觉层次 */}
      <div
        className={`absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent transition-opacity  duration-300 ${showControls ? "opacity-100" : "opacity-0"
          } group-hover:opacity-100`}
      >
        {/* 中央播放按钮 - 优化为更现代的圆形按钮 */}
        {!isPlaying && !isLoading && !error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Button
              size="lg"
              onClick={togglePlay}
              className="w-16 h-16 rounded-full bg-white/90 hover:bg-white text-black shadow-lg transition-transform hover:scale-105 active:scale-95"
            >
              <Play className="w-8 h-8 fill-black ml-0.5" />
            </Button>
          </div>
        )}

        {/* 底部控制栏 - 参考B站布局：进度条在左侧，控制按钮在右侧 */}
        <div className="absolute bottom-0 left-0 right-0 p-3 space-y-2 flex ">
          {/* 进度条 - 单独一行，更宽的滑块 */}
          <div className="flex items-center gap-3 px-1">
            <span className="text-white text-xs font-medium min-w-[40px] text-right tabular-nums opacity-90">
              {formatTime(currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={duration || 0}
              value={currentTime}
              onChange={handleSeek}
              className="flex-1 h-1.5 bg-white/30 hover:bg-white/50 rounded-full appearance-none cursor-pointer transition-colors
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white
                [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(0,0,0,0.5)]
                [&::-webkit-slider-thumb]:hover:scale-110
                [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 
                [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white
                [&::-moz-range-thumb]:border-0
                [&::-moz-range-thumb]:hover:scale-110"
            />
            <span className="text-white text-xs font-medium min-w-[40px] tabular-nums opacity-90">
              {formatTime(duration)}
            </span>
          </div>

          {/* 控制按钮 - 紧凑布局，参考B站 */}
          <div className="flex items-center justify-between px-1">
            {/* 左侧：播放/暂停 + 重新开始 + 音量滑块 */}
            <div className="flex items-center gap-2">
              <Button
                size="icon"
                variant="ghost"
                onClick={togglePlay}
                className="text-white hover:bg-white/20 h-10 w-10 rounded-lg transition-colors"
              >
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              </Button>

            </div>

            {/* 右侧：全屏按钮 */}
            <Button
              size="icon"
              variant="ghost"
              onClick={toggleFullscreen}
              className="text-white hover:bg-white/20 h-10 w-10 rounded-lg transition-colors"
              title="全屏"
            >
              <Maximize className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* 播放状态指示器 - 在屏幕中央显示播放/暂停状态 */}
      {!showControls && !isLoading && !error && (
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-0 transition-opacity duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-black/50 backdrop-blur-sm rounded-full p-4 transform scale-90 transition-transform duration-200">
            {isPlaying ? (
              <Pause className="w-8 h-8 text-white fill-white" />
            ) : (
              <Play className="w-8 h-8 text-white fill-white" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
