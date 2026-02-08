/**
 * React Native App Configuration for Production
 *
 * Handles code splitting, performance optimizations, and platform-specific configs.
 */

const packageName = require('./package.json').name;

export default {
  name: packageName,
  displayName: 'Atom AI',

  // Production optimizations
  production: {
    // Enable Hermes for improved performance
    hermes: true,

    // Code splitting
    splitChunks: true,

    // Minify code
    minify: true,

    // Remove console statements
    removeConsole: true,

    // Enable inline requires
    inlineRequires: true,
  },

  // Platform-specific configs
  ios: {
    bundleIdentifier: 'com.atomplatform.ai',
    version: '1.0.0',
    buildNumber: '1',
    supportsTablet: true,
  },

  android: {
    package: 'com.atomplatform.ai',
    versionCode: 1,
    versionName: '1.0.0',
    permissions: [
      'CAMERA',
      'ACCESS_FINE_LOCATION',
      'ACCESS_COARSE_LOCATION',
      'ACCESS_BACKGROUND_LOCATION',
      'RECORD_AUDIO',
      'INTERNET',
      'ACCESS_NETWORK_STATE',
      'POST_NOTIFICATIONS'
    ]
  },

  // Deep linking
  schemes: ['atom'],

  // Environment variables
  env: {
    API_BASE_URL: process.env.API_BASE_URL || 'https://api.atom-platform.com',
    WEBSOCKET_URL: process.env.WEBSOCKET_URL || 'wss://api.atom-platform.com',
    ENVIRONMENT: process.env.ENVIRONMENT || 'production',
    SENTRY_DSN: process.env.SENTRY_DSN,
    ANALYTICS_KEY: process.env.ANALYTICS_KEY,
  },

  // Performance optimizations
  performance: {
    // Lazy load heavy components
    lazyImports: {
      '@react-navigation/native-stack': 'react-native-screens',
      '@react-navigation/bottom-tabs': 'react-native-tab-view',
    },
  },

  // Asset handling
  assets: ['./src/assets/'],
};
