import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    const tradingEngineUrl = process.env.TRADING_ENGINE_URL ?? "http://127.0.0.1:3030";

    return [
      { source: "/health", destination: `${tradingEngineUrl}/health` },
      { source: "/metrics", destination: `${tradingEngineUrl}/metrics` },
      { source: "/api/:path*", destination: `${tradingEngineUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;
