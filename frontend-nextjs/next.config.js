/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // output: 'export', // Disabled for dynamic API routes
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
        destination: "http://127.0.0.1:5059/api/sales/:path*",
      },
      {
        source: "/api/accounting/:path*",
        destination: "http://127.0.0.1:5059/api/accounting/:path*",
      },
      {
        source: "/api/integrations/:path*",
        destination: "http://127.0.0.1:5059/api/v1/integrations/:path*",
      },
      {
        source: "/api/workflows/:path*",
        destination: "http://127.0.0.1:5059/api/v1/workflow-ui/:path*",
      },
      {
        source: "/api/ai/:path*",
        destination: "http://127.0.0.1:5059/api/v1/ai/:path*",
      },
      {
        source: "/api/system/:path*",
        destination: "http://127.0.0.1:5059/api/v1/system/:path*",
      },
      {
        source: "/api/analytics/:path*",
        destination: "http://127.0.0.1:5059/api/v1/analytics/:path*",
      },
      {
        source: "/api/workflow-agent/:path*",
        destination: "http://127.0.0.1:5059/api/workflow-agent/:path*",
      },
      {
        source: "/api/atom-agent/:path*",
        destination: "http://127.0.0.1:5059/api/atom-agent/:path*",
      },
      // Add general API rewrite for other endpoints
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:5059/api/v1/:path*",
      },
      {
        source: "/api/auth/login",
        destination: "http://127.0.0.1:5059/api/auth/login",
      }
    ];
  },
};

module.exports = nextConfig;
