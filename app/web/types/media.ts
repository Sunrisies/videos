export interface MediaItem {
  id?: string | number; // 视频ID
  name: string;
  path: string;
  type: string;
  // 建议后端新增的字段
  thumbnail?: string; // 缩略图URL
  duration?: number; // 时长（秒）
  size?: string; // 文件大小
  resolution?: string; // 视频分辨率
  bitrate?: string; // 比特率
  createdAt?: string; // 创建时间
  subtitle?: string; // 字幕路径
  width?: number; // 视频宽度（像素）
  height?: number; // 视频高度（像素）
  parent_path: string; // 父目录路径
}

export interface MediaResponse {
  videos: MediaItem[];
}

export type MediaType = "video" | "audio" | "hls";
