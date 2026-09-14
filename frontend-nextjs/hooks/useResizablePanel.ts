"use client";

/**
 * useResizablePanel — drag-resize for a docked side panel.
 *
 * Powers the draggable vertical border between a canvas view and its chat
 * panel (pages/canvas/[id].tsx): the user can shove the divider left to make
 * the chat small and right to make it large (and the reverse for a
 * left-docked panel).
 *
 * Contract
 * - `width` is the panel's pixel width, always clamped to
 *   `[minWidth, min(maxWidth, viewport - viewportReserve)]` so the panel can
 *   never swallow the whole workspace, and the cap shrinks with the window.
 * - Dragging is driven by window-level pointer listeners armed on pointerdown
 *   (no pointer-capture dependency — jsdom and touch both work).
 * - Arrow keys resize (a11y: the handle is a `role="separator"`), Home/End
 *   jump to the smallest/largest size, and double-click resets the default.
 * - `storageKey` persists the width so "make it small" survives a reload.
 *   The read happens in an effect (never during render) so SSR output stays
 *   the default width and hydration is not perturbed.
 */

import type * as React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface UseResizablePanelOptions {
    /** Width used before any stored value is restored. */
    defaultWidth: number;
    /** Smallest allowed width, in px. Defaults to 220. */
    minWidth?: number;
    /** Largest allowed width, in px. Defaults to 900. */
    maxWidth?: number;
    /**
     * Which edge of the workspace the panel is docked to.
     * `"right"` (default): dragging the border LEFT grows the panel.
     */
    side?: "left" | "right";
    /** Px moved per arrow-key press. Defaults to 16. */
    keyboardStep?: number;
    /** localStorage key; when omitted the width is not persisted. */
    storageKey?: string;
    /** Workspace px kept visible for the other pane when capping the max. */
    viewportReserve?: number;
}

export interface ResizablePanelHandleProps {
    role: "separator";
    "aria-orientation": "vertical";
    "aria-label": string;
    "aria-valuenow": number;
    "aria-valuemin": number;
    "aria-valuemax": number;
    tabIndex: 0;
    onPointerDown: (event: React.PointerEvent<HTMLElement>) => void;
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => void;
    onDoubleClick: (event: React.MouseEvent<HTMLElement>) => void;
}

export interface UseResizablePanelResult {
    width: number;
    minWidth: number;
    maxWidth: number;
    isResizing: boolean;
    /** Spread onto the divider element. */
    handleProps: ResizablePanelHandleProps;
    setWidth: (value: number) => void;
    reset: () => void;
}

export function useResizablePanel({
    defaultWidth,
    minWidth = 220,
    maxWidth = 900,
    side = "right",
    keyboardStep = 16,
    storageKey,
    viewportReserve = 320,
}: UseResizablePanelOptions): UseResizablePanelResult {
    // Keep the SSR/first-client render at the default width; the stored value
    // is adopted in an effect (see module docstring).
    const [width, setWidthState] = useState(() =>
        Math.min(Math.max(Math.round(defaultWidth), minWidth), Math.max(minWidth, maxWidth))
    );
    const [isResizing, setIsResizing] = useState(false);

    const clamp = useCallback(
        (value: number): number => {
            let upper = Math.max(minWidth, maxWidth);
            if (typeof window !== "undefined" && window.innerWidth > 0) {
                upper = Math.max(
                    minWidth,
                    Math.min(upper, window.innerWidth - viewportReserve)
                );
            }
            const rounded = Math.round(Number.isFinite(value) ? value : defaultWidth);
            return Math.min(Math.max(rounded, minWidth), upper);
        },
        [defaultWidth, minWidth, maxWidth, viewportReserve]
    );

    const widthRef = useRef(width);
    useEffect(() => {
        widthRef.current = width;
    }, [width]);

    const setWidth = useCallback(
        (value: number) => setWidthState(clamp(value)),
        [clamp]
    );

    const reset = useCallback(() => setWidthState(clamp(defaultWidth)), [clamp, defaultWidth]);

    // ── Restore / persist ────────────────────────────────────────────────
    // `loadedKeyRef` gates the persist effect so a mount-time (or key-change)
    // write cannot clobber the stored value before it has been read back.
    const loadedKeyRef = useRef<string | null>(null);
    const [restored, setRestored] = useState(false);

    useEffect(() => {
        if (!storageKey || typeof window === "undefined") {
            loadedKeyRef.current = storageKey ?? null;
            setRestored(true);
            return;
        }
        if (loadedKeyRef.current !== storageKey) {
            try {
                const raw = window.localStorage.getItem(storageKey);
                const parsed = raw == null ? NaN : Number(raw);
                if (Number.isFinite(parsed) && parsed > 0) {
                    setWidthState(clamp(parsed));
                }
            } catch {
                // Private mode / storage disabled — fall back to the default.
            }
            loadedKeyRef.current = storageKey;
        }
        setRestored(true);
    }, [storageKey, clamp]);

    useEffect(() => {
        if (!storageKey || !restored || loadedKeyRef.current !== storageKey) return;
        try {
            window.localStorage.setItem(storageKey, String(Math.round(width)));
        } catch {
            // Persisting is best-effort.
        }
    }, [storageKey, restored, width]);

    // Keep the panel inside the window when the window shrinks.
    useEffect(() => {
        if (typeof window === "undefined") return;
        const onWindowResize = () => setWidthState((current) => clamp(current));
        window.addEventListener("resize", onWindowResize);
        return () => window.removeEventListener("resize", onWindowResize);
    }, [clamp]);

    // ── Drag ─────────────────────────────────────────────────────────────
    const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

    const handlePointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
        if (event.pointerType === "mouse" && event.button !== 0) return;
        // preventDefault would otherwise swallow the focus that makes the
        // arrow-key resize work right after a click — claim it explicitly.
        event.preventDefault();
        (event.currentTarget as HTMLElement)?.focus?.();
        dragRef.current = { startX: event.clientX, startWidth: widthRef.current };
        setIsResizing(true);
    }, []);

    useEffect(() => {
        if (!isResizing || typeof window === "undefined") return;
        const onMove = (event: PointerEvent) => {
            const drag = dragRef.current;
            if (!drag) return;
            // Dragging left yields a positive delta.
            const delta = drag.startX - event.clientX;
            setWidthState(clamp(drag.startWidth + (side === "right" ? delta : -delta)));
        };
        const stop = () => {
            dragRef.current = null;
            setIsResizing(false);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", stop);
        window.addEventListener("pointercancel", stop);
        return () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", stop);
        };
    }, [isResizing, side, clamp]);

    // While dragging, suppress text selection + show the resize cursor
    // everywhere (the pointer outruns the 6px handle).
    useEffect(() => {
        if (!isResizing || typeof document === "undefined") return;
        const { body } = document;
        const prevCursor = body.style.cursor;
        const prevSelect = body.style.userSelect;
        body.style.cursor = "col-resize";
        body.style.userSelect = "none";
        return () => {
            body.style.cursor = prevCursor;
            body.style.userSelect = prevSelect;
        };
    }, [isResizing]);

    const handleKeyDown = useCallback(
        (event: React.KeyboardEvent<HTMLElement>) => {
            // ArrowLeft moves the border left: grows a right-docked panel,
            // shrinks a left-docked one.
            const growOnLeft = side === "right" ? 1 : -1;
            if (event.key === "ArrowLeft") {
                event.preventDefault();
                setWidthState((current) => clamp(current + growOnLeft * keyboardStep));
            } else if (event.key === "ArrowRight") {
                event.preventDefault();
                setWidthState((current) => clamp(current - growOnLeft * keyboardStep));
            } else if (event.key === "Home") {
                event.preventDefault();
                setWidthState(clamp(minWidth));
            } else if (event.key === "End") {
                event.preventDefault();
                setWidthState(clamp(Number.MAX_SAFE_INTEGER));
            }
        },
        [clamp, keyboardStep, minWidth, side]
    );

    const handleDoubleClick = useCallback(
        (event: React.MouseEvent<HTMLElement>) => {
            event.preventDefault();
            reset();
        },
        [reset]
    );

    const effectiveMax = useMemo(() => clamp(Number.MAX_SAFE_INTEGER), [clamp]);

    const handleProps = useMemo<ResizablePanelHandleProps>(
        () => ({
            role: "separator",
            "aria-orientation": "vertical",
            "aria-label": "Resize panel",
            "aria-valuenow": width,
            "aria-valuemin": minWidth,
            "aria-valuemax": effectiveMax,
            tabIndex: 0,
            onPointerDown: handlePointerDown,
            onKeyDown: handleKeyDown,
            onDoubleClick: handleDoubleClick,
        }),
        [width, minWidth, effectiveMax, handlePointerDown, handleKeyDown, handleDoubleClick]
    );

    return {
        width,
        minWidth,
        maxWidth: effectiveMax,
        isResizing,
        handleProps,
        setWidth,
        reset,
    };
}

export default useResizablePanel;
