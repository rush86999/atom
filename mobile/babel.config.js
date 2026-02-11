module.exports = function(api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxRuntime: 'automatic', preserveEnvVars: true }],
    ],
    plugins: [
      'react-native-reanimated/plugin',
    ],
  };
};
