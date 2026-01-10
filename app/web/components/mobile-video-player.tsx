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
  const controlsTimeoutRef = useRef<NodeJS.Timeout>()
  const hlsRef = useRef<any>(null)

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
            videoUrl = `http://192.168.10.4:3000/public/${filename}`
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
    if (isPlaying) {
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

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return

    video.muted = !isMuted
    setIsMuted(!isMuted)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current
    if (!video) return

    const newVolume = Number.parseFloat(e.target.value)
    video.volume = newVolume
    setVolume(newVolume)
    setIsMuted(newVolume === 0)
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

  const handleRestart = () => {
    const video = videoRef.current
    if (!video) return

    video.currentTime = 0
    video.play()
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
      className="relative w-full aspect-video bg-black rounded-lg overflow-hidden touch-none"
      onTouchStart={resetControlsTimeout}
      onTouchMove={resetControlsTimeout}
      onClick={resetControlsTimeout}
    >
      <video
        ref={videoRef}
        className="w-full h-full"
        playsInline
        preload="metadata"
        poster={`http://192.168.10.4:3000\\${media.thumbnail}`}
        onClick={togglePlay}
        crossOrigin="anonymous"
      >
        <source type="video/mp4" />
        您的浏览器不支持视频播放
      </video>

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <div className="w-12 h-12 border-4 border-white/30 border-t-white rounded-full animate-spin" />
        </div>
      )}

      <div
        className={`absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/40 transition-opacity duration-300 ${showControls ? "opacity-100" : "opacity-0"
          }`}
      >
        {/* 顶部信息栏 */}
        <div className="absolute top-0 left-0 right-0 p-4">
          <h3 className="text-white font-medium text-lg truncate">{media.name}</h3>

          {media.resolution && <p className="text-white/70 text-sm mt-1">{media.resolution}</p>}
        </div>

        {/* 中央播放按钮 */}
        {!isPlaying && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Button size="lg" onClick={togglePlay} className="w-20 h-20 rounded-full bg-white/90 hover:bg-white">
              <Play className="w-10 h-10 text-black fill-black ml-1" />
            </Button>
          </div>
        )}

        {/* 底部控制栏 */}
        <div className="absolute bottom-0 left-0 right-0 p-4 space-y-3">
          {/* 进度条 */}
          <div className="flex items-center gap-3">
            <span className="text-white text-sm font-medium min-w-[40px]">{currentTime}</span>
            <input
              type="range"
              min="0"
              max={duration || 0}
              value={currentTime}
              onChange={handleSeek}
              className="flex-1 h-2 bg-white/30 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white
                [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 
                [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-0"
            />
            <span className="text-white text-sm font-medium min-w-[40px] text-right">{formatTime(duration)}</span>
          </div>

          {/* 控制按钮 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                size="icon"
                variant="ghost"
                onClick={togglePlay}
                className="text-white hover:bg-white/20 h-12 w-12"
              >
                {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
              </Button>

              <Button
                size="icon"
                variant="ghost"
                onClick={handleRestart}
                className="text-white hover:bg-white/20 h-12 w-12"
              >
                <RotateCcw className="w-5 h-5" />
              </Button>

              <div className="flex items-center gap-2">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={toggleMute}
                  className="text-white hover:bg-white/20 h-12 w-12"
                >
                  {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                </Button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={isMuted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 bg-white/30 rounded-full appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 
                    [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white
                    [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 
                    [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-0"
                />
              </div>
            </div>

            <Button
              size="icon"
              variant="ghost"
              onClick={toggleFullscreen}
              className="text-white hover:bg-white/20 h-12 w-12"
            >
              <Maximize className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
