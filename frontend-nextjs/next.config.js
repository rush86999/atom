/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    domains: ["localhost", "127.0.0.1", "api.slack.com", "graph.microsoft.com"],
  },
  transpilePackages: ["@chakra-ui/react", "@chakra-ui/icons", "@ark-ui/react"],
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [
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
    ];
  },
};

module.exports = nextConfig;
