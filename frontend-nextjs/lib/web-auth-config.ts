import { getApiBase } from './api-base';

export function resolveWebAuthBackend(): string {
  return getApiBase() || 'http://127.0.0.1:8000';
}

/** Both cookie readers use the same web issuer, never a backend JWT key. */
export function resolveWebAuthSecret(): string {
  const configured = process.env.NEXTAUTH_SECRET;
  if (typeof configured === 'string' && configured.trim()) return configured;
  if (process.env.NODE_ENV === 'production') throw new Error('NEXTAUTH_SECRET is required in production');
  return 'development-fallback-secret-123';
}
