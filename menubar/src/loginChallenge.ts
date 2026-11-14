/**
 * Sign-in challenge helpers for the menu bar companion.
 *
 * The backend already answers a password-only attempt with a structured
 * ``two_factor_required`` flag. The native ``login`` command currently turns
 * every refusal into a string error, so this module checks structured fields
 * first (they will start working as soon as the native bridge forwards them)
 * and falls back to the server's stable prompts for today's contract.
 */

/** Number of digits in the TOTP codes accepted by the backend. */
export const TOTP_CODE_LENGTH = 6;

/** Server prompts that mean "password accepted, second factor required". */
const TWO_FACTOR_REQUIRED_MESSAGES = new Set([
  "2fa required",
  "two factor authentication required",
  "two-factor authentication required",
]);

/**
 * Error codes that only occur after the server has established that a second
 * factor is enabled for the account.
 */
const TWO_FACTOR_REQUIRED_CODES = new Set([
  "CONFLICT",
  "INVALID_2FA_CODE",
  "TWO_FACTOR_REQUIRED",
]);

function normalizeMessage(message: string): string {
  return message
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[.!]+$/, "");
}

function extractMessage(error: unknown): string | null {
  if (typeof error === "string") {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    for (const key of ["message", "error", "detail"]) {
      const value = record[key];
      if (typeof value === "string") {
        return value;
      }
      if (value && typeof value === "object") {
        const nested = (value as Record<string, unknown>).message;
        if (typeof nested === "string") {
          return nested;
        }
      }
    }
  }
  return null;
}

/**
 * Turn a Tauri rejection into a message suitable for display.
 *
 * Tauri rejects commands with the Rust error value, which is a string here
 * rather than an ``Error`` instance. Accept both, plus the object shapes used
 * by the HTTP layer, so a refused sign-in never degrades to a generic message.
 */
export function loginErrorMessage(
  error: unknown,
  fallback = "Sign-in failed"
): string {
  const message = extractMessage(error)?.trim();
  return message || fallback;
}

/**
 * True when the sign-in attempt should move to the authenticator-code step.
 *
 * A structured native flag wins when present. Otherwise exactly match the
 * known challenge prompts: broad "two-factor" matching would misclassify
 * terminal errors such as "Two-factor authentication is not configured".
 */
export function isTwoFactorChallenge(error: unknown): boolean {
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    for (const key of ["twoFactorRequired", "two_factor_required"]) {
      const flag = record[key];
      if (typeof flag === "boolean") {
        return flag;
      }
    }
    for (const key of ["code", "error_code"]) {
      const code = record[key];
      if (
        typeof code === "string" &&
        TWO_FACTOR_REQUIRED_CODES.has(code.trim().toUpperCase())
      ) {
        return true;
      }
    }
  }

  return TWO_FACTOR_REQUIRED_MESSAGES.has(
    normalizeMessage(loginErrorMessage(error, ""))
  );
}

/** Keep only the digits a TOTP field can accept. */
export function normalizeTotpCode(value: string): string {
  return value.replace(/\D/g, "").slice(0, TOTP_CODE_LENGTH);
}
