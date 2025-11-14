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
};

module.exports = nextConfig;
