"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  approvePlaybook,
  createPlaybook,
  listPlaybooks,
  retirePlaybook,
  updatePlaybook,
  type Playbook,
} from "@/lib/playbook-api";
import { PlaybookCard } from "./PlaybookCard";

type Segment = "draft" | "approved" | "retired";

const SEGMENTS: { key: Segment; label: string }[] = [
  { key: "draft", label: "Drafts" },
  { key: "approved", label: "Active" },
  { key: "retired", label: "Retired" },
];

const CANVAS_TYPES = ["email", "spreadsheet", "document", "presentation", "generic"];

// Learned drafts the viewer already saw — "new rules from your corrections"
// banner only counts ids not yet dismissed here (localStorage, best-effort).
const SEEN_KEY = "atom_playbook_seen_learned";

function readSeenLearned(): string[] {
  try {
    const raw = window.localStorage.getItem(SEEN_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function writeSeenLearned(ids: string[]) {
  try {
    window.localStorage.setItem(SEEN_KEY, JSON.stringify(ids.slice(-200)));
  } catch { /* private mode — banner just re-shows */ }
}

/**
 * The Playbooks review queue inside the canvas Training tab (Playbook
 * Journey, docs/architecture/PLAYBOOK_USER_JOURNEY.md): correction-drafted
 * and taught rules wait here for one-click supervisor approval; approved
 * playbooks advise matching tasks. Self-fetching like TrainingPanel; every
 * mutation goes through /api/playbooks.
 */
export function PlaybookSection({
  isSupervisor,
  onDraftsCountChange,
}: {
  isSupervisor: boolean;
  onDraftsCountChange?: (count: number) => void;
}) {
  const [playbooks, setPlaybooks] = useState<Playbook[] | null>(null);
  const [segment, setSegment] = useState<Segment>("draft");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [newLearnedCount, setNewLearnedCount] = useState(0);

  // P4 mini-wizard
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizard, setWizard] = useState({ name: "", canvasType: "", keywords: "", steps: "", questions: "" });
  const [wizardBusy, setWizardBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const rows = await listPlaybooks(true);
      setPlaybooks(rows);
      const drafts = rows.filter((p) => p.approval_state === "draft");
      onDraftsCountChange?.(drafts.length);

      const seen = readSeenLearned();
      const freshLearned = drafts.filter((p) => p.source === "learned" && !seen.includes(p.id));
      setNewLearnedCount(freshLearned.length);
      if (freshLearned.length > 0) {
        writeSeenLearned([...seen, ...freshLearned.map((p) => p.id)]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [onDraftsCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  const dismissNotice = () => setNewLearnedCount(0);

  const handleApprove = async (pb: Playbook) => {
    setBusyId(pb.id);
    setError(null);
    setNotice(null);
    try {
      await approvePlaybook(pb.id);
      setNotice(`"${pb.name}" is now active — matching tasks will follow it (advisory).`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleRetire = async (pb: Playbook) => {
    setBusyId(pb.id);
    setError(null);
    setNotice(null);
    try {
      await retirePlaybook(pb.id);
      setNotice(`"${pb.name}" retired — it no longer enters prompts.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleSaveEdit = async (
    pb: Playbook,
    patch: { steps: string[]; trigger_keywords: string[] },
  ) => {
    setBusyId(pb.id);
    setError(null);
    setNotice(null);
    try {
      await updatePlaybook(pb.id, patch);
      setNotice("Draft updated.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleCreate = async () => {
    if (!wizard.name.trim()) return;
    setWizardBusy(true);
    setError(null);
    setNotice(null);
    try {
      const state = await createPlaybook({
        name: wizard.name.trim(),
        trigger_canvas_type: wizard.canvasType || null,
        trigger_keywords: wizard.keywords.split(",").map((k) => k.trim().toLowerCase()).filter(Boolean),
        steps: wizard.steps.split("\n").map((s) => s.trim()).filter(Boolean),
        template_questions: wizard.questions.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      setNotice(
        state === "approved"
          ? `"${wizard.name.trim()}" created and active.`
          : `"${wizard.name.trim()}" created as a draft.`,
      );
      setWizard({ name: "", canvasType: "", keywords: "", steps: "", questions: "" });
      setWizardOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWizardBusy(false);
    }
  };

  const rows = playbooks ?? [];
  const bySegment = (s: Segment) => rows.filter((p) => p.approval_state === s);
  const counts: Record<Segment, number> = {
    draft: bySegment("draft").length,
    approved: bySegment("approved").length,
    retired: bySegment("retired").length,
  };

  return (
    <div className="border rounded-lg p-2.5 space-y-2" data-testid="playbook-section">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium">Playbooks</p>
        {isSupervisor && (
          <Button
            size="sm"
            variant="ghost"
            className="h-6 text-[11px]"
            onClick={() => setWizardOpen((v) => !v)}
            data-testid="playbook-wizard-toggle"
          >
            {wizardOpen ? "Cancel" : "+ New"}
          </Button>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground -mt-1.5">
        Corrections and lessons draft rules here — approve to guide matching tasks (advisory).
      </p>

      {error && (
        <p role="alert" className="text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1 break-words">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded px-2 py-1 break-words">
          {notice}
        </p>
      )}
      {newLearnedCount > 0 && (
        <p className="text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded px-2 py-1" data-testid="playbook-new-learned">
          📐 {newLearnedCount} new rule{newLearnedCount > 1 ? "s" : ""} drafted from your corrections — review below.
          <button className="ml-2 underline" onClick={dismissNotice} data-testid="playbook-notice-dismiss">dismiss</button>
        </p>
      )}

      {wizardOpen && (
        <div className="border rounded-md p-2 space-y-1.5" data-testid="playbook-wizard">
          <Input
            value={wizard.name}
            onChange={(e) => setWizard((w) => ({ ...w, name: e.target.value }))}
            placeholder="Process name"
            className="h-7 text-xs"
            aria-label="Process name"
            data-testid="playbook-wizard-name"
          />
          <div className="flex gap-1.5">
            <select
              value={wizard.canvasType}
              onChange={(e) => setWizard((w) => ({ ...w, canvasType: e.target.value }))}
              className="h-7 text-xs border rounded-md bg-background px-1"
              aria-label="Trigger canvas type"
              data-testid="playbook-wizard-canvas-type"
            >
              <option value="">Any canvas type</option>
              {CANVAS_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <Input
              value={wizard.keywords}
              onChange={(e) => setWizard((w) => ({ ...w, keywords: e.target.value }))}
              placeholder="Trigger keywords (comma-sep)"
              className="h-7 text-xs flex-1"
              aria-label="Trigger keywords"
              data-testid="playbook-wizard-keywords"
            />
          </div>
          <textarea
            value={wizard.steps}
            onChange={(e) => setWizard((w) => ({ ...w, steps: e.target.value }))}
            rows={3}
            className="w-full border rounded-md px-2 py-1 text-xs bg-background"
            aria-label="Steps"
            data-testid="playbook-wizard-steps"
            placeholder="Steps (one per line)"
          />
          <textarea
            value={wizard.questions}
            onChange={(e) => setWizard((w) => ({ ...w, questions: e.target.value }))}
            rows={2}
            className="w-full border rounded-md px-2 py-1 text-xs bg-background"
            aria-label="Template questions"
            data-testid="playbook-wizard-questions"
            placeholder="Questions to always ask (one per line, optional)"
          />
          <Button
            size="sm"
            className="h-7 text-xs"
            onClick={handleCreate}
            disabled={wizardBusy || !wizard.name.trim()}
            data-testid="playbook-wizard-submit"
          >
            {wizardBusy ? "Creating…" : "Create playbook"}
          </Button>
        </div>
      )}

      <div className="flex gap-1" role="tablist" aria-label="Playbook states">
        {SEGMENTS.map(({ key, label }) => (
          <button
            key={key}
            role="tab"
            aria-selected={segment === key}
            onClick={() => setSegment(key)}
            className={`text-[11px] px-2 py-1 rounded-md ${
              segment === key ? "bg-primary/10 text-foreground font-medium" : "text-muted-foreground hover:text-foreground"
            }`}
            data-testid={`playbook-segment-${key}`}
          >
            {label} ({counts[key]})
          </button>
        ))}
      </div>

      {!playbooks && <p className="text-xs text-muted-foreground">Loading playbooks…</p>}

      {playbooks && bySegment(segment).length === 0 && (
        <p className="text-[11px] text-muted-foreground py-1" data-testid="playbook-empty">
          {segment === "draft" && "Corrections you make on canvases draft rules here for one-click approval."}
          {segment === "approved" && "Approved processes appear here and guide matching tasks (advisory)."}
          {segment === "retired" && "Retired rules are kept for the record — a recurring correction re-drafts them."}
        </p>
      )}

      <div className="space-y-2">
        {bySegment(segment).map((pb) => (
          <PlaybookCard
            key={pb.id}
            playbook={pb}
            isSupervisor={isSupervisor}
            busy={busyId === pb.id}
            onApprove={handleApprove}
            onRetire={handleRetire}
            onSaveEdit={handleSaveEdit}
          />
        ))}
      </div>
    </div>
  );
}

export default PlaybookSection;
