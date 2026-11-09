/** Real in-house test globals: setup-owned hooks and explicitly supplied fallback fixtures. */
import type { MMKV } from 'react-native-mmkv';

export type MockMmkvInstance = Pick<MMKV,
  'set' | 'getString' | 'getNumber' | 'getBoolean' | 'remove' |
  'contains' | 'getAllKeys' | 'clearAll' | 'size'>;

declare global {
  var __mmkvGlobalInstance: MockMmkvInstance | undefined;
  var __resetMmkvMock: (() => void) | undefined;
  var __resetAsyncStorageMock: (() => void) | undefined;
  var __resetSecureStoreMock: (() => void) | undefined;
  // Owned by explicit fallback tests, not created by the default setup.
  var __mmkvStorage: Map<string, unknown> | undefined;
}
