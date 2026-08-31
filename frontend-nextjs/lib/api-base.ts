/**
 * Runtime backend base URL resolution.
 *
 * NEXT_PUBLIC_* vars are inlined at build time and have proven flaky in this
 * dev setup (bundles served with the var missing → every `|| ""` fallback
 * produced RELATIVE fetch URLs that die on the dev proxy's 308 redirect, and
 * the WebSocket hook built `new WebSocket("/ws")` which throws SyntaxError).
 * This resolver works even when inlining fails: explicit env first, then the
 * dev backend port (Makefile PORT ?= 8001), then same-origin in production.
 */
export function getApiBase(): string {
    const fromEnv = (
        process.env.NEXT_PUBLIC_API_URL ||
        process.env.API_BASE_URL ||
        process.env.PYTHON_BACKEND_URL ||
        ""
    ).replace(/\/$/, "");
    if (fromEnv) return fromEnv;
    if (typeof window !== "undefined") {
        if (process.env.NODE_ENV === "development") {
            return `http://${window.location.hostname}:8001`;
        }
        return ""; // same-origin (proxied) in production
    }
    return "";
}
