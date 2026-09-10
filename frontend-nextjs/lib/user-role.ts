/**
 * User role hierarchy — the frontend half of the 2026-09-08 role-journey pass.
 *
 * Mirrors core/security/rbac.py on the backend (levels guest=1 ..
 * super_admin=8). The backend is the enforcement point; this module only
 * drives UI visibility (nav filtering, action gating) so roles stop seeing
 * surfaces that would 403 on them.
 *
 * The role is fetched fresh from GET /api/auth/me on every mount — it is
 * NOT taken from the NextAuth session (the API-first login flow, which is
 * what the app actually uses, leaves that session without a role).
 */

export const ROLE_LEVELS: Record<string, number> = {
    guest: 1,
    viewer: 2,
    member: 3,
    team_lead: 4,
    workspace_admin: 5,
    admin: 6,
    owner: 7,
    super_admin: 8,
};

/** team_lead and above may decide HITL/training/supervision actions. */
export const SUPERVISOR_MIN_LEVEL = ROLE_LEVELS.team_lead;
/** member and above do the everyday work — including starting role-based runs. */
export const MEMBER_MIN_LEVEL = ROLE_LEVELS.member;
/** workspace_admin and above manage users/settings/workspaces. */
export const ADMIN_MIN_LEVEL = ROLE_LEVELS.workspace_admin;

export function roleLevel(role?: string | null): number {
    if (!role) return 0;
    return ROLE_LEVELS[String(role).trim().toLowerCase()] ?? 0;
}

export function meetsRole(role: string | null | undefined, minLevel: number): boolean {
    return roleLevel(role) >= minLevel;
}

const ROLE_CACHE_KEY = "atom_user_role";

export interface CurrentUser {
    role: string | null;
    id: string | null;
}

/**
 * The signed-in identity from /api/auth/me. `id` is needed by surfaces that
 * gate on ownership (a GoalRun is worked by its owner OR a supervisor), not
 * just on role.
 */
export async function fetchCurrentUser(): Promise<CurrentUser> {
    if (typeof window === "undefined") return { role: null, id: null };
    const API = process.env.NEXT_PUBLIC_API_URL || "";
    const token =
        window.localStorage.getItem("auth_token") ||
        window.localStorage.getItem("token") ||
        "";
    if (!token) return { role: null, id: null };
    try {
        const res = await fetch(`${API}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return { role: null, id: null };
        const data = await res.json();
        const role = typeof data?.role === "string" ? data.role : null;
        const id = data?.id != null ? String(data.id)
            : data?.user_id != null ? String(data.user_id) : null;
        if (role) window.localStorage.setItem(ROLE_CACHE_KEY, role);
        return { role, id };
    } catch {
        return { role: null, id: null };
    }
}

export async function fetchCurrentRole(): Promise<string | null> {
    return (await fetchCurrentUser()).role;
}

export function cachedRole(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ROLE_CACHE_KEY);
}

export function clearCachedRole(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ROLE_CACHE_KEY);
}

export type UseUserRole = {
    /** raw role string once known; null while loading/unauthenticated */
    role: string | null;
    /** signed-in user id once known; null while loading/unauthenticated */
    userId: string | null;
    /** numeric level (0 = unknown) */
    level: number;
    isSupervisor: boolean;
    isAdmin: boolean;
    loading: boolean;
};

import { useEffect, useState } from "react";

/**
 * Role for UI gating. Paints from the localStorage cache immediately (so a
 * reload doesn't flash admin nav), then refreshes from /api/auth/me so a
 * promotion/demotion by an admin takes effect without a re-login.
 *
 * `level === 0` (still unknown / fetch failed) means "don't gate yet" —
 * the backend enforces every gate; hiding nav for a transient failure
 * would strand the operator.
 */
export function useUserRole(): UseUserRole {
    const [role, setRole] = useState<string | null>(null);
    const [userId, setUserId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        const cached = cachedRole();
        if (cached) setRole(cached);
        fetchCurrentUser().then((fresh) => {
            if (cancelled) return;
            if (fresh.role) setRole(fresh.role);
            if (fresh.id) setUserId(fresh.id);
            setLoading(false);
        });
        return () => {
            cancelled = true;
        };
    }, []);

    const level = roleLevel(role);
    return {
        role,
        userId,
        level,
        isSupervisor: meetsRole(role, SUPERVISOR_MIN_LEVEL),
        isAdmin: meetsRole(role, ADMIN_MIN_LEVEL),
        loading,
    };
}
