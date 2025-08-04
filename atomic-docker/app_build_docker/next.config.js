/** @type {import('next').NextConfig} */
const path = require('path');
const webpack = require('webpack');
const NodePolyfillPlugin = require('node-polyfill-webpack-plugin');

const packageJson = require('./package.json');
const withTM = require('next-transpile-modules')([
  '@rneui/base',
  '@rneui/themed',
  '@react-native-picker/picker',
  '@shopify/restyle',
  ...Object.keys(packageJson.dependencies).filter((dep) =>
    dep.startsWith('react-native')
  ),
]);

const nextConfig = {
  reactStrictMode: false,
  transpilePackages: [
    '@rneui/base',
    '@rneui/themed',
    '@react-native-picker/picker',
    '@shopify/restyle',
    ...Object.keys(packageJson.dependencies).filter((dep) =>
      dep.startsWith('react-native')
    ),
  ],
  webpack: (config, { isServer, defaultLoaders }) => {
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

    if (isServer) {
      // provide plugin
      config.plugins.push(
        new webpack.ProvidePlugin({
          requestAnimationFrame: path.resolve(__dirname, './raf.ts'),
        })
      );
    }

    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      // Transform all direct `react-native` imports to `react-native-web`
      'react-native$': 'react-native-web',
      'react-native-vector-icons/MaterialCommunityIcons':
        'react-native-vector-icons/dist/MaterialCommunityIcons',
      'react-native-vector-icons/MaterialIcons':
        'react-native-vector-icons/dist/MaterialIcons',
      'react-native-vector-icons/FontAwesome':
        'react-native-vector-icons/dist/FontAwesome',
      'react-native-vector-icons/AntDesign':
        'react-native-vector-icons/dist/AntDesign',
      'react-native-vector-icons/Entypo':
        'react-native-vector-icons/dist/Entypo',
      'react-native-vector-icons/EvilIcons':
        'react-native-vector-icons/dist/EvilIcons',
      'react-native-vector-icons/Feather':
        'react-native-vector-icons/dist/Feather',
      'react-native-vector-icons/FontAwesome5_Brands':
        'react-native-vector-icons/dist/FontAwesome5_Brands',
      'react-native-vector-icons/FontAwesome5_Solid':
        'react-native-vector-icons/dist/FontAwesome5_Solid',
      'react-native-vector-icons/Foundation':
        'react-native-vector-icons/dist/Foundation',
      'react-native-vector-icons/Ionicons':
        'react-native-vector-icons/dist/Ionicons',
      'react-native-vector-icons/Octicons':
        'react-native-vector-icons/dist/Octicons',
      'react-native-vector-icons/SimpleLineIcons':
        'react-native-vector-icons/dist/SimpleLineIcons',
      'react-native-vector-icons/Zocial':
        'react-native-vector-icons/dist/Zocial',
    };

    config.resolve.extensions = [
      '.web.js',
      '.web.jsx',
      '.web.ts',
      '.web.tsx',
      ...config.resolve.extensions,
    ];

    console.log(__dirname, ' __dirname');
    config.module.rules.push({
      test: /\.(woff|woff2|eot|ttf|otf)$/i,
      type: 'asset/resource',
      generator: {
        //publicPath: '../fonts/',
        filename: 'compiled/fonts/[hash][ext][query]',
      },
      include: [
        // Not sure which one should work so I added both possible paths
        // from this package
        path.resolve(__dirname, '.', 'node_modules'),
        path.resolve(
          __dirname,
          '.',
          'node_modules',
          'react-native-vector-icons'
        ),
      ],
    });

    return config;
  },
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },
};

module.exports = withTM(nextConfig);
