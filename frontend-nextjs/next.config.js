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
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }

    // Transpile shared UI components from src directory
    config.module.rules.push({
      test: /\.(ts|tsx)$/,
      include: [
        path.resolve(__dirname, "../src/ui-shared"),
        path.resolve(__dirname, "../src"),
      ],
      use: [
        {
          loader: "babel-loader",
          options: {
            presets: ["next/babel"],
          },
        },
      ],
    });

    return config;
  },
  transpilePackages: ["../src/ui-shared", "../src"],
};

const path = require("path");
module.exports = nextConfig;
