"use client"

import { useState, useEffect, useCallback, useRef } from "react"

interface CacheEntry<T> {
  data: T
  timestamp: number
}

interface UseDataCacheOptions {
  /** 缓存键名 */
  cacheKey: string
  /** 缓存有效期（毫秒），默认 5 分钟 */
  maxAge?: number
  /** 是否在后台刷新数据 */
  backgroundRefresh?: boolean
}

interface UseDataCacheReturn<T> {
  /** 缓存的数据 */
  data: T | null
  /** 是否正在加载 */
  loading: boolean
  /** 错误信息 */
  error: string | null
  /** 手动刷新数据 */
  refresh: () => Promise<void>
  /** 是否使用了缓存数据 */
  fromCache: boolean
}

// 内存缓存存储
const memoryCache = new Map<string, CacheEntry<any>>()

/**
 * 数据缓存 Hook
 * 
 * 实现智能缓存机制：
 * 1. 从播放页面返回时优先使用缓存数据
 * 2. 支持后台静默刷新
 * 3. 缓存过期后自动重新请求
 */
export function useDataCache<T>(
  fetcher: () => Promise<T>,
  options: UseDataCacheOptions
): UseDataCacheReturn<T> {
  const { cacheKey, maxAge = 5 * 60 * 1000, backgroundRefresh = true } = options
  
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fromCache, setFromCache] = useState(false)
  const fetcherRef = useRef(fetcher)
  
  // 更新 fetcher 引用
  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  // 检查缓存是否有效
  const isCacheValid = useCallback((entry: CacheEntry<T> | undefined): boolean => {
    if (!entry) return false
    const now = Date.now()
    return now - entry.timestamp < maxAge
  }, [maxAge])

  // 从缓存或网络获取数据
  const fetchData = useCallback(async (forceRefresh = false) => {
    const cachedEntry = memoryCache.get(cacheKey) as CacheEntry<T> | undefined
    
    // 检查是否从播放页面返回
    const isReturningFromPlay = sessionStorage.getItem("returningFromPlay") === "true"
    
    // 如果是从播放页面返回且缓存有效，优先使用缓存
    if (!forceRefresh && isReturningFromPlay && cachedEntry) {
      setData(cachedEntry.data)
      setFromCache(true)
      setLoading(false)
      setError(null)
      
      // 后台静默刷新（如果启用）
      if (backgroundRefresh && !isCacheValid(cachedEntry)) {
        fetcherRef.current().then(newData => {
          memoryCache.set(cacheKey, { data: newData, timestamp: Date.now() })
          setData(newData)
          setFromCache(false)
        }).catch(() => {
          // 静默失败，保持缓存数据
        })
      }
      return
    }
    
    // 如果缓存有效且不是强制刷新，使用缓存
    if (!forceRefresh && isCacheValid(cachedEntry)) {
      setData(cachedEntry!.data)
      setFromCache(true)
      setLoading(false)
      setError(null)
      return
    }
    
    // 如果有缓存但已过期，先显示缓存数据
    if (cachedEntry && !forceRefresh) {
      setData(cachedEntry.data)
      setFromCache(true)
    }
    
    // 从网络获取新数据
    setLoading(cachedEntry ? false : true) // 如果有缓存，不显示加载状态
    
    try {
      const newData = await fetcherRef.current()
      memoryCache.set(cacheKey, { data: newData, timestamp: Date.now() })
      setData(newData)
      setFromCache(false)
      setError(null)
    } catch (err) {
      // 如果有缓存数据，保持显示缓存
      if (!cachedEntry) {
        setError(err instanceof Error ? err.message : "获取数据失败")
      }
    } finally {
      setLoading(false)
    }
  }, [cacheKey, isCacheValid, backgroundRefresh])

  // 初始加载
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 手动刷新
  const refresh = useCallback(async () => {
    await fetchData(true)
  }, [fetchData])

  return { data, loading, error, refresh, fromCache }
}

/**
 * 清除指定缓存
 */
export function clearCache(cacheKey: string): void {
  memoryCache.delete(cacheKey)
}

/**
 * 清除所有缓存
 */
export function clearAllCache(): void {
  memoryCache.clear()
}

/**
 * 预热缓存
 */
export function warmCache<T>(cacheKey: string, data: T): void {
  memoryCache.set(cacheKey, { data, timestamp: Date.now() })
}
