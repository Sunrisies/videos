import { NextResponse } from "next/server";
import type { MediaResponse } from "@/types/media";

// 模拟从后端获取媒体数据的API路由
export async function GET() {
  // 在实际应用中，这里应该从数据库或文件系统读取
  const mediaData: MediaResponse = {
    videos: [
      {
        name: "1221",
        path: "/public/1221",
        type: "hls_directory",
      },
      {
        name: "20250821_170542.mp4",
        path: "/public/20250821_170542.mp4",
        type: "mp4",
      },
      {
        name: "20250821_171913.mp4",
        path: "/public/20250821_171913.mp4",
        type: "mp4",
      },
      {
        name: "20250825_082816.mp4",
        path: "/public/20250825_082816.mp4",
        type: "mp4",
      },
      {
        name: "20250828_174030.mp4",
        path: "/public/20250828_174030.mp4",
        type: "mp4",
      },
      {
        name: "20250904_111833.mp4",
        path: "/public/20250904_111833.mp4",
        type: "mp4",
      },
      {
        name: "20250904_150139.mp4",
        path: "/public/20250904_150139.mp4",
        type: "mp4",
      },
      {
        name: "20250908_144042.mp4",
        path: "/public/20250908_144042.mp4",
        type: "mp4",
      },
      {
        name: "20250909_100124.mp4",
        path: "/public/20250909_100124.mp4",
        type: "mp4",
      },
      {
        name: "20250920_105949.mp4",
        path: "/public/20250920_105949.mp4",
        type: "mp4",
      },
      {
        name: "20250920_110324.mp4",
        path: "/public/20250920_110324.mp4",
        type: "mp4",
      },
      {
        name: "20250920_110557.mp4",
        path: "/public/20250920_110557.mp4",
        type: "mp4",
      },
    ],
  };
  return NextResponse.json(mediaData);
}
