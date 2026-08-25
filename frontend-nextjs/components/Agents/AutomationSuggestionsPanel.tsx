import React, { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCw, Lightbulb, TrendingUp } from 'lucide-react';
import {
  AutomationSuggestion,
  AutomationSuggestionsResult,
  getAutomationSuggestions,
} from '@/lib/agent-onboarding-api';

/**
 * History-mined workflow automation suggestions: what this workspace keeps
 * doing manually, and what to automate next. Rendered on the Agents page so
 * employees see opportunities without going looking for them.
 */
export function AutomationSuggestionsPanel({ onCreateAgent }: { onCreateAgent?: (goal: string) => void }) {
  const [data, setData] = useState<AutomationSuggestionsResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = () => {
    setIsLoading(true);
    getAutomationSuggestions(5)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6 text-gray-500" data-testid="suggestions-loading">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing your workspace history...
      </div>
    );
  }

  if (!data || data.suggestions.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-4" data-testid="suggestions-empty">
        No automation opportunities detected yet — they appear as agents run and approvals accumulate.
      </div>
    );
  }

  return (
    <div data-testid="automation-suggestions-panel">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-1.5">
          <Lightbulb className="h-4 w-4 text-amber-500" />
          Automate next
        </h3>
        <Button variant="ghost" size="sm" onClick={load} data-testid="suggestions-refresh" aria-label="Refresh suggestions">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-3">
        {data.suggestions.map((s: AutomationSuggestion) => (
          <div
            key={s.title}
            className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-800"
            data-testid={`suggestion-card-${s.title.slice(0, 12)}`}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{s.title}</p>
              {s.estimated_time_saved_minutes_per_month ? (
                <Badge variant="outline" className="shrink-0 text-green-700 border-green-300 bg-green-50 dark:bg-green-900/20">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  ~{s.estimated_time_saved_minutes_per_month} min/mo
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">{s.description}</p>
            {s.evidence && (
              <p className="mt-1.5 text-[11px] text-gray-400 italic">Evidence: {s.evidence}</p>
            )}
            {onCreateAgent && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                data-testid={`suggestion-create-agent-${s.title.slice(0, 12)}`}
                onClick={() => onCreateAgent(s.description || s.title)}
              >
                Build an agent for this
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
