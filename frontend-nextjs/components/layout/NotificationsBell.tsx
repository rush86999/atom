/**
 * P2.2 — In-app notification center bell.
 *
 * Self-contained dropdown that polls /api/notifications on mount and on click.
 * Shows unread-count badge. "Mark all read" calls POST /api/notifications/read-all.
 * Clicking an individual notification marks it read and navigates to action_url.
 *
 * Kept dependency-free (no SWR/react-query) on purpose — the rest of the app
 * uses plain fetch + localStorage tokens, so we match that pattern.
 */
'use client';

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FaBell, FaCheckCircle } from "react-icons/fa";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface NotificationItem {
    id: string;
    type: string;
    title: string;
    message: string;
    read: boolean;
    action_url?: string | null;
    action_label?: string | null;
    created_at?: string | null;
    metadata?: Record<string, unknown>;
}

export const NotificationsBell: React.FC = () => {
    const [open, setOpen] = useState(false);
    const [items, setItems] = useState<NotificationItem[]>([]);
    const [unread, setUnread] = useState(0);
    const [loading, setLoading] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const fetchUnread = useCallback(async () => {
        try {
            const token = typeof window !== "undefined" ? (localStorage.getItem("token") || localStorage.getItem("auth_token")) : null;
            const res = await fetch(`${API_BASE}/api/notifications?limit=10`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!res.ok) return;
            const json = await res.json();
            const data = json?.data ?? json;
            setItems(Array.isArray(data?.notifications) ? data.notifications : []);
            setUnread(Number(data?.unread_count ?? 0));
        } catch {
            // Silent — the bell is non-critical UI.
        }
    }, []);

    // Initial poll on mount, and when the dropdown is first opened.
    useEffect(() => {
        fetchUnread();
    }, [fetchUnread]);

    // Close on outside click.
    useEffect(() => {
        if (!open) return;
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, [open]);

    const markRead = useCallback(async (id: string) => {
        try {
            const token = typeof window !== "undefined" ? (localStorage.getItem("token") || localStorage.getItem("auth_token")) : null;
            await fetch(`${API_BASE}/api/notifications/${id}/read`, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
        } catch {
            // Best-effort.
        }
    }, []);

    const markAllRead = useCallback(async () => {
        setLoading(true);
        try {
            const token = typeof window !== "undefined" ? (localStorage.getItem("token") || localStorage.getItem("auth_token")) : null;
            await fetch(`${API_BASE}/api/notifications/read-all`, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            await fetchUnread();
        } finally {
            setLoading(false);
        }
    }, [fetchUnread]);

    const handleClickItem = useCallback(async (item: NotificationItem) => {
        if (!item.read) {
            // Optimistic update.
            setItems(prev => prev.map(n => n.id === item.id ? { ...n, read: true } : n));
            setUnread(prev => Math.max(0, prev - 1));
            await markRead(item.id);
        }
        if (item.action_url) {
            // Let Link handle the navigation.
            setOpen(false);
        }
    }, [markRead]);

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                type="button"
                aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
                onClick={() => {
                    const next = !open;
                    setOpen(next);
                    if (next) fetchUnread();
                }}
                className="relative p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
            >
                <FaBell className="w-4 h-4" />
                {unread > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                        {unread > 9 ? "9+" : unread}
                    </span>
                )}
            </button>

            {open && (
                <div className="absolute right-0 mt-2 w-80 max-h-[480px] overflow-y-auto rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-lg z-50">
                    <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 dark:border-gray-800">
                        <span className="text-sm font-semibold">Notifications</span>
                        {unread > 0 && (
                            <button
                                type="button"
                                disabled={loading}
                                onClick={markAllRead}
                                className="text-xs text-purple-600 hover:underline disabled:opacity-50"
                            >
                                {loading ? "Marking…" : "Mark all read"}
                            </button>
                        )}
                    </div>

                    {items.length === 0 ? (
                        <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                            You&apos;re all caught up.
                        </div>
                    ) : (
                        <ul className="divide-y divide-gray-100 dark:divide-gray-800">
                            {items.map((item) => {
                                const content = (
                                    <div className={cn(
                                        "px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50",
                                        !item.read && "bg-purple-50/40 dark:bg-purple-950/20"
                                    )}>
                                        <div className="flex items-start gap-2">
                                            {!item.read && (
                                                <span className="mt-1.5 w-2 h-2 rounded-full bg-purple-500 shrink-0" />
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{item.title}</p>
                                                <p className="text-xs text-muted-foreground line-clamp-2">{item.message}</p>
                                                {item.action_url && item.action_label && (
                                                    <span className="text-[11px] text-purple-600">{item.action_label}</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                );
                                return (
                                    <li key={item.id}>
                                        {item.action_url ? (
                                            <Link href={item.action_url} onClick={() => handleClickItem(item)}>
                                                {content}
                                            </Link>
                                        ) : (
                                            <div onClick={() => handleClickItem(item)}>{content}</div>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
};

export default NotificationsBell;
