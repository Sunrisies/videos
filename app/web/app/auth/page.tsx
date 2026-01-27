"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Video, Lock, AlertCircle } from "lucide-react"

export default function AuthPage() {
  const router = useRouter()
  const { login, isAuthenticated } = useAuth()
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    // 如果已经授权，检查是否有重定向路径
    if (isAuthenticated) {
      const redirectPath = sessionStorage.getItem("authRedirect")
      sessionStorage.removeItem("authRedirect")
      router.push(redirectPath || "/")
    }
  }, [isAuthenticated, router])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    // 模拟验证延迟，提供更好的用户体验
    setTimeout(() => {
      const success = login(password)
      setIsLoading(false)

      if (success) {
        // 登录成功，跳转到目标页面
        const redirectPath = sessionStorage.getItem("authRedirect")
        sessionStorage.removeItem("authRedirect")
        router.push(redirectPath || "/")
      } else {
        setError("密码错误，请重试")
        setPassword("")
      }
    }, 500)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSubmit(e as any)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo 和标题 */ }
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-accent/10 rounded-full mb-4">
            <Video className="w-8 h-8 text-accent" />
          </div>
          <h1 className="text-2xl font-bold mb-2">视频库访问验证</h1>
          <p className="text-muted-foreground">请输入密码以继续访问</p>
        </div>

        {/* 密码输入卡片 */ }
        <div className="bg-card border rounded-xl shadow-lg p-6">
          <form onSubmit={ handleSubmit } className="space-y-4">
            {/* 密码输入框 */ }
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium flex items-center gap-2">
                <Lock className="w-4 h-4" />
                访问密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={ password }
                onChange={ (e) => setPassword(e.target.value) }
                onKeyPress={ handleKeyPress }
                autoFocus
                disabled={ isLoading }
                className="h-12 text-base"
              />
            </div>

            {/* 错误提示 */ }
            { error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-lg">
                <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
                <p className="text-sm text-red-600 dark:text-red-400">{ error }</p>
              </div>
            ) }

            {/* 提交按钮 */ }
            <Button
              type="submit"
              className="w-full h-12 text-base"
              disabled={ !password || isLoading }
            >
              { isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                  验证中...
                </>
              ) : (
                "确认"
              ) }
            </Button>
          </form>

          {/* 提示信息 */ }
          <div className="mt-6 pt-4 border-t text-center">
            <p className="text-xs text-muted-foreground">
              提示：密码在会话期间有效，关闭浏览器后需重新输入
            </p>
          </div>
        </div>

        {/* 返回首页链接 */ }
        <div className="text-center mt-6">
          <Button
            variant="ghost"
            onClick={ () => router.push("/") }
            className="text-muted-foreground hover:text-foreground"
          >
            返回首页
          </Button>
        </div>
      </div>
    </div>
  )
}
