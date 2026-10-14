import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Server-side only: the browser talks to /api/v1/*, never to the gateway origin.
  rewrites() {
    const gateway = process.env.API_GATEWAY_URL ?? "http://localhost:8001";
    return [
      { source: "/api/:path*", destination: `${gateway}/api/:path*` },
      { source: "/healthz", destination: `${gateway}/healthz` },
    ];
  },
};

export default nextConfig;
