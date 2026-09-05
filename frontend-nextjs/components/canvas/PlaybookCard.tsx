"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Playbook } from "@/lib/playbook-api";

const SOURCE_BADGE: Record<string, string> = {
  authored: "bg-slate-100 text-slate-800 dark:bg-slate-900/40 dark:text-slate-300",
  taught: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  learned: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
};

/** The taxonomy token correction reflection embedded in "[taxonomy] token"
    draft names — rendered as its own chip so the rule text can stay clean. */
function splitTaxonomy(name: string): { taxonomy: string | null; rest: string } {
  const m = name.match(/^\[([a-z]+)\]\s*(.+)$/i);
  return m ? { taxonomy: m[1], rest: m[2] } : { taxonomy: null, rest: name };
}

/**
 * One playbook in the Training tab's review queue (Playbook Journey).
 * Presentational: the parent owns list state and the API calls; the card
 * owns only its inline-edit draft. Draft cards show approve/retire/edit
 * (supervisor only); active cards show retire.
 */
export function PlaybookCard({
  playbook,
  isSupervisor,
  busy,
  onApprove,
  onRetire,
  onSaveEdit,
}: {
  playbook: Playbook;
  isSupervisor: boolean;
  busy?: boolean;
  onApprove?: (pb: Playbook) => void;
  onRetire?: (pb: Playbook) => void;
  onSaveEdit?: (pb: Playbook, patch: { steps: string[]; trigger_keywords: string[] }) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [stepsDraft, setStepsDraft] = useState(playbook.steps.join("\n"));
  const [keywordsDraft, setKeywordsDraft] = useState(playbook.trigger_keywords.join(", "));

  const isDraft = playbook.approval_state === "draft";
  const { taxonomy, rest } = splitTaxonomy(playbook.name);
  // Recurring corrections bump the version instead of stacking rows — on a
  // learned draft the version count IS the "seen n×" evidence.
  const seenCount = playbook.source === "learned" ? playbook.version : null;

  const saveEdit = () => {
    const steps = stepsDraft.split("\n").map((s) => s.trim()).filter(Boolean);
    const keywords = keywordsDraft.split(",").map((k) => k.trim().toLowerCase()).filter(Boolean);
    onSaveEdit?.(playbook, { steps, trigger_keywords: keywords });
    setEditing(false);
  };

  return (
    <div className="border rounded-lg p-2.5 space-y-1.5" data-testid="playbook-card">
      <div className="flex items-center gap-1.5 flex-wrap">
        {taxonomy && (
          <span className="text-[10px] px-1 rounded bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300">
            {taxonomy}
          </span>
        )}
        <span
          className={`text-[10px] px-1 rounded ${SOURCE_BADGE[playbook.source] ?? SOURCE_BADGE.authored}`}
        >
          {playbook.source}
        </span>
        <span className="text-[10px] text-muted-foreground">v{playbook.version}</span>
        {seenCount !== null && seenCount > 1 && (
          <span className="text-[10px] text-amber-700 dark:text-amber-400" data-testid="playbook-seen">
            seen {seenCount}×
          </span>
        )}
        {/* Autonomy latch (Journey §6): while the sleep-time job accrues
            clean replays toward no-human-click promotion — or why it's
            paused (crew still maturing / human-always surface). */}
        {isDraft && playbook.source === "learned" && playbook.auto_latch?.blocked && (
          <span
            className="text-[10px] text-muted-foreground underline decoration-dotted cursor-help"
            title={playbook.auto_latch.blocked}
            data-testid="playbook-latch-paused"
          >
            auto-approve paused
          </span>
        )}
        {isDraft && playbook.source === "learned" && !playbook.auto_latch?.blocked &&
          (playbook.auto_latch?.passes ?? 0) > 0 && (
          <span
            className="text-[10px] text-emerald-700 dark:text-emerald-400"
            data-testid="playbook-latch"
          >
            auto-latch {playbook.auto_latch!.passes}/{playbook.auto_latch!.threshold ?? 3}
          </span>
        )}
        <span className="text-[10px] text-muted-foreground ml-auto">
          {playbook.approval_state === "draft" && "needs review"}
          {playbook.approval_state === "retired" && "retired"}
        </span>
      </div>

      <p className="text-xs font-medium break-words" data-testid="playbook-name">
        {taxonomy ? rest : playbook.name}
      </p>

      {!editing && playbook.steps.length > 0 && (
        <ul className="text-[11px] text-muted-foreground list-disc pl-4 space-y-0.5" data-testid="playbook-steps">
          {playbook.steps.slice(0, 4).map((s, i) => (
            <li key={i} className="break-words">{s}</li>
          ))}
          {playbook.steps.length > 4 && <li>… {playbook.steps.length - 4} more</li>}
        </ul>
      )}

      {editing && (
        <div className="space-y-1.5">
          <textarea
            value={stepsDraft}
            onChange={(e) => setStepsDraft(e.target.value)}
            rows={4}
            className="w-full border rounded-md px-2 py-1 text-xs bg-background"
            aria-label="Playbook steps"
            data-testid="playbook-edit-steps"
            placeholder="One step per line"
          />
          <Input
            value={keywordsDraft}
            onChange={(e) => setKeywordsDraft(e.target.value)}
            className="h-7 text-xs"
            aria-label="Trigger keywords"
            data-testid="playbook-edit-keywords"
            placeholder="Trigger keywords (comma-separated)"
          />
        </div>
      )}

      {(playbook.trigger_canvas_type || playbook.trigger_keywords.length > 0) && !editing && (
        <div className="flex flex-wrap gap-1">
          {playbook.trigger_canvas_type && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
              {playbook.trigger_canvas_type}
            </span>
          )}
          {playbook.trigger_keywords.slice(0, 4).map((kw) => (
            <span key={kw} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
              {kw}
            </span>
          ))}
        </div>
      )}

      {isSupervisor && (
        <div className="flex gap-1.5 flex-wrap">
          {isDraft && !editing && (
            <Button
              size="sm"
              className="h-7 text-xs bg-green-600 hover:bg-green-500"
              onClick={() => onApprove?.(playbook)}
              disabled={busy}
              data-testid="playbook-approve"
            >
              {busy ? "…" : "Approve"}
            </Button>
          )}
          {isDraft && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => (editing ? saveEdit() : setEditing(true))}
              disabled={busy}
              data-testid="playbook-edit"
            >
              {editing ? "Save" : "Edit"}
            </Button>
          )}
          {playbook.approval_state !== "retired" && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => onRetire?.(playbook)}
              disabled={busy}
              data-testid="playbook-retire"
            >
              Retire
            </Button>
          )}
        </div>
      )}

      {playbook.description && (
        <p className="text-[10px] text-muted-foreground break-words">{playbook.description}</p>
      )}
    </div>
  );
}

export default PlaybookCard;
