/** @type {import('next').NextConfig} */
const path = require("path");
const webpack = require("webpack");
const NodePolyfillPlugin = require("node-polyfill-webpack-plugin");

const nextConfig = {
  reactStrictMode: false,
  transpilePackages: [
    "nanoid",
    "@rneui/base",
    "@rneui/themed",
    "@react-native-picker/picker",
    "@shopify/restyle",
  ],
  outputFileTracingRoot: path.join(__dirname, "../../"),
  webpack: (config, { isServer }) => {
    // Fixes npm packages that depend on `fs` module
    if (!isServer) {
      config.resolve.fallback = {
        fs: false,
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
          process: "process/browser",
          Buffer: ["buffer", "Buffer"],
        }),
        new NodePolyfillPlugin(),
      );

      config.ignoreWarnings = [/Failed to parse source map/];
    }

    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      // Transform all direct `react-native` imports to `react-native-web`
      "react-native$": "react-native-web",
      "react-native-vector-icons/MaterialCommunityIcons":
        "react-native-vector-icons/dist/MaterialCommunityIcons",
      "react-native-vector-icons/MaterialIcons":
        "react-native-vector-icons/dist/MaterialIcons",
      "react-native-vector-icons/FontAwesome":
        "react-native-vector-icons/dist/FontAwesome",
      "react-native-vector-icons/AntDesign":
        "react-native-vector-icons/dist/AntDesign",
      "react-native-vector-icons/Entypo":
        "react-native-vector-icons/dist/Entypo",
      "react-native-vector-icons/EvilIcons":
        "react-native-vector-icons/dist/EvilIcons",
      "react-native-vector-icons/Feather":
        "react-native-vector-icons/dist/Feather",
      "react-native-vector-icons/FontAwesome5_Brands":
        "react-native-vector-icons/dist/FontAwesome5_Brands",
      "react-native-vector-icons/FontAwesome5_Solid":
        "react-native-vector-icons/dist/FontAwesome5_Solid",
      "react-native-vector-icons/Foundation":
        "react-native-vector-icons/dist/Foundation",
      "react-native-vector-icons/Ionicons":
        "react-native-vector-icons/dist/Ionicons",
      "react-native-vector-icons/Octicons":
        "react-native-vector-icons/dist/Octicons",
      "react-native-vector-icons/SimpleLineIcons":
        "react-native-vector-icons/dist/SimpleLineIcons",
      "react-native-vector-icons/Zocial":
        "react-native-vector-icons/dist/Zocial",
      // Shared components between NextJS and Desktop app
      "@shared-components": path.resolve(
        __dirname,
        "../src/ui-shared/components",
      ),
      "@shared-hooks": path.resolve(__dirname, "../src/ui-shared/hooks"),
      "@shared": path.resolve(__dirname, "../src/ui-shared"),
      // Main project src directory aliases
      "@/services": path.resolve(__dirname, "../../src/services"),
      "@/orchestration": path.resolve(__dirname, "../../src/orchestration"),
      "@/llm": path.resolve(__dirname, "../../src/llm"),
      "@/utils": path.resolve(__dirname, "../../src/utils"),
    };

    config.resolve.extensions = [
      ".web.js",
      ".web.jsx",
      ".web.ts",
      ".web.tsx",
      ...config.resolve.extensions,
    ];

    config.module.rules.push({
      test: /\.(woff|woff2|eot|ttf|otf)$/i,
      type: "asset/resource",
      generator: {
        filename: "compiled/fonts/[hash][ext][query]",
      },
      include: [
        path.resolve(__dirname, ".", "node_modules"),
        path.resolve(
          __dirname,
          ".",
          "node_modules",
          "react-native-vector-icons",
        ),
      ],
    });

    return config;
  },
  output: "standalone",
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
};

module.exports = nextConfig;
