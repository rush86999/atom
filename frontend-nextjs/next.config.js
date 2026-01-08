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
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/sales/:path*",
        destination: "http://localhost:8000/api/sales/:path*",
      },
      {
        source: "/api/accounting/:path*",
        destination: "http://localhost:8000/api/accounting/:path*",
      },
      {
        source: "/api/integrations/:path*",
        destination: "http://127.0.0.1:5059/api/integrations/:path*",
      },
      {
        source: "/api/workflows/:path*",
        destination: "http://localhost:8000/api/v1/workflow-ui/:path*",
      },
      {
        source: "/api/ai/:path*",
        destination: "http://localhost:8000/api/v1/ai/:path*",
      },
      {
        source: "/api/system/:path*",
        destination: "http://localhost:8000/api/v1/system/:path*",
      },
      {
        source: "/api/analytics/:path*",
        destination: "http://localhost:8000/api/v1/analytics/:path*",
      },
      {
        source: "/api/workflow-agent/:path*",
        destination: "http://localhost:8000/api/workflow-agent/:path*",
      },
      {
        source: "/api/atom-agent/:path*",
        destination: "http://localhost:8000/api/atom-agent/:path*",
      },
      {
        source: "/api/intelligence/:path*",
        destination: "http://localhost:8000/api/intelligence/:path*",
      },
      {
        source: "/api/time-travel/:path*",
        destination: "http://localhost:8000/api/time-travel/:path*",
      },
      // Add general API rewrite for other endpoints
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
      {
        source: "/api/auth/login",
        destination: "http://localhost:8000/api/auth/login",
      },
      {
        source: "/api/atom/:path*",
        destination: "http://localhost:8000/api/atom/:path*",
      }
    ];
  },
};

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

module.exports = withBundleAnalyzer(nextConfig);
