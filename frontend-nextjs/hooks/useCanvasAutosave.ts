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
 * A save that rejects with `retryable === false` is an UNCONFIRMED save, not
 * a transient failure. The hook keeps the edits dirty, clears every timer,
 * sets `blocked`, and refuses all further dispatches (idle timer, forced
 * flush, beforeunload, unmount, new edits) until `reset()` receives an
 * authoritative new canvas payload.
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

function isExplicitlyNonRetryable(error: unknown): boolean {
    return (
        typeof error === "object" &&
        error !== null &&
        (error as { retryable?: unknown }).retryable === false
    );
}

export function useCanvasAutosave({
    save,
    delayMs = 3000,
    enabled = true,
    maxRetries = 2,
}: UseCanvasAutosaveOptions) {
    const [status, setStatus] = useState<AutosaveStatus>("idle");
    const [blocked, setBlocked] = useState(false);

    // saveRef is re-assigned every render so the debounce callback always
    // invokes the handler with the freshest closures (latest content refs).
    const saveRef = useRef(save);
    saveRef.current = save;

    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const dirtyRef = useRef(false);
    const attemptsRef = useRef(0);
    const inFlightRef = useRef(false);
    const mountedRef = useRef(true);
    const blockedRef = useRef(false);
    // Incremented by reset() so a save that was already in flight for the
    // superseded payload cannot mark the new payload saved or blocked.
    const generationRef = useRef(0);
    const editRevisionRef = useRef(0);
    const queuedAfterFlightRef = useRef(false);

    const clearTimer = useCallback(() => {
        if (timerRef.current !== null) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    // Related audited mutations share the same no-repeat barrier. Only an
    // authoritative payload reset may release an unconfirmed type change.
    const block = useCallback(() => {
        blockedRef.current = true;
        dirtyRef.current = true;
        clearTimer();
        if (mountedRef.current) {
            setBlocked(true);
            setStatus("error");
        }
    }, [clearTimer]);

    const runSave = useCallback(async (final: boolean): Promise<boolean> => {
        if (blockedRef.current) return false;
        if (inFlightRef.current) {
            queuedAfterFlightRef.current = dirtyRef.current;
            return false;
        }

        inFlightRef.current = true;
        const generation = generationRef.current;
        const editRevision = editRevisionRef.current;
        if (mountedRef.current) setStatus("saving");

        try {
            const ok = await saveRef.current();
            if (generation !== generationRef.current) return false;
            if (ok === false) throw new Error("save handler reported failure");

            // A receipt confirms the dispatched snapshot, not keystrokes
            // typed while it was in flight. Keep the newer edit pending.
            if (editRevision !== editRevisionRef.current) {
                dirtyRef.current = true;
                queuedAfterFlightRef.current = true;
                if (mountedRef.current) setStatus("pending");
                return false;
            }
            dirtyRef.current = false;
            attemptsRef.current = 0;
            if (mountedRef.current) setStatus("saved");
            return true;
        } catch (error) {
            if (generation !== generationRef.current) return false;

            if (isExplicitlyNonRetryable(error)) {
                // Retain the edits: only an authoritative reset may release
                // this canvas. No timer, manual flush, lifecycle hook, or
                // later edit may redispatch the uncertain save.
                blockedRef.current = true;
                dirtyRef.current = true;
                clearTimer();
                if (mountedRef.current) {
                    setBlocked(true);
                    setStatus("error");
                }
                return false;
            }

            if (attemptsRef.current < maxRetries && !final) {
                attemptsRef.current += 1;
                if (mountedRef.current) setStatus("pending");
                clearTimer();
                timerRef.current = setTimeout(() => {
                    timerRef.current = null;
                    if (!blockedRef.current) void runSave(false);
                }, delayMs);
            } else if (mountedRef.current) {
                setStatus("error");
            }
            return false;
        } finally {
            inFlightRef.current = false;
            if (mountedRef.current && !blockedRef.current && dirtyRef.current
                && queuedAfterFlightRef.current) {
                queuedAfterFlightRef.current = false;
                // The current generation's debounce may already be armed.
                // Re-arm only when it expired behind the old worker.
                if (timerRef.current === null) {
                    timerRef.current = setTimeout(() => {
                        timerRef.current = null;
                        void runSave(false);
                    }, delayMs);
                }
            }
        }
    }, [clearTimer, delayMs, maxRetries]);

    /**
     * Record an edit: (re)start the idle timer. Call on EVERY change so the
     * save fires at the end of a typing burst, not in the middle of one.
     */
    const schedule = useCallback(() => {
        if (!enabled || blockedRef.current) return;

        editRevisionRef.current += 1;
        dirtyRef.current = true;
        attemptsRef.current = 0;
        if (mountedRef.current) setStatus("pending");
        clearTimer();
        timerRef.current = setTimeout(() => {
            timerRef.current = null;
            if (!blockedRef.current) void runSave(false);
        }, delayMs);
    }, [clearTimer, delayMs, enabled, runSave]);

    /**
     * Save immediately. By default only fires when edits are pending
     * (unmount / beforeunload); pass force:true for an explicit user save
     * that must always go through, dirty or not. Returns true when there is
     * nothing left to save (or the save was confirmed); false when blocked,
     * already in flight, or the save failed — callers should stop dependent
     * chat work in that case.
     */
    const flush = useCallback(async (opts?: { force?: boolean }): Promise<boolean> => {
        const force = opts?.force ?? false;
        if (blockedRef.current) return false;
        if (inFlightRef.current) return false;
        if (!enabled && !force) return !dirtyRef.current;
        if (!force && !dirtyRef.current) return true;

        clearTimer();
        return runSave(false);
    }, [clearTimer, enabled, runSave]);

    /**
     * Drop pending autosave state WITHOUT saving — call when a fresh payload
     * (agent update, canvas close/navigation) replaces local edits, so a
     * stale timer can't fire afterwards and write the superseded content.
     * This is also the only operation that releases a blocked canvas.
     */
    const reset = useCallback(() => {
        clearTimer();
        generationRef.current += 1;
        editRevisionRef.current += 1;
        queuedAfterFlightRef.current = false;
        dirtyRef.current = false;
        attemptsRef.current = 0;
        blockedRef.current = false;
        if (mountedRef.current) {
            setBlocked(false);
            setStatus("idle");
        }
    }, [clearTimer]);

    // Best-effort flush of pending edits on unmount / tab close. The
    // callbacks are stable (literal options), so this effect runs once.
    useEffect(() => {
        mountedRef.current = true;
        const flushNow = () => {
            if (dirtyRef.current && !blockedRef.current) void flush();
        };
        window.addEventListener("beforeunload", flushNow);
        return () => {
            mountedRef.current = false;
            window.removeEventListener("beforeunload", flushNow);
            clearTimer();
            if (dirtyRef.current && !blockedRef.current) void runSave(true);
        };
    }, [clearTimer, flush, runSave]);

    const revision = useCallback(() => editRevisionRef.current, []);
    return { status, blocked, schedule, flush, reset, block, revision };
}

export default useCanvasAutosave;
