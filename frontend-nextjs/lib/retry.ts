/**
 * Retry helpers for chat-history hydration.
 *
 * Why this exists (2026-09-10): a backend restart (scripts/
 * restart_backend.sh takes 15–20s) killed in-flight history fetches and
 * both chat surfaces swallowed the failure — the canvas co-editor showed
 * a fresh "💬 Ask the agent" panel and the global widget a welcome-only
 * transcript, with no error and no retry. The websocket auto-reconnects
 * (unlimited, in useWebSocket) while REST state stays stuck until a
 * manual reload.
 *
 * Layering:
 *  - lib/api.ts's axios interceptor already retries transient failures
 *    (1s/2s/4s ≈ 7s window) — shorter than a restart, so consumers still
 *    need reconnect-triggered re-hydration (components watch
 *    useWebSocket().isConnected transitions).
 *  - fetch-style callers (authFetch) have NO retry — this helper adds it.
 */

/** HTTP statuses worth retrying on a later attempt (server bouncing). */
export const TRANSIENT_HTTP_STATUS = new Set([502, 503, 504, 429]);

export interface RetryOptions<T> {
    /** Total attempts including the first (default: 3). */
    attempts?: number;
    /** Delay before retry N (0-indexed) is baseDelayMs * 2^N (default: 500). */
    baseDelayMs?: number;
    /**
     * Decides whether a produced (non-throwing) value should be retried.
     * Throwing fn calls are always retried (network failures). When attempts
     * are exhausted the LAST value/throw is returned/re-thrown — the caller
     * sees a real Response, never a synthetic one.
     */
    shouldRetryValue?: (value: T) => boolean;
}

export async function withRetry<T>(
    fn: () => Promise<T>,
    options: RetryOptions<T> = {}
): Promise<T> {
    const attempts = Math.max(1, options.attempts ?? 3);
    const baseDelayMs = options.baseDelayMs ?? 500;
    const shouldRetryValue = options.shouldRetryValue;
    let lastValue: T | undefined;
    let lastError: unknown;

    for (let attempt = 0; attempt < attempts; attempt++) {
        if (attempt > 0) {
            await new Promise((resolve) =>
                setTimeout(resolve, baseDelayMs * Math.pow(2, attempt - 1))
            );
        }
        try {
            const value = await fn();
            if (!shouldRetryValue || !shouldRetryValue(value)) return value;
            lastValue = value;
        } catch (err) {
            lastError = err;
        }
    }
    if (lastError !== undefined) throw lastError;
    return lastValue as T;
}

/**
 * Fetch-style wrapper: retries network failures and transient HTTP
 * statuses, passes everything else (auth, 404, …) through untouched so
 * caller-side classification (403 stale-session etc.) still works.
 */
export async function fetchWithRetry(
    fn: () => Promise<Response>,
    options: RetryOptions<Response> = {}
): Promise<Response> {
    return withRetry(fn, {
        ...options,
        shouldRetryValue: (res) =>
            !res.ok && TRANSIENT_HTTP_STATUS.has(res.status),
    });
}
