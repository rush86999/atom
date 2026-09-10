import { withRetry, fetchWithRetry, TRANSIENT_HTTP_STATUS } from "../retry";

describe("withRetry", () => {
    it("returns the first successful value without delaying", async () => {
        let calls = 0;
        const value = await withRetry(async () => {
            calls++;
            return "ok";
        });
        expect(value).toBe("ok");
        expect(calls).toBe(1);
    });

    it("retries thrown (network) failures and succeeds", async () => {
        let calls = 0;
        const value = await withRetry(
            async () => {
                calls++;
                if (calls < 3) throw new TypeError("fetch failed");
                return "recovered";
            },
            { baseDelayMs: 1 }
        );
        expect(value).toBe("recovered");
        expect(calls).toBe(3);
    });

    it("retries values flagged by shouldRetryValue (e.g. transient HTTP status)", async () => {
        let calls = 0;
        const value = await withRetry(
            async () => {
                calls++;
                return calls < 2 ? "503" : "200";
            },
            { baseDelayMs: 1, shouldRetryValue: (v) => v === "503" }
        );
        expect(value).toBe("200");
        expect(calls).toBe(2);
    });

    it("throws the LAST error when attempts are exhausted", async () => {
        let calls = 0;
        await expect(
            withRetry(
                async () => {
                    calls++;
                    throw new TypeError(`down ${calls}`);
                },
                { attempts: 3, baseDelayMs: 1 }
            )
        ).rejects.toThrow("down 3");
        expect(calls).toBe(3);
    });

    it("returns the last (still-flagged) value when attempts are exhausted", async () => {
        let calls = 0;
        const value = await withRetry(
            async () => {
                calls++;
                return `503-${calls}`;
            },
            { attempts: 2, baseDelayMs: 1, shouldRetryValue: (v) => v === "503-1" || v === "503-2" }
        );
        expect(value).toBe("503-2");
    });

    it("never retries when attempts is 1", async () => {
        let calls = 0;
        await expect(
            withRetry(
                async () => {
                    calls++;
                    throw new Error("no");
                },
                { attempts: 1, baseDelayMs: 1 }
            )
        ).rejects.toThrow("no");
        expect(calls).toBe(1);
    });
});

describe("fetchWithRetry", () => {
    const res = (status: number, ok?: boolean) =>
        ({ ok: ok ?? (status >= 200 && status < 300), status }) as Response;

    it("passes through a non-transient error status untouched (403 stale-session)", async () => {
        let calls = 0;
        const response = await fetchWithRetry(async () => {
            calls++;
            return res(403);
        }, { baseDelayMs: 1 });
        expect(response.status).toBe(403);
        expect(calls).toBe(1);
    });

    it("retries transient statuses (503) and returns the eventual success", async () => {
        let calls = 0;
        const response = await fetchWithRetry(async () => {
            calls++;
            return calls < 2 ? res(503) : res(200);
        }, { baseDelayMs: 1 });
        expect(response.status).toBe(200);
        expect(calls).toBe(2);
    });

    it("retries network TypeErrors and succeeds", async () => {
        let calls = 0;
        const response = await fetchWithRetry(async () => {
            calls++;
            if (calls < 2) throw new TypeError("Failed to fetch");
            return res(200);
        }, { baseDelayMs: 1 });
        expect(response.status).toBe(200);
        expect(calls).toBe(2);
    });

    it("returns the last transient response when attempts run out (caller classifies)", async () => {
        let calls = 0;
        const response = await fetchWithRetry(async () => {
            calls++;
            return res(503);
        }, { attempts: 3, baseDelayMs: 1 });
        expect(response.status).toBe(503);
        expect(calls).toBe(3);
    });

    it("covers exactly the restart-window statuses", () => {
        expect(TRANSIENT_HTTP_STATUS.has(502)).toBe(true);
        expect(TRANSIENT_HTTP_STATUS.has(503)).toBe(true);
        expect(TRANSIENT_HTTP_STATUS.has(504)).toBe(true);
        expect(TRANSIENT_HTTP_STATUS.has(429)).toBe(true);
        expect(TRANSIENT_HTTP_STATUS.has(403)).toBe(false);
        expect(TRANSIENT_HTTP_STATUS.has(404)).toBe(false);
    });
});
