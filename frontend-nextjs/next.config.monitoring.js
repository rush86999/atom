/** @type {import('next').NextConfig} */

const nextConfig = {
  // ... existing config
  
  // Performance monitoring
  experimental: {
    // ... existing experimental config
    instrument: true,
    nextScriptWorkers: true,
  },
  
  // Analytics setup
  async redirects() {
    return [
      // ... existing redirects
      {
        source: '/analytics',
        destination: '/api/analytics',
        permanent: false,
      },
    ];
  },
};

// Performance monitoring initialization
if (process.env.NODE_ENV === 'production') {
  const { register } = require('next-pwa');
  nextConfig.pwa = {
    dest: 'public',
    disable: process.env.NODE_ENV === 'development',
    register: true,
    skipWaiting: true,
    runtimeCaching: [
      {
        urlPattern: /^https?.*/,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'https-calls',
          networkTimeoutSeconds: 15,
          expiration: {
            maxEntries: 150,
            maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
          },
          cacheKeyWillBeUsed: async ({ request }) => {
            return `${request.url}?mode=${request.mode}`;
          },
        },
      },
    ],
  };
}

module.exports = nextConfig;