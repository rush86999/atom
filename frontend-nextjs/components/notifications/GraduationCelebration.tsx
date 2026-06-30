/**
 * P2.3 — Graduation celebration toast.
 *
 * On mount, polls /api/notifications?unread_only=true&type=agent_graduated.
 * If any agent_graduated notifications are unread, renders a celebratory
 * toast banner. Clicking dismiss or the CTA marks the notification read so
 * it doesn't re-appear on the next page load.
 *
 * Kept lightweight (no confetti library) — uses CSS animations + emoji to
 * achieve the celebration effect without adding a JS dependency.
 */
'use client';

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FaTimes, FaGraduationCap } from "react-icons/fa";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CelebrationItem {
    id: string;
    title: string;
    message: string;
    action_url?: string | null;
    action_label?: string | null;
    metadata?: Record<string, unknown>;
}

export const GraduationCelebration: React.FC = () => {
    const [items, setItems] = useState<CelebrationItem[]>([]);

    const poll = useCallback(async () => {
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const res = await fetch(
                `${API_BASE}/api/notifications?unread_only=true&type=agent_graduated&limit=5`,
                { headers: token ? { Authorization: `Bearer ${token}` } : {} },
            );
            if (!res.ok) return;
            const json = await res.json();
            const data = json?.data ?? json;
            const notifs = Array.isArray(data?.notifications) ? data.notifications : [];
            // Only surface agent_graduated that the user hasn't seen yet.
            setItems(notifs.filter((n: any) => !n.read));
        } catch {
            // Silent — celebration is non-critical.
        }
    }, []);

    useEffect(() => {
        poll();
        // Re-check every 60s so a graduation triggered in another tab surfaces
        // without a manual reload. Cheap endpoint (capped at 5 rows).
        const id = window.setInterval(poll, 60_000);
        return () => window.clearInterval(id);
    }, [poll]);

    const dismiss = useCallback(async (id: string) => {
        setItems(prev => prev.filter(n => n.id !== id));
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            await fetch(`${API_BASE}/api/notifications/${id}/read`, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
        } catch {
            // Best-effort.
        }
    }, []);

    if (items.length === 0) return null;

    // Show only the most recent celebration at a time to avoid stacking.
    const current = items[0];

    return (
        <div
            role="status"
            aria-live="polite"
            className="fixed bottom-4 right-4 z-50 w-80 rounded-lg border border-purple-200 dark:border-purple-900 bg-white dark:bg-gray-900 shadow-xl overflow-hidden animate-[slidein_0.25s_ease-out]"
        >
            <div className="bg-gradient-to-r from-purple-500 to-pink-500 px-4 py-3 text-white">
                <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                        <FaGraduationCap className="w-5 h-5 shrink-0" />
                        <p className="font-semibold text-sm truncate">{current.title}</p>
                    </div>
                    <button
                        type="button"
                        aria-label="Dismiss"
                        onClick={() => dismiss(current.id)}
                        className="shrink-0 text-white/80 hover:text-white"
                    >
                        <FaTimes className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>
            <div className="px-4 py-3">
                <p className="text-sm text-gray-700 dark:text-gray-300">{current.message}</p>
                <p className="text-2xl mt-1" aria-hidden>🎉</p>
                <div className="mt-3 flex justify-end gap-2">
                    {current.action_url && (
                        <Link
                            href={current.action_url}
                            onClick={() => dismiss(current.id)}
                            className="inline-flex items-center rounded-md bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 text-xs font-medium"
                        >
                            {current.action_label || "View"}
                        </Link>
                    )}
                </div>
            </div>

            {/* Local <style> tag for the slide-in animation; kept inline so the
                component is fully self-contained without touching globals.css. */}
            <style jsx>{`
                @keyframes slidein {
                    from { transform: translateY(16px); opacity: 0; }
                    to   { transform: translateY(0);    opacity: 1; }
                }
            `}</style>
        </div>
    );
};

export default GraduationCelebration;
