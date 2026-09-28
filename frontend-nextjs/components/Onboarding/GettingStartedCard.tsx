import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/router';
import { CheckCircle, Circle, Key, Bot, Play, X, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const DISMISS_KEY = 'atom.getting_started.dismissed.v1';

interface Progress {
    provider_configured: boolean;
    has_agent: boolean;
    first_job_done: boolean;
}

const subscribeToDismissal = (callback: () => void) => {
    window.addEventListener('storage', callback);
    return () => window.removeEventListener('storage', callback);
};

const getDismissedSnapshot = () => {
    try {
        return window.localStorage.getItem(DISMISS_KEY) === '1';
    } catch {
        return false;
    }
};

const getServerDismissedSnapshot = () => true;

const fetchProgress = async (): Promise<Progress | null | undefined> => {
    const token = typeof window !== 'undefined'
        ? (localStorage.getItem('token') || localStorage.getItem('auth_token'))
        : null;
    if (!token) return undefined;
    try {
        const res = await fetch(`${API_BASE}/api/onboarding/progress`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return undefined;
        const data = await res.json();
        return data?.data ?? data ?? null;
    } catch {
        return undefined;
    }
};

/**
 * "Getting started" checklist for the dashboard — the persistent, visible
 * guide from first login to the user's first AI agent job:
 *   1. Connect an AI provider (Settings → AI, or free local Ollama)
 *   2. Set up a first agent (Agents page / template marketplace)
 *   3. Run a first AI job (chat with an agent)
 * State comes from GET /api/onboarding/progress; the card auto-hides once
 * every step is done. Dismissal is remembered and reversible.
 */
export function GettingStartedCard() {
    const router = useRouter();
    const [progress, setProgress] = useState<Progress | null>(null);
    const storedDismissed = useSyncExternalStore(
        subscribeToDismissal,
        getDismissedSnapshot,
        getServerDismissedSnapshot
    );
    const [dismissedOverride, setDismissedOverride] = useState<boolean | null>(null);
    const dismissed = dismissedOverride ?? storedDismissed;

    useEffect(() => {
        let cancelled = false;
        const onFocus = () => {
            void fetchProgress().then((nextProgress) => {
                if (!cancelled && nextProgress !== undefined) setProgress(nextProgress);
            });
        };
        onFocus();
        window.addEventListener('focus', onFocus);
        return () => {
            cancelled = true;
            window.removeEventListener('focus', onFocus);
        };
    }, []);

    const allDone = !!progress
        && progress.provider_configured
        && progress.has_agent
        && progress.first_job_done;

    if (dismissed || allDone) {
        if (allDone) return null;
        return (
            <button
                onClick={() => {
                    setDismissedOverride(false);
                    try { localStorage.removeItem(DISMISS_KEY); } catch { /* ignore */ }
                }}
                data-testid="getting-started-restore"
                className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 mb-4"
            >
                <Lightbulb className="w-4 h-4" /> Getting started guide
            </button>
        );
    }

    const steps = [
        {
            icon: Key,
            title: 'Connect an AI provider',
            done: progress?.provider_configured,
            description: 'Add an API key (OpenAI, Anthropic, …) or use free local Ollama.',
            cta: 'Configure AI',
            href: '/settings/ai',
        },
        {
            icon: Bot,
            title: 'Set up your first agent',
            done: progress?.has_agent,
            description: 'Browse ready-made agent templates in the marketplace, or describe a workflow in plain language.',
            cta: 'Browse agents',
            href: '/agents',
        },
        {
            icon: Play,
            title: 'Run your first AI job',
            done: progress?.first_job_done,
            description: 'Chat with an agent — try one of the example prompts to see Atom work.',
            cta: 'Start chatting',
            href: '/chat',
        },
    ];

    const doneCount = steps.filter(s => s.done).length;

    return (
        <div
            data-testid="getting-started-card"
            className="mb-6 bg-white dark:bg-gray-800 border border-purple-100 dark:border-purple-900 rounded-lg shadow-sm"
        >
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-purple-600" />
                    <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                        Get to your first AI agent job
                    </h2>
                    <span className="text-xs text-gray-400">
                        {doneCount}/3 complete
                    </span>
                </div>
                <button
                    onClick={() => {
                        setDismissedOverride(true);
                        try { localStorage.setItem(DISMISS_KEY, '1'); } catch { /* ignore */ }
                    }}
                    aria-label="Dismiss getting started guide"
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {steps.map((step, i) => (
                    <div key={i} className="flex items-center gap-4 px-4 py-3">
                        {step.done
                            ? <CheckCircle className="w-5 h-5 text-green-500 shrink-0" aria-label="Step complete" />
                            : <Circle className="w-5 h-5 text-gray-300 dark:text-gray-600 shrink-0" />}
                        <div className="flex-1 min-w-0">
                            <p className={`text-sm font-medium ${step.done
                                ? 'text-gray-400 dark:text-gray-500 line-through'
                                : 'text-gray-800 dark:text-gray-100'}`}>
                                {i + 1}. {step.title}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                                {step.description}
                            </p>
                        </div>
                        {!step.done && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => router.push(step.href)}
                                data-testid={`getting-started-step-${i + 1}-cta`}
                            >
                                {step.cta}
                            </Button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default GettingStartedCard;
