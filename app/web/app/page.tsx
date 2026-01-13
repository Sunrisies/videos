"use client"

import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Video, PlayCircle } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"

export default function HomePage() {
  const router = useRouter()
  const { isAuthenticated, requireAuth } = useAuth()

  const handleBrowseVideos = () => {
    if (isAuthenticated) {
      router.push("/videos")
    } else {
      requireAuth("/videos")
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      {/* 顶部导航 */}
      <header className="border-b bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
              <Video className="w-6 h-6 text-accent-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-bold">移动视频播放器</h1>
              <p className="text-xs text-muted-foreground">支持多格式视频播放</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12">
        {/* 欢迎区域 */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-accent/10 rounded-full mb-6">
            <PlayCircle className="w-12 h-12 text-accent" />
          </div>
          <h2 className="text-3xl font-bold mb-3">欢迎使用视频播放器</h2>
          <p className="text-muted-foreground text-lg mb-8 max-w-md mx-auto">
            专为移动端优化的视频播放体验，支持 MP4、WebM、HLS 等多种格式
          </p>

          <Button size="lg" onClick={handleBrowseVideos} className="h-14 px-8 text-lg">
            <Video className="w-5 h-5 mr-2" />
            浏览视频库
          </Button>
        </div>

        {/* 功能特性 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mt-16">
          <div className="bg-card border rounded-xl p-6 text-center">
            <div className="w-12 h-12 bg-accent/10 rounded-lg flex items-center justify-center mx-auto mb-4">
              <Video className="w-6 h-6 text-accent" />
            </div>
            <h3 className="font-semibold mb-2">多格式支持</h3>
            <p className="text-sm text-muted-foreground">支持 MP4、WebM、OGV、HLS 等主流视频格式</p>
          </div>

          <div className="bg-card border rounded-xl p-6 text-center">
            <div className="w-12 h-12 bg-accent/10 rounded-lg flex items-center justify-center mx-auto mb-4">
              <PlayCircle className="w-6 h-6 text-accent" />
            </div>
            <h3 className="font-semibold mb-2">流畅播放</h3>
            <p className="text-sm text-muted-foreground">自动适配网络环境，确保最佳播放体验</p>
          </div>

          <div className="bg-card border rounded-xl p-6 text-center">
            <div className="w-12 h-12 bg-accent/10 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h3 className="font-semibold mb-2">移动优化</h3>
            <p className="text-sm text-muted-foreground">专为触摸屏设计，操作简单直观</p>
          </div>
        </div>

        {/* 说明文档 */}
        <div className="max-w-2xl mx-auto mt-16 bg-muted/30 rounded-xl p-6 border">
          <h3 className="font-semibold mb-4">后端数据结构建议</h3>
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">为了获得最佳体验，建议后端接口返回以下字段：</p>
            <ul className="space-y-2 text-muted-foreground">
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>type</strong>（必需）：视频格式（mp4/webm/ogv/hls_directory）
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>path</strong>（必需）：视频资源URL或路径
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>thumbnail</strong>（推荐）：缩略图URL
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>duration</strong>（推荐）：视频时长（秒）
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>resolution</strong>（可选）：分辨率（如"1920x1080"）
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>size</strong>（可选）：文件大小
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent">•</span>
                <span>
                  <strong>bitrate</strong>（可选）：比特率
                </span>
              </li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  )
}
