const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  output: 'standalone',
  images: {
    unoptimized: true,
  },
  transpilePackages: ["@chakra-ui/react", "@chakra-ui/icons", "@ark-ui/react"],
  outputFileTracingRoot: path.join(__dirname, "../../"),
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/sales/:path*",
        destination: "http://127.0.0.1:8000/api/sales/:path*",
      },
      {
        source: "/api/accounting/:path*",
        destination: "http://127.0.0.1:8000/api/accounting/:path*",
      },
      {
        source: "/api/integrations/:path*",
        destination: "http://127.0.0.1:5059/api/integrations/:path*",
      },
      {
        source: "/api/workflows/:path*",
        destination: "http://127.0.0.1:8000/api/v1/workflow-ui/:path*",
      },
      {
        source: "/api/ai/:path*",
        destination: "http://127.0.0.1:8000/api/v1/ai/:path*",
      },
      {
        source: "/api/system/:path*",
        destination: "http://127.0.0.1:8000/api/v1/system/:path*",
      },
      {
        source: "/api/analytics/:path*",
        destination: "http://127.0.0.1:8000/api/v1/analytics/:path*",
      },
      {
        source: "/api/workflow-agent/:path*",
        destination: "http://127.0.0.1:8000/api/workflow-agent/:path*",
      },
      {
        source: "/api/atom-agent/:path*",
        destination: "http://127.0.0.1:8000/api/atom-agent/:path*",
      },
      {
        source: "/api/intelligence/:path*",
        destination: "http://127.0.0.1:8000/api/intelligence/:path*",
      },
      {
        source: "/api/time-travel/:path*",
        destination: "http://127.0.0.1:8000/api/time-travel/:path*",
      },
      {
        source: "/api/workflow-templates/:path*",
        destination: "http://127.0.0.1:8000/api/workflow-templates/:path*",
      },
      // Chat Rewrite
      {
        source: "/api/chat/:path*",
        destination: "http://127.0.0.1:8000/api/chat/:path*",
      },
      // Add general API rewrite for other endpoints
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
      // Specific Auth Rewrites (Delegate only these to Python Backend)
      {
        source: "/api/auth/login",
        destination: "http://127.0.0.1:8000/api/auth/login",
      },
      {
        source: "/api/auth/register",
        destination: "http://127.0.0.1:8000/api/auth/register",
      },
      {
        source: "/api/auth/profile",
        destination: "http://127.0.0.1:8000/api/auth/profile",
      },
      {
        source: "/api/auth/me",
        destination: "http://127.0.0.1:8000/api/auth/me",
      },
      {
        source: "/api/auth/accounts",
        destination: "http://127.0.0.1:8000/api/auth/accounts",
      },
      {
        source: "/api/auth/logout",
        destination: "http://127.0.0.1:8000/api/auth/logout",
      },
      {
        source: "/api/auth/refresh",
        destination: "http://127.0.0.1:8000/api/auth/refresh",
      },
      {
        source: "/api/auth/forgot-password",
        destination: "http://127.0.0.1:8000/api/auth/forgot-password",
      },
      {
        source: "/api/auth/reset-password",
        destination: "http://127.0.0.1:8000/api/auth/reset-password",
      },
      {
        source: "/api/auth/verify-token",
        destination: "http://127.0.0.1:8000/api/auth/verify-token",
      },
      {
        source: "/api/auth/change-password",
        destination: "http://127.0.0.1:8000/api/auth/change-password",
      },
      {
        source: "/api/atom/:path*",
        destination: "http://127.0.0.1:8000/api/atom/:path*",
      },
      {
        source: "/api/agents/:path*",
        destination: "http://127.0.0.1:8000/api/agents/:path*",
      },
      // WebSocket Proxy - REMOVED to prevent ECONNRESET crashes
      // Frontend now connects directly to port 8000 (see hooks/useWebSocket.ts)
      /*
      {
        source: "/ws",
        destination: "http://127.0.0.1:8000/ws",
      },
      {
        source: "/ws/:path*",
        destination: "http://127.0.0.1:8000/ws/:path*",
      }
      */
    ];
  },
};

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

module.exports = withBundleAnalyzer(nextConfig);
