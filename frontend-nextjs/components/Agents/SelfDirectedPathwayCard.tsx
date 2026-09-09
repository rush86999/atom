"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  SelfDirectedAgentProgress,
  SelfDirectedEpisode,
} from "@/lib/maturity-api";

const OUTCOME_BADGE: Record<string, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failure: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  partial: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
};

function formatEpisodeDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function EpisodeRow({ ep }: { ep: SelfDirectedEpisode }) {
  return (
    <div className="flex items-start gap-1.5 text-[11px]" data-testid="self-directed-episode-row">
      <span
        className={`shrink-0 rounded px-1 py-px text-[9px] font-medium uppercase ${
          OUTCOME_BADGE[ep.outcome] ||
          "bg-muted text-muted-foreground"
        }`}
      >
        {ep.outcome}
      </span>
      <span className="min-w-0 flex-1 truncate text-muted-foreground" title={ep.task}>
        {ep.task}
      </span>
      <span className="shrink-0 text-[9px] text-muted-foreground">
        {formatEpisodeDate(ep.started_at)}
      </span>
    </div>
  );
}

/**
 * Validation card for the self-directed STUDENT → INTERN pathway.
 *
 * Shows the human what they are actually validating: outcome-tracked
 * episode evidence vs the graduation floors (episodes, success ratio,
 * confidence, sessions), the multi-pathway readiness verdict, a step list
 * explaining what is (or isn't) done, and the recent work itself. The
 * promote action stays a supervisor judgment call — this card supplies the
 * evidence, never the decision.
 *
 * Rendered in the canvas Training tab's Graduation section and on
 * /approvals (compact queue cards). Data comes from
 * GET /api/maturity/training/self-directed.
 */
export function SelfDirectedPathwayCard({
  progress,
  compact = false,
  nextTierLabel,
  onPromote,
  promoteBusy = false,
}: {
  progress: SelfDirectedAgentProgress;
  /** Queue mode (approvals): tighter layout, fewer rows. */
  compact?: boolean;
  nextTierLabel?: string;
  onPromote?: () => void;
  promoteBusy?: boolean;
}) {
  const { evidence } = progress;
  const pct = Math.round(progress.episode_progress * 100);
  const ratioPct = Math.round(evidence.success_ratio * 100);
  const ready = progress.ready_for_review;
  const episodesShown = compact ? progress.recent_episodes.slice(0, 3) : progress.recent_episodes.slice(0, 5);

  return (
    <div className="space-y-2" data-testid="self-directed-pathway-card">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[11px] font-medium">{progress.agent_name}</span>
        <Badge variant="outline" className="h-4 px-1 text-[9px] uppercase">
          {progress.tier}
        </Badge>
        <span className="text-[10px] text-muted-foreground">
          {Math.round(progress.confidence * 100)}% confidence
        </span>
        {ready && (
          <span
            className="text-[10px] font-medium text-green-700 dark:text-green-400"
            data-testid="self-directed-ready"
          >
            · ready for review
          </span>
        )}
      </div>

      {/* Verified-episode progress toward the evidence floor */}
      <div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span data-testid="self-directed-progress-label">
            Verified episodes {evidence.episodes}/{evidence.required_episodes}
          </span>
          <span>{ratioPct}% success</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all ${
              ratioPct >= 70 ? "bg-green-500" : "bg-amber-500"
            }`}
            style={{ width: `${Math.min(100, pct)}%` }}
            data-testid="self-directed-progress-bar"
          />
        </div>
      </div>

      {/* What the pathway needs — each step states its evidence rule */}
      <ul className="space-y-1" data-testid="self-directed-guidance">
        {progress.guidance.map((g) => (
          <li key={g.label} className="flex items-start gap-1.5 text-[11px]">
            <span
              className={`mt-px shrink-0 ${
                g.done ? "text-green-600 dark:text-green-400" : "text-muted-foreground"
              }`}
            >
              {g.done ? "✓" : "○"}
            </span>
            <span
              className={g.done ? "text-foreground" : "text-muted-foreground"}
              title={g.detail}
            >
              {g.label}
            </span>
          </li>
        ))}
      </ul>

      {/* The work being validated */}
      {episodesShown.length > 0 && (
        <div className="space-y-1" data-testid="self-directed-episodes">
          <p className="text-[10px] font-medium text-muted-foreground">
            Recent verified work
          </p>
          {episodesShown.map((ep) => (
            <EpisodeRow key={ep.id} ep={ep} />
          ))}
        </div>
      )}

      {!ready && progress.readiness.reason && !compact && (
        <p className="text-[10px] text-muted-foreground">{progress.readiness.reason}</p>
      )}

      {ready && onPromote && (
        <Button
          size="sm"
          className="h-7 text-xs w-full"
          onClick={onPromote}
          disabled={promoteBusy}
          data-testid="self-directed-promote-button"
        >
          {promoteBusy
            ? "Promoting…"
            : `Promote to ${(nextTierLabel || "INTERN").toUpperCase()}`}
        </Button>
      )}
    </div>
  );
}
