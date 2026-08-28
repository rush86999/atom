
import React, { useCallback, useEffect, useState } from "react";
import { OnboardingWizard } from "./OnboardingWizard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Session-scoped dismissal: closing the wizard without finishing it hides it
// for the rest of this browser session, but a fresh session (next sign-in)
// offers it again. Completing onboarding persists server-side.
const DISMISS_KEY = "atom.onboarding.dismissed";

/**
 * Mounts the OnboardingWizard globally (via Layout) for authenticated users
 * who haven't completed onboarding. Renders nothing on error — a broken
 * status fetch must never break the app shell.
 */
export const OnboardingWizardHost: React.FC = () => {
    const [show, setShow] = useState(false);
    const [user, setUser] = useState<any>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            if (typeof window === "undefined") return;
            if (sessionStorage.getItem(DISMISS_KEY)) return;

            const token = localStorage.getItem("token") || localStorage.getItem("auth_token");
            if (!token) return; // not signed in — nothing to onboard

            try {
                const [statusRes, userRes] = await Promise.all([
                    fetch(`${API_BASE}/api/onboarding/status`, {
                        headers: { Authorization: `Bearer ${token}` },
                    }),
                    fetch(`${API_BASE}/api/users/me`, {
                        headers: { Authorization: `Bearer ${token}` },
                    }).catch((): Response | null => null),
                ]);

                // 401/5xx/etc: stay silent — the wizard is an enhancement, not
                // a gate. Users on older backends (no onboarding columns) must
                // still get a fully working app.
                if (!statusRes.ok) return;
                const statusData = await statusRes.json();
                const completed = !!(
                    statusData?.data?.onboarding_completed ?? statusData?.onboarding_completed
                );
                if (completed || cancelled) return;

                if (userRes && userRes.ok) {
                    const userData = await userRes.json().catch((): unknown => null);
                    setUser(userData?.data ?? userData ?? null);
                }
                if (!cancelled) setShow(true);
            } catch {
                // network error etc. — silently skip
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const handleClose = useCallback(() => {
        sessionStorage.setItem(DISMISS_KEY, "1");
        setShow(false);
    }, []);

    const handleUpdate = useCallback((data: any) => {
        if (data?.onboarding_completed) {
            setShow(false);
        }
    }, []);

    if (!show) return null;

    return (
        <OnboardingWizard
            isOpen={show}
            onClose={handleClose}
            user={user}
            onUpdate={handleUpdate}
        />
    );
};

export default OnboardingWizardHost;
