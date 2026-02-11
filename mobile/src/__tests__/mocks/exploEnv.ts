/**
 * Mock for expo/virtual/env
 *
 * This module is used by Expo SDK 50+ to access environment variables at build time.
 * In Jest, we provide a mock that mimics process.env behavior.
 */

const originalEnv = process.env;

// Create a mock that returns environment variables
const mockEnv = new Proxy(
  {},
  {
    get: (target, prop) => {
      // Return environment variables from the actual process.env
      if (typeof prop === 'string') {
        return originalEnv[prop] || originalEnv[`EXPO_PUBLIC_${prop}`];
      }
      return undefined;
    },
    has: () => true,
  }
);

// Set EXPO_PUBLIC_API_URL if not already set
if (!process.env.EXPO_PUBLIC_API_URL) {
  process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';
}

module.exports = mockEnv;
