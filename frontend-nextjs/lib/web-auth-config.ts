/** Server authentication never infers an authority from a browser/dev fallback. */
export function resolveWebAuthBackend(): string {
  resolveWebAuthSecret();
  const configured = process.env.API_BASE_URL || process.env.PYTHON_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!configured || !configured.trim()) throw new Error('WEB_AUTH_BACKEND_REQUIRED');
  let url: URL;
  try { url = new URL(configured); } catch { throw new Error('WEB_AUTH_BACKEND_INVALID'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash)
    throw new Error('WEB_AUTH_BACKEND_INVALID');
  return url.href.replace(/\/+$/, '');
}

/** One explicitly configured web issuer, never a public fallback/backend JWT key. */
export function resolveWebAuthSecret(): string {
  const configured = process.env.NEXTAUTH_SECRET;
  if (typeof configured === 'string' && configured.trim() && configured !== 'your-secret-key-change-in-production') return configured;
  throw new Error('NEXTAUTH_SECRET is required; run the existing quickstart configuration setup');
}
