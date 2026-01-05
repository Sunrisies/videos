"use client"

import { useEffect, useRef, useState } from "react"
import { Play, Pause, Volume2, VolumeX, Maximize, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"

interface MediaItem {
  name: string
  path: string
  type: string
  thumbnail?: string // 可选：缩略图
  duration?: number // 可选：时长
  size?: string // 可选：文件大小
}

interface MediaPlayerProps {
  media: MediaItem
  autoPlay?: boolean
}

export function MediaPlayer({ media, autoPlay = false }: MediaPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState([100])
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isHlsSupported, setIsHlsSupported] = useState(false)

  // 根据type获取实际的播放URL
  const getMediaUrl = () => {
    // 处理路径中的反斜杠
    const cleanPath = media.path.replace(/\\/g, "/")

    if (media.type === "hls_directory") {
      // HLS目录，指向playlist.m3u8
      return `${cleanPath}/playlist.m3u8`
    }

    return cleanPath
  }

  // 判断是视频还是音频
  const isVideo = ["mp4", "webm", "ogg", "hls_directory", "hls", "m3u8"].includes(media.type.toLowerCase())
  const isAudio = ["mp3", "wav", "aac", "flac", "ogg"].includes(media.type.toLowerCase())
  const isHls = media.type === "hls_directory" || media.type === "hls" || media.type === "m3u8"

  // 初始化HLS播放器
  useEffect(() => {
    if (!isHls || !videoRef.current) return

    const loadHls = async () => {
      // 动态加载HLS.js
      const Hls = (await import("hls.js")).default

      if (Hls.isSupported()) {
        const hls = new Hls()
        hls.loadSource(getMediaUrl())
        hls.attachMedia(videoRef.current!)
        setIsHlsSupported(true)

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          if (autoPlay) {
            videoRef.current?.play()
          }
        })

        return () => {
          hls.destroy()
        }
      } else if (videoRef.current.canPlayType("application/vnd.apple.mpegurl")) {
        // Safari原生支持HLS
        videoRef.current.src = getMediaUrl()
        setIsHlsSupported(true)
      }
    }

    loadHls()
  }, [media, isHls, autoPlay])

  // 播放/暂停控制
  const togglePlay = () => {
    const element = isVideo ? videoRef.current : audioRef.current
    if (!element) return

    if (isPlaying) {
      element.pause()
    } else {
      element.play()
    }
    setIsPlaying(!isPlaying)
  }

  // 音量控制
  const toggleMute = () => {
    const element = isVideo ? videoRef.current : audioRef.current
    if (!element) return

    element.muted = !isMuted
    setIsMuted(!isMuted)
  }

  const handleVolumeChange = (value: number[]) => {
    const element = isVideo ? videoRef.current : audioRef.current
    if (!element) return

    setVolume(value)
    element.volume = value[0] / 100
  }

  // 进度控制
  const handleTimeUpdate = () => {
    const element = isVideo ? videoRef.current : audioRef.current
    if (!element) return

    setCurrentTime(element.currentTime)
    setDuration(element.duration || 0)
  }

  const handleSeek = (value: number[]) => {
    const element = isVideo ? videoRef.current : audioRef.current
    if (!element) return

    element.currentTime = value[0]
    setCurrentTime(value[0])
  }

  // 全屏控制
  const toggleFullscreen = () => {
    if (!videoRef.current) return

    if (!document.fullscreenElement) {
      videoRef.current.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }

  // 格式化时间
  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return "0:00"
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // 获取文件图标
  const getMediaTypeLabel = () => {
    const typeMap: Record<string, string> = {
      mp4: "MP4视频",
      webm: "WebM视频",
      hls_directory: "HLS流媒体",
      hls: "HLS流媒体",
      m3u8: "HLS流媒体",
      mp3: "MP3音频",
      wav: "WAV音频",
      aac: "AAC音频",
      flac: "FLAC音频",
    }
    return typeMap[media.type.toLowerCase()] || media.type.toUpperCase()
  }

  if (isVideo) {
    return (
      <div className="w-full bg-black rounded-lg overflow-hidden">
        <div className="relative group">
          <video
            ref={videoRef}
            className="w-full aspect-video"
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            src={!isHls ? getMediaUrl() : undefined}
            autoPlay={autoPlay}
          />

          {/* 播放器控制栏 */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="space-y-2">
              {/* 进度条 */}
              <Slider
                value={[currentTime]}
                max={duration || 100}
                step={0.1}
                onValueChange={handleSeek}
                className="cursor-pointer"
              />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button size="icon" variant="ghost" onClick={togglePlay} className="text-white hover:bg-white/20">
                    {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                  </Button>

                  <Button size="icon" variant="ghost" onClick={toggleMute} className="text-white hover:bg-white/20">
                    {isMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
                  </Button>

                  <div className="w-24">
                    <Slider
                      value={volume}
                      max={100}
                      step={1}
                      onValueChange={handleVolumeChange}
                      className="cursor-pointer"
                    />
                  </div>

                  <span className="text-white text-sm">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>

                <Button size="icon" variant="ghost" onClick={toggleFullscreen} className="text-white hover:bg-white/20">
                  <Maximize className="h-5 w-5" />
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* 媒体信息 */}
        <div className="bg-muted p-3 flex items-center justify-between">
          <div>
            <p className="font-medium">{media.name}</p>
            <p className="text-sm text-muted-foreground">{getMediaTypeLabel()}</p>
          </div>
          <Button size="sm" variant="outline" asChild>
            <a href={getMediaUrl()} download>
              <Download className="h-4 w-4 mr-2" />
              下载
            </a>
          </Button>
        </div>
      </div>
    )
  }

  if (isAudio) {
    return (
      <div className="w-full bg-card rounded-lg border overflow-hidden">
        <audio
          ref={audioRef}
          onTimeUpdate={handleTimeUpdate}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          src={getMediaUrl()}
          autoPlay={autoPlay}
        />

        <div className="p-4 space-y-4">
          {/* 音频信息 */}
          <div className="flex items-center gap-3">
            <div className="w-16 h-16 bg-primary/10 rounded-lg flex items-center justify-center">
              <Volume2 className="h-8 w-8 text-primary" />
            </div>
            <div className="flex-1">
              <p className="font-medium">{media.name}</p>
              <p className="text-sm text-muted-foreground">{getMediaTypeLabel()}</p>
            </div>
          </div>

          {/* 进度条 */}
          <div className="space-y-2">
            <Slider
              value={[currentTime]}
              max={duration || 100}
              step={0.1}
              onValueChange={handleSeek}
              className="cursor-pointer"
            />
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* 控制按钮 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button size="icon" onClick={togglePlay}>
                {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
              </Button>

              <Button size="icon" variant="outline" onClick={toggleMute}>
                {isMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
              </Button>

              <div className="w-24">
                <Slider
                  value={volume}
                  max={100}
                  step={1}
                  onValueChange={handleVolumeChange}
                  className="cursor-pointer"
                />
              </div>
            </div>

            <Button size="sm" variant="outline" asChild>
              <a href={getMediaUrl()} download>
                <Download className="h-4 w-4 mr-2" />
                下载
              </a>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // 不支持的格式
  return (
    <div className="w-full bg-card rounded-lg border p-6 text-center">
      <p className="text-muted-foreground">不支持的媒体格式: {media.type}</p>
      <p className="text-sm mt-2">{media.name}</p>
    </div>
  )
}
