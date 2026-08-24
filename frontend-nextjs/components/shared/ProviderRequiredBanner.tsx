import React from 'react';
import Link from 'next/link';

/**
 * Amber "you need an AI provider first" banner (same look/CTA as the chat
 * recovery banner). Render it above actions that require an LLM so users
 * learn before failing a run, not after.
 */
export const ProviderRequiredBanner: React.FC = () => (
    <div
        data-testid="provider-required-banner"
        className="rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 p-3 text-sm"
    >
        <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
                <p className="font-medium text-amber-900 dark:text-amber-200">
                    You need an AI provider for this.
                </p>
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                    Add an API key or enable local Ollama to get started.
                </p>
            </div>
            <Link
                href="/settings/ai"
                className="shrink-0 inline-flex items-center rounded-md bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 text-xs font-medium"
            >
                Configure now →
            </Link>
        </div>
    </div>
);

export default ProviderRequiredBanner;
