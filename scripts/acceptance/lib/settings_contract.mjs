import crypto from "node:crypto";

/**
 * Pure WA-075 settings helpers.
 *
 * Kept free of Playwright/DOM so they can be unit-tested without a browser
 * (see `scripts/tests/test_browser_settings_acceptance_preflight.py`). The
 * driver imports these; nothing here performs I/O.
 */

/** Decode an RFC 4648 base32 secret (padding and lowercase tolerated). */
export function base32Decode(input) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = String(input).toUpperCase().replace(/[^A-Z2-7]/g, "").replace(/=+$/, "");
  let bits = 0;
  let value = 0;
  const out = [];
  for (const ch of clean) {
    const idx = alphabet.indexOf(ch);
    if (idx < 0) continue;
    value = (value << 5) | idx;
    bits += 5;
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(out);
}

/** RFC 6238 period in milliseconds (SHA-1, 6 digits, 30 s). */
export const TOTP_PERIOD_MS = 30_000;

/** The RFC 6238 time-step index for an instant. */
export function totpStepAtMs(atMs = Date.now()) {
  return Math.floor(atMs / TOTP_PERIOD_MS);
}

/**
 * Milliseconds until `nowMs` sits in a step strictly later than the one
 * consumed at `consumedAtMs`.
 *
 * The backend records `two_factor_last_totp_step` and refuses a second use of
 * the same step (409), so enable/disable/cleanup must each use a later step.
 * The harness waits for the clock; it never computes a code for a future step,
 * because pyotp verifies against the server's current step and would reject
 * that code. `marginMs` keeps the request clear of the boundary; it does not
 * change which step is targeted. `nowMs` is injectable for tests.
 */
export function freshTotpStepDelayMs(
  consumedAtMs, { nowMs = Date.now(), marginMs = 0 } = {},
) {
  const targetMs = (totpStepAtMs(consumedAtMs) + 1) * TOTP_PERIOD_MS + marginMs;
  return Math.max(0, targetMs - nowMs);
}

/** RFC 6238 TOTP (SHA-1, 6 digits, 30 s). `atMs` is injectable for tests. */
export function totpCode(secretBase32, atMs = Date.now()) {
  const key = base32Decode(secretBase32);
  const counter = Math.floor(atMs / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const mac = crypto.createHmac("sha1", key).update(buf).digest();
  const offset = mac[mac.length - 1] & 0x0f;
  const binary = (mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(binary).padStart(6, "0");
}

/** The three fields a provider policy save can change. */
export function normalizePolicy(policy) {
  if (!policy) return null;
  const mode = policy.mode || null;
  return {
    mode,
    // `unset` is the documented legacy default and allows every provider
    // exactly like `automatic` (core/llm/provider_policy.py). The tab has no
    // "unset" control, so behavior comparisons use this derived mode.
    effective_mode: policyMode(mode),
    allowed_providers: [...(policy.allowed_providers || [])].sort(),
    preferred: policy.preferred
      ? { provider: policy.preferred.provider, model: policy.preferred.model }
      : null,
  };
}

/** The mode the UI can represent: `unset` behaves as `automatic`. */
export function policyMode(policyOrMode) {
  const mode = typeof policyOrMode === "string"
    ? policyOrMode : (policyOrMode && policyOrMode.mode);
  if (!mode) return null;
  return mode === "unset" ? "automatic" : mode;
}

export function samePolicy(a, b) {
  const na = normalizePolicy(a);
  const nb = normalizePolicy(b);
  if (!na || !nb) return na === nb;
  // Raw `unset` and explicit `automatic` are the same routing behavior.
  return JSON.stringify({ ...na, mode: na.effective_mode })
    === JSON.stringify({ ...nb, mode: nb.effective_mode });
}

/** Normalize /api/chat/routing-stats into the values the dashboard renders. */
export function routingStatsFrom(json) {
  const stats = (json && (json.stats || json.data?.stats)) || {};
  return {
    enabled: Boolean(json && (json.enabled ?? json.data?.enabled)),
    ema_enabled: Boolean(json && (json.ema_enabled ?? json.data?.ema_enabled)),
    feedback_samples: Number(stats.feedback_samples || 0),
    model_success_rates: stats.model_success_rates || {},
    ema_scores: stats.ema_scores || {},
    stats_error: stats.error || null,
  };
}

/** Parse a rendered metric such as "1,234" back to a number. */
export function toNumber(text) {
  const cleaned = String(text).replace(/[^0-9.-]/g, "");
  if (!cleaned) throw new Error(`not a number: ${text}`);
  return Number(cleaned);
}
