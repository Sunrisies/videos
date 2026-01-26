import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 保持滚动位置
  // experimental: {
  //   scrollRestoration: true,
  // },
  allowedDevOrigins: ["local-origin.dev", "*.local-origin.dev"],
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "192.168.10.19",
        port: "3003",
        pathname: "/**",
      },
    ],
  },
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
