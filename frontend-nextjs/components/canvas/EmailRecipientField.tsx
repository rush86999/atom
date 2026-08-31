"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * Recipient input with address-book autocomplete for the email canvas
 * composer (To / Cc rows).
 *
 * Suggestions come from GET /api/canvas/email/contacts?q=… — the connected
 * mailbox's address book (the same account Send dispatches through). No
 * mailbox connected → the endpoint returns an empty list and this degrades
 * to a plain free-text input.
 *
 * The value is a comma-separated string ("a@x.com, b@x.com"); autocomplete
 * operates on the token being typed after the last comma.
 */
export function EmailRecipientField({
    label,
    value,
    onChange,
    placeholder,
    inputClassName,
    testId,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    inputClassName?: string;
    testId?: string;
}) {
    const [suggestions, setSuggestions] = useState<{ name: string; email: string }[]>([]);
    const [open, setOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState(-1);
    const fetchTokenRef = useRef(0);

    // The token being typed: text after the last comma.
    const lastToken = (value.split(",").pop() || "").trim();

    useEffect(() => {
        // Debounced suggestion lookup. Empty/one-char tokens don't hit the
        // API — typing a comma (finishing a recipient) shouldn't refetch.
        if (!open || lastToken.length < 2) {
            setSuggestions([]);
            return;
        }
        const token = ++fetchTokenRef.current;
        const timer = setTimeout(async () => {
            try {
                const { apiClient } = await import("@/lib/api");
                const res = await apiClient.get(
                    `/api/canvas/email/contacts?q=${encodeURIComponent(lastToken)}`
                );
                const data = (res as any).data || res || {};
                // Stale response (user kept typing) — drop it.
                if (token !== fetchTokenRef.current) return;
                const already = new Set(
                    value.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean)
                );
                const fresh = ((data.contacts || []) as any[])
                    .filter((c) => c?.email && !already.has(String(c.email).toLowerCase()))
                    .slice(0, 8);
                setSuggestions(fresh);
                setActiveIndex(fresh.length > 0 ? 0 : -1);
            } catch {
                if (token === fetchTokenRef.current) setSuggestions([]);
            }
        }, 250);
        return () => clearTimeout(timer);
        // `value` intentionally not a dep: refetching on every keystroke of
        // the same token would duplicate in-flight lookups.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastToken, open]);

    const applySuggestion = (email: string) => {
        // Drop the in-progress token, append the picked address, and leave
        // a trailing ", " so the next recipient types cleanly.
        const parts = value.split(",").slice(0, -1).map((p) => p.trim()).filter(Boolean);
        onChange([...parts, email].join(", ") + ", ");
        setSuggestions([]);
        setOpen(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!suggestions.length) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((i) => (i + 1) % suggestions.length);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((i) => (i - 1 + suggestions.length) % suggestions.length);
        } else if (e.key === "Enter" && activeIndex >= 0) {
            e.preventDefault();
            applySuggestion(suggestions[activeIndex].email);
        } else if (e.key === "Escape") {
            setOpen(false);
            setSuggestions([]);
        }
    };

    return (
        <div className="flex items-center gap-2 relative flex-1">
            <span className="text-[10px] text-zinc-400 w-12 font-bold uppercase tracking-wider shrink-0">{label}</span>
            <div className="flex-1 relative">
                <input
                    type="text"
                    data-testid={testId}
                    value={value}
                    placeholder={placeholder}
                    onChange={(e) => {
                        onChange(e.target.value);
                        setOpen(true);
                    }}
                    onFocus={() => setOpen(true)}
                    onBlur={() => {
                        // Clicking a suggestion mousedown-prevents default so
                        // the blur doesn't swallow the click; plain blurs close.
                        setTimeout(() => setOpen(false), 150);
                    }}
                    onKeyDown={handleKeyDown}
                    className={inputClassName || "w-full bg-transparent border-none text-zinc-900 dark:text-zinc-200 text-sm focus:ring-0 outline-none placeholder:text-zinc-300"}
                    role="combobox"
                    aria-expanded={open && suggestions.length > 0}
                    aria-autocomplete="list"
                    aria-controls={testId ? `${testId}-listbox` : undefined}
                />
                {open && suggestions.length > 0 && (
                    <ul
                        role="listbox"
                        id={testId ? `${testId}-listbox` : undefined}
                        data-testid={testId ? `${testId}-suggestions` : undefined}
                        className="absolute z-20 left-0 right-0 top-full mt-1 bg-white dark:bg-[#1e293b] border border-zinc-200 dark:border-white/10 rounded-lg shadow-lg overflow-hidden"
                    >
                        {suggestions.map((s, i) => (
                            <li
                                key={`${s.email}-${i}`}
                                role="option"
                                aria-selected={i === activeIndex}
                                className={`px-3 py-1.5 text-xs cursor-pointer flex items-baseline gap-2 ${
                                    i === activeIndex
                                        ? "bg-indigo-50 dark:bg-indigo-500/20"
                                        : "hover:bg-zinc-50 dark:hover:bg-white/5"
                                }`}
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => applySuggestion(s.email)}
                            >
                                {s.name && (
                                    <span className="text-zinc-700 dark:text-zinc-200 truncate max-w-[50%]">{s.name}</span>
                                )}
                                <span className="text-zinc-500 dark:text-zinc-400 truncate">{s.email}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
