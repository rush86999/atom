/** Verify helper behavior against the installed React Native Platform.select contract. */
import { Platform } from 'react-native';
import { mockPlatform, restorePlatform } from '../testUtils';

describe.each(['ios', 'android'] as const)('Platform selection on %s', platform => {
  beforeEach(() => { mockPlatform(platform); });
  afterEach(() => { restorePlatform(); });

  test('never borrows an unsupported platform value', () => {
    const options = platform === 'ios' ? { android: 'foreign', default: 'fallback' } : { ios: 'foreign', default: 'fallback' };
    expect(Platform.select(options)).toBe('fallback');
  });

  test('an explicitly selected undefined stays undefined', () => {
    const options = platform === 'ios' ? { ios: undefined, native: 'native', default: 'fallback' } : { android: undefined, native: 'native', default: 'fallback' };
    expect(Platform.select(options)).toBeUndefined();
  });

  test('native takes precedence over default when the platform key is absent', () => {
    expect(Platform.select({ native: 'native', default: 'fallback' })).toBe('native');
  });

  test('selected zero is preserved', () => {
    expect(Platform.select({ ios: 0, android: 0, default: 123 })).toBe(0);
  });

  test('selected false is preserved', () => {
    expect(Platform.select({ ios: false, android: false, default: true })).toBe(false);
  });
});
