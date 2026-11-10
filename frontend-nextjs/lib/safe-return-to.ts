/**
 * Same-app post-login return-target validation.
 *
 * RFC 9700 (OAuth 2.0 Security BCP) requires one-time authorization codes and
 * forbids credential material in redirect URLs. The handoff code is exchanged
 * by the callback page, but the server-provided `return_to` is still untrusted
 * input and must not become an open redirect or an auth-loop target.
 *
 * This mirrors backend/api/sso_oidc_routes.py::_safe_return_to. It accepts
 * only a relative same-origin path (+ optional query), rejecting
 * protocol-relative, backslash, control, encoded-danger and auth-recursive
 * targets.
 */

const MAX_RETURN_TO_LENGTH = 2048;
const BLOCKED_PATH_PREFIXES = ['/api/auth', '/auth', '/login'] as const;
const RELATIVE_BASE = 'http://same-app.invalid';

function hasControlCharacter(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0)!;
    if (code < 32 || code === 127) return true;
  }
  return false;
}

function rawPath(value: string): string {
  const queryOrFragment = value.search(/[?#]/);
  return queryOrFragment === -1 ? value : value.slice(0, queryOrFragment);
}

function hasDotSegment(pathname: string): boolean {
  return pathname.split('/').some((segment) => segment === '.' || segment === '..');
}

function hasBlockedPrefix(pathname: string): boolean {
  const lower = pathname.toLowerCase();
  return BLOCKED_PATH_PREFIXES.some(
    (blocked) => lower === blocked || lower.startsWith(`${blocked}/`),
  );
}

export function validateSameAppReturnTo(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  if (!value || value.length > MAX_RETURN_TO_LENGTH || value !== value.trim()) {
    return null;
  }
  if (hasControlCharacter(value) || value.includes('\\')) return null;
  if (!value.startsWith('/') || value.startsWith('//')) return null;

  try {
    const parsed = new URL(value, RELATIVE_BASE);
    if (
      parsed.origin !== RELATIVE_BASE ||
      parsed.username ||
      parsed.password ||
      parsed.hash
    ) {
      return null;
    }
  } catch {
    return null;
  }

  // Decode repeatedly so encoded variants cannot smuggle a second redirect or
  // an auth-recursive target past the checks. Three passes matches the backend.
  let decoded = value;
  let stable = false;
  for (let pass = 0; pass < 3; pass += 1) {
    let next: string;
    try {
      next = decodeURIComponent(decoded);
    } catch {
      return null;
    }
    if (next === decoded) {
      stable = true;
      break;
    }
    decoded = next;
  }
  if (!stable) return null;
  if (decoded !== decoded.trim()) return null;
  if (hasControlCharacter(decoded) || decoded.includes('\\')) return null;
  if (!decoded.startsWith('/') || decoded.startsWith('//')) return null;

  try {
    const parsed = new URL(decoded, RELATIVE_BASE);
    if (
      parsed.origin !== RELATIVE_BASE ||
      parsed.username ||
      parsed.password ||
      parsed.hash
    ) {
      return null;
    }
  } catch {
    return null;
  }

  const pathname = rawPath(decoded);
  if (hasDotSegment(pathname) || hasBlockedPrefix(pathname)) return null;
  return value;
}

export function safeReturnTo(value: unknown, fallback = '/dashboard'): string {
  return validateSameAppReturnTo(value) ?? fallback;
}
