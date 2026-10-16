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
  // Server-side only: the browser talks to /api/v1/* and /agent/*, never to a service origin.
  rewrites() {
    const gateway = process.env.API_GATEWAY_URL ?? "http://localhost:8001";
    const agent = process.env.AGENT_SERVICE_URL ?? "http://localhost:8007";
    return [
      { source: "/api/:path*", destination: `${gateway}/api/:path*` },
      { source: "/healthz", destination: `${gateway}/healthz` },
      // The Evolus key lives on agent-service, so the chat panel is proxied too.
      { source: "/agent/:path*", destination: `${agent}/agent/:path*` },
    ];
  },
};

export default nextConfig;
