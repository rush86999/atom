"use client";

/**
 * useCanvasAutosave — idle-debounced autosave for canvas editors.
 *
 * Contract follows the established autosave pattern of mature editors
 * (Notion / Google Docs): every edit restarts an idle timer; when the user
 * stops editing for `delayMs`, the save runs. Pending edits are flushed
 * best-effort on unmount and beforeunload, and a failed save retries up to
 * `maxRetries` times before surfacing an "error" status.
 *
 * Idle-debounce (not a fixed interval) is deliberate: the backend appends an
 * audit/version row per save (CanvasAudit via PUT /api/canvas/{id},
 * ArtifactVersion via /api/artifacts/update), so a save per keystroke would
 * bloat the append-only stores. The timer resets on every edit, so a save
 * only fires at typing pauses.
 *
 * The hook never owns WHAT to save: `save` is the component's existing save
 * handler, invoked through a ref so each call closes over the latest state.
 * It must resolve truthy on success; resolving `false` or throwing counts as
 * failure.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type AutosaveStatus = "idle" | "pending" | "saving" | "saved" | "error";

interface UseCanvasAutosaveOptions {
    /** Persist the current editor state. Resolve false / throw on failure. */
    save: () => Promise<boolean | void>;
    /** Idle time after the last edit before saving (ms). Default 3000. */
    delayMs?: number;
    /** Kill switch for the whole mechanism. Default true. */
    enabled?: boolean;
    /** Failed-save retries before surfacing "error". Default 2. */
    maxRetries?: number;
}

export function useCanvasAutosave({
    save,
    delayMs = 3000,
    enabled = true,
    maxRetries = 2,
}: UseCanvasAutosaveOptions) {
    const [status, setStatus] = useState<AutosaveStatus>("idle");

    // saveRef is re-assigned every render so the debounce callback always
    // invokes the handler with the freshest closures (latest content refs).
    const saveRef = useRef(save);
    saveRef.current = save;

    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const dirtyRef = useRef(false);
    const attemptsRef = useRef(0);
    const inFlightRef = useRef(false);
    const mountedRef = useRef(true);

    const clearTimer = useCallback(() => {
        if (timerRef.current !== null) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    const runSave = useCallback(async (final: boolean): Promise<boolean> => {
        if (inFlightRef.current) return false;
        inFlightRef.current = true;
        if (mountedRef.current) setStatus("saving");
        try {
            const ok = await saveRef.current();
            if (ok === false) throw new Error("save handler reported failure");
            dirtyRef.current = false;
            attemptsRef.current = 0;
            if (mountedRef.current) setStatus("saved");
            return true;
        } catch {
            if (attemptsRef.current < maxRetries && !final) {
                attemptsRef.current += 1;
                if (mountedRef.current) setStatus("pending");
                clearTimer();
                timerRef.current = setTimeout(() => {
                    void runSave(false);
                }, delayMs);
            } else if (mountedRef.current) {
                setStatus("error");
            }
            return false;
        } finally {
            inFlightRef.current = false;
        }
    }, [clearTimer, delayMs, maxRetries]);

    /**
     * Record an edit: (re)start the idle timer. Call on EVERY change so the
     * save fires at the end of a typing burst, not in the middle of one.
     */
    const schedule = useCallback(() => {
        if (!enabled) return;
        dirtyRef.current = true;
        attemptsRef.current = 0;
        if (mountedRef.current) setStatus("pending");
        clearTimer();
        timerRef.current = setTimeout(() => {
            void runSave(false);
        }, delayMs);
    }, [clearTimer, delayMs, enabled, runSave]);

    /**
     * Save immediately. By default only fires when edits are pending
     * (unmount / beforeunload); pass force:true for an explicit user save
     * that must always go through, dirty or not.
     */
    const flush = useCallback(async (opts?: { force?: boolean }) => {
        const force = opts?.force ?? false;
        if (inFlightRef.current) return;
        if (!enabled && !force) return;
        if (!force && !dirtyRef.current) return;
        clearTimer();
        await runSave(false);
    }, [clearTimer, enabled, runSave]);

    /**
     * Drop pending autosave state WITHOUT saving — call when a fresh payload
     * (agent update, canvas close/navigation) replaces local edits, so a
     * stale timer can't fire afterwards and write the superseded content.
     */
    const reset = useCallback(() => {
        clearTimer();
        dirtyRef.current = false;
        attemptsRef.current = 0;
        if (mountedRef.current) setStatus("idle");
    }, [clearTimer]);

    // Best-effort flush of pending edits on unmount / tab close. The
    // callbacks are stable (literal options), so this effect runs once.
    useEffect(() => {
        mountedRef.current = true;
        const flushNow = () => {
            if (dirtyRef.current) void flush();
        };
        window.addEventListener("beforeunload", flushNow);
        return () => {
            mountedRef.current = false;
            window.removeEventListener("beforeunload", flushNow);
            clearTimer();
            if (dirtyRef.current) void runSave(true);
        };
    }, [clearTimer, flush, runSave]);

    return { status, schedule, flush, reset };
}

export default useCanvasAutosave;
