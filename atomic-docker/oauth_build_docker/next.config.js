/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  webpack: (config, { isServer }) => {
    // Fixes npm packages that depend on `fs` module
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback, // if you miss it, all the other options in fallback, specified
        // by next.js will be dropped. Doesn't make much sense, but how it is
        fs: false, // the solution
        child_process: false,
        http2: false,
        tls: false,
        dns: false,
        util: false,
        os: false,
        events: false,
        url: false,
        process: false,
        http: false,
        crypto: false,
        https: false,
        net: false,
      };
      config.ignoreWarnings = [/Failed to parse source map/];
    }

    return config;
  },
  output: 'standalone',
};
