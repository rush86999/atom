"use client";

import React, { useEffect, useRef, useState } from "react";
import { CANVAS } from "@/src/lib/testIds";
import { CANVAS_TYPE_OPTIONS, isTypeSwitchable, type SwitchableCanvasType } from "./canvasType";

const BADGE_CLASS =
    "text-[8px] h-3.5 px-1 uppercase bg-zinc-100 dark:bg-white/5 border border-zinc-200 dark:border-white/10 text-zinc-500 flex items-center rounded";

/**
 * The canvas type badge in the panel header. For text-like canvas types the
 * badge becomes a dropdown that manually retypes the canvas — the escape
 * hatch for a wrong type the agent-chat classifier picked. Specialized types
 * (office files, charts, forms) render as a plain badge.
 */
export function CanvasTypeBadge({
    component,
    onSwitch,
}: {
    component: string;
    onSwitch: (target: SwitchableCanvasType) => void;
}) {
    const [open, setOpen] = useState(false);
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const onDocClick = (e: MouseEvent) => {
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", onDocClick);
        return () => document.removeEventListener("mousedown", onDocClick);
    }, [open]);

    if (!isTypeSwitchable(component)) {
        return (
            <span data-testid={`${CANVAS.TYPE_PREFIX}${component}`} className={BADGE_CLASS}>
                {component}
            </span>
        );
    }

    return (
        <div className="relative" ref={rootRef}>
            <button
                data-testid={`${CANVAS.TYPE_PREFIX}${component}`}
                onClick={() => setOpen(!open)}
                title="Change canvas type"
                aria-haspopup="listbox"
                aria-expanded={open}
                className={`${BADGE_CLASS} hover:border-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors cursor-pointer`}
            >
                {/* Label and ▾ in separate text nodes — tests (and any exact
                    text matching) key on the bare component name. */}
                <span>{component}</span>
                <span aria-hidden="true">▾</span>
            </button>
            {open && (
                <div
                    role="listbox"
                    data-testid="canvas-type-menu"
                    className="absolute left-0 top-full mt-1 z-40 w-36 bg-white dark:bg-[#1e293b] border border-zinc-200 dark:border-white/10 rounded-lg shadow-lg py-1"
                >
                    <p className="px-2 pb-1 text-[9px] uppercase tracking-wider text-zinc-400">Change type</p>
                    {CANVAS_TYPE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            role="option"
                            aria-selected={opt.value === component}
                            data-testid={`canvas-type-option-${opt.value}`}
                            onClick={() => { setOpen(false); if (opt.value !== component) onSwitch(opt.value); }}
                            className={`w-full text-left px-2 py-1.5 text-[11px] transition-colors ${
                                opt.value === component
                                    ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 font-medium"
                                    : "text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/5"
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
