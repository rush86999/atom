/** @type {import('next').NextConfig} */

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    domains: [
      "localhost",
      "127.0.0.1",
      "api.slack.com",
      "graph.microsoft.com",
      "github.com",
      "gitlab.com",
      "api.atlassian.com",
      "api.notion.com",
      "calendar.google.com",
      "drive.google.com",
      "mail.google.com",
      "outlook.office.com",
      "api.hubspot.com",
      "api.salesforce.com",
      "api.stripe.com",
      "quickbooks.api.intuit.com",
      "api.xero.com",
      "api.zendesk.com",
      "zoom.us",
      "discord.com",
      "api.freshdesk.com",
      "us1.admin.mailchimp.com",
      "public.tableau.com",
      "app.asana.com",
      "api.trello.com",
      "api.linear.app",
      "api.airtable.com",
      "app.box.com",
      "teams.microsoft.com",
      "chat.googleapis.com"
    ],
    formats: ['image/webp', 'image/avif'],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },
  transpilePackages: [
    "@chakra-ui/react",
    "@chakra-ui/icons",
    "@ark-ui/react",
    "react-icons",
    "date-fns",
    "recharts"
  ],
  experimental: {
    externalDir: true,
    optimizeCss: true,
    scrollRestoration: true,
    largePageDataBytes: 128 * 1000, // 128KB
    turbo: {
      loaders: ['css'],
      resolveAlias: {
        '@': './',
      },
    },
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
    styledComponents: true,
  },
  poweredByHeader: false,
  generateEtags: true,
  compress: true,
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/health/:path*',
          destination: '/api/health/:path*',
        },
        {
          source: '/api/integrations/:service/:action',
          destination: '/api/integrations/[service]/[action]',
        },
      ],
    };
  },
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, must-revalidate, max-age=0',
          },
          {
            key: 'Access-Control-Allow-Origin',
            value: process.env.NODE_ENV === 'production' ? 'https://yourdomain.com' : '*',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type, Authorization',
          },
        ],
      },
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        source: '/images/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
  async redirects() {
    return [
      {
        source: '/docs',
        destination: 'https://docs.yourapp.com',
        permanent: true,
      },
      {
        source: '/support',
        destination: 'https://support.yourapp.com',
        permanent: true,
      },
    ];
  },
  webpack: (config, { isServer, dev }) => {
    // Optimize bundle size
    if (!dev && !isServer) {
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            chunks: 'all',
          },
          chakra: {
            test: /[\\/]node_modules[\\/](@chakra-ui)[\\/]/,
            name: 'chakra',
            chunks: 'all',
          },
          integrations: {
            test: /[\\/]pages[\\/]integrations[\\/]/,
            name: 'integrations',
            chunks: 'all',
          },
        },
      };
    }

    // Add aliases for cleaner imports
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': require('path').resolve('.'),
      '@/components': require('path').resolve('./components'),
      '@/pages': require('path').resolve('./pages'),
      '@/styles': require('path').resolve('./styles'),
      '@/utils': require('path').resolve('./utils'),
    };

    return config;
  },
  // Performance optimizations
  maxThreads: 2,
  // Disable source maps in production for smaller bundle size
  productionBrowserSourceMaps: false,
  // Enable React concurrent features
  concurrentFeatures: true,
  // Optimize server-side rendering
  serverComponentsExternalPackages: ['@chakra-ui/react', 'react-icons'],
};

module.exports = nextConfig;