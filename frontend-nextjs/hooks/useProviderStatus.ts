import { useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export type ProviderStatus = {
    /** null while loading or when the check is unavailable. */
    configured: boolean | null;
    refresh: () => void;
};

/**
 * Pre-flight check: does this workspace have any usable LLM provider
 * (BYOK key saved or env-configured)? Surfaces the answer BEFORE the user
 * burns a failed agent run / workflow generation, instead of after.
 */
export function useProviderStatus(): ProviderStatus {
    const [configured, setConfigured] = useState<boolean | null>(null);
    const [tick, setTick] = useState(0);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            const token = typeof window !== 'undefined'
                ? (localStorage.getItem('token') || localStorage.getItem('auth_token'))
                : null;
            if (!token) return;
            try {
                const res = await fetch(`${API_BASE}/api/onboarding/progress`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok || cancelled) return;
                const data = await res.json();
                const value = data?.data?.provider_configured ?? data?.provider_configured;
                if (!cancelled && typeof value === 'boolean') {
                    setConfigured(value);
                }
            } catch {
                // leave null — caller treats null as "unknown, don't nag"
            }
        })();
        return () => { cancelled = true; };
    }, [tick]);

    return {
        configured,
        refresh: () => setTick(t => t + 1),
    };
}
