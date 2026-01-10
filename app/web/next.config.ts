import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "192.168.10.4",
        port: "3000",
        pathname: "/**",
      },
    ],
  },
  async headers() {
    return [
      // {
      //   source: "/api/:path*",
      //   headers: [
      //     { key: "Access-Control-Allow-Origin", value: "*" },
      //     {
      //       key: "Access-Control-Allow-Methods",
      //       value: "GET, POST, PUT, DELETE, OPTIONS",
      //     },
      //     {
      //       key: "Access-Control-Allow-Headers",
      //       value: "Content-Type, Authorization",
      //     },
      //   ],
      // },
    ];
  },
};

export default nextConfig;
