/**
 * React Native Mock
 *
 * This mock file is loaded before all other imports to prevent TurboModule errors.
 * It must be in the __mocks__ directory at the root of the mobile project.
 */

const ReactNative = jest.requireActual('react-native');

// Mock SettingsManager to prevent TurboModule errors
const MockSettingsManager = {
  settings: {},
  getSettings: jest.fn(() => ({})),
  setSettings: jest.fn(() => {}),
  watchSettings: jest.fn(() => ({ remove: jest.fn() })),
};

module.exports = {
  ...ReactNative,
  NativeModules: {
    ...ReactNative.NativeModules,
    SettingsManager: MockSettingsManager,
  },
  TurboModuleRegistry: {
    getEnforcing: jest.fn((name) => {
      if (name === 'SettingsManager') {
        return MockSettingsManager;
      }
      return {};
    }),
  },
};
