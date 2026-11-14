/**
 * Global helpers installed by jest.setup.js and consumed by test utilities.
 *
 * Declaring them here keeps test helpers strictly typed without resorting to
 * `global as any` casts at every call site.
 */

import type { AppStateStatus } from 'react-native';

interface MmkvMockInstance {
  set: jest.Mock<void, [string, string | number | boolean]>;
  getString: jest.Mock<string | undefined, [string]>;
  getAllKeys: jest.Mock<string[], []>;
  removeAll: jest.Mock<void, []>;
}

declare global {
  // eslint-disable-next-line no-var
  var __resetAsyncStorageMock: (() => void) | undefined;
  // eslint-disable-next-line no-var
  var __resetSecureStoreMock: (() => void) | undefined;
  // eslint-disable-next-line no-var
  var __resetMmkvMock: (() => void) | undefined;
  // eslint-disable-next-line no-var
  var __mmkvGlobalInstance: MmkvMockInstance | undefined;
  // eslint-disable-next-line no-var
  var __mmkvStorage: Map<string, unknown> | undefined;
  // eslint-disable-next-line no-var
  var __atomNavStateCapture:
    | ((state: unknown, screenName?: string) => void)
    | undefined;
  // eslint-disable-next-line no-var
  var appStateListeners: Array<(status: AppStateStatus) => void>;
}

export {};
