import type { MediaType } from "@/types/media"

export function getMediaType(type: string): MediaType {
  const lowerType = type.toLowerCase()

  if (lowerType.includes("hls") || lowerType === "m3u8") {
    return "hls"
  }

  if (["mp3", "wav", "aac", "flac", "ogg", "webm"].some((ext) => lowerType.includes(ext))) {
    return "audio"
  }

  return "video"
}

export function formatDuration(seconds: number): string {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

export function formatFileSize(bytes?: string): string {
  if (!bytes) return ""
  const num = Number.parseInt(bytes)
  if (isNaN(num)) return bytes

  const sizes = ["B", "KB", "MB", "GB"]
  if (num === 0) return "0 B"
  const i = Math.floor(Math.log(num) / Math.log(1024))
  return `${(num / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
}

export function normalizeMediaPath(path: string): string {
  // 将后端路径转换为前端可用的URL
  return path.replace(/\\/g, "/").replace("/public", "")
}
