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
    const catalog = process.env.CATALOG_SERVICE_URL ?? "http://localhost:8004";
    return [
      // The shelf answers the storefront directly: it is read every few seconds, and a polling
      // browser has no business on the service that queues GPU jobs. The gateway serves the same
      // routes for any client that goes through it.
      { source: "/api/v1/stock", destination: `${catalog}/api/v1/stock` },
      { source: "/api/v1/stock/:path*", destination: `${catalog}/api/v1/stock/:path*` },
      { source: "/api/:path*", destination: `${gateway}/api/:path*` },
      { source: "/healthz", destination: `${gateway}/healthz` },
      // The Evolus key lives on agent-service, so the chat panel is proxied too.
      { source: "/agent/:path*", destination: `${agent}/agent/:path*` },
      // One origin for the whole shop: an MCP client outside this machine reaches the
      // connector through the page's URL, which is the origin PUBLIC_BASE_URL is set to.
      { source: "/mcp/:path*", destination: `${agent}/mcp/` },
    ];
  },
};

export default nextConfig;
