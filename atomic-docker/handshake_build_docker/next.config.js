/** @type {import('next').NextConfig} */
const webpack = require('webpack');
const NodePolyfillPlugin = require('node-polyfill-webpack-plugin');
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

      config.plugins.push(
        new webpack.ProvidePlugin({
          process: 'process/browser',
          Buffer: ['buffer', 'Buffer'],
        }),
        new webpack.NormalModuleReplacementPlugin(/node:/, (resource) => {
          const mod = resource.request.replace(/^node:/, '');
          switch (mod) {
            case 'buffer':
              resource.request = 'buffer';
              break;
            case 'stream':
              resource.request = 'readable-stream';
              break;
            case 'fs':
              resource.request = 'fs';
              break;
            case 'child_process':
              resource.request = 'child_process';
              break;
            case 'http2':
              resource.request = 'http2';
              break;
            case 'tls':
              resource.request = 'tls';
              break;
            case 'dns':
              resource.request = 'dns';
              break;
            case 'util':
              resource.request = 'util';
              break;
            case 'os':
              resource.request = 'os';
              break;
            case 'events':
              resource.request = 'events';
              break;
            case 'url':
              resource.request = 'url';
              break;

            case 'process':
              resource.request = 'process';
              break;
            case 'http':
              resource.request = 'http';
              break;
            case 'crypto':
              resource.request = 'crypto';
              break;
            case 'https':
              resource.request = 'https';
              break;
            case 'net':
              resource.request = 'net';
              break;

            default:
              throw new Error(`Not found ${mod}`);
          }
        }),
        new NodePolyfillPlugin()
      );
      config.ignoreWarnings = [/Failed to parse source map/];
    }

    return config;
  },
  output: 'standalone',
};
