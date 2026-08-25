import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];

    return [
      { source: "/health", destination: "http://127.0.0.1:3030/health" },
      { source: "/metrics", destination: "http://127.0.0.1:3030/metrics" },
      { source: "/api/:path*", destination: "http://127.0.0.1:3030/api/:path*" },
    ];
  },
};

export default nextConfig;
