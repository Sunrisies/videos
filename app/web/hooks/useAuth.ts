"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"

export function useAuth() {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect(() => {
    // 检查 sessionStorage 中的授权状态
    const authStatus = sessionStorage.getItem("authenticated")
    setIsAuthenticated(authStatus === "true")
    setIsLoading(false)
  }, [])

  const login = (password: string): boolean => {
    const correctPassword = process.env.NEXT_PUBLIC_APP_PASSWORD

    // 如果未配置密码，直接允许访问
    if (!correctPassword) {
      sessionStorage.setItem("authenticated", "true")
      setIsAuthenticated(true)
      return true
    }

    // 验证密码
    if (password === correctPassword) {
      sessionStorage.setItem("authenticated", "true")
      setIsAuthenticated(true)
      return true
    }

    return false
  }

  const logout = () => {
    sessionStorage.removeItem("authenticated")
    setIsAuthenticated(false)
    router.push("/auth")
  }

  const requireAuth = (redirectPath?: string) => {
    if (!isLoading && !isAuthenticated) {
      // 保存目标路径以便验证后跳转
      if (redirectPath) {
        sessionStorage.setItem("authRedirect", redirectPath)
      }
      router.push("/auth")
    }
  }

  return {
    isAuthenticated,
    isLoading,
    login,
    logout,
    requireAuth,
  }
}
