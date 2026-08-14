/**
 * exploEnv Mock Unit Tests
 *
 * Verifies the expo/virtual/env proxy mock: env-var reads, EXPO_PUBLIC_
 * prefix fallback, non-string property handling, and the module-level
 * EXPO_PUBLIC_API_URL default.
 *
 * NOTE: React Native's process.env shim does not support `delete`, and
 * babel-preset-expo rewrites DOTTED `process.env.EXPO_PUBLIC_*` access —
 * all env writes/reads here use computed access to stay intact.
 */

describe('exploEnv (expo/virtual/env mock)', () => {
  let mockEnv: any;

  const env = (): Record<string, any> => process.env as any;

  const loadFresh = () => {
    jest.resetModules();
    mockEnv = require('../exploEnv');
  };

  beforeEach(() => {
    process.env.TEST_ATOM_DIRECT = 'direct-value';
    process.env.TEST_ATOM_PREFIXED = 'prefixed-value';
  });

  afterEach(() => {
    process.env.TEST_ATOM_DIRECT = undefined as any;
    process.env.TEST_ATOM_PREFIXED = undefined as any;
    env()['EXPO_PUBLIC_API_URL'] = '' as any;
    jest.resetModules();
  });

  it('reads environment variables directly from process.env', () => {
    loadFresh();
    expect(mockEnv.TEST_ATOM_DIRECT).toBe('direct-value');
  });

  it('falls back to the EXPO_PUBLIC_ prefixed variable', () => {
    env()['EXPO_PUBLIC_TEST_ATOM_PREFIXED'] = 'prefixed-value';
    loadFresh();
    expect(mockEnv.TEST_ATOM_PREFIXED).toBe('prefixed-value');
  });

  it('returns undefined for unknown variables', () => {
    loadFresh();
    expect(mockEnv.TOTALLY_UNKNOWN_VAR_XYZ).toBeUndefined();
  });

  it('returns undefined for non-string property keys', () => {
    loadFresh();
    expect(mockEnv[Symbol('sym')]).toBeUndefined();
    expect(mockEnv[123]).toBeUndefined();
  });

  it('answers true for has() on any property', () => {
    loadFresh();
    expect('anyRandomProperty' in mockEnv).toBe(true);
  });

  it('sets EXPO_PUBLIC_API_URL to localhost default when missing', () => {
    env()['EXPO_PUBLIC_API_URL'] = '' as any;
    loadFresh();
    expect(env()['EXPO_PUBLIC_API_URL']).toBe('http://localhost:8000');
    expect(mockEnv['EXPO_PUBLIC_API_URL']).toBe('http://localhost:8000');
  });

  it('keeps an existing EXPO_PUBLIC_API_URL value', () => {
    env()['EXPO_PUBLIC_API_URL'] = 'http://custom.example';
    loadFresh();
    expect(env()['EXPO_PUBLIC_API_URL']).toBe('http://custom.example');
    expect(mockEnv['EXPO_PUBLIC_API_URL']).toBe('http://custom.example');
  });
});
