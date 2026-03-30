'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  CheckCircle2,
  XCircle,
  Zap,
  ChevronDown,
  ChevronRight,
  GitMerge,
  Shield,
  AlertTriangle,
  Info,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'react-hot-toast';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface FieldMergeDecision {
  field: string;
  source_value: any;
  target_value: any;
  suggested_value: any;
  confidence: number;        // 0..1
  reason: string;
  chosen: 'source' | 'target' | 'suggested';
}

export interface MergeProposal {
  id: string;
  source_label: string;
  target_label: string;
  entity_type: string;
  overall_confidence: number;    // 0..1
  field_decisions: FieldMergeDecision[];
  conflict_count: number;
  ai_summary: string;
  created_at?: string;
}

export interface MergeDialogProps {
  open: boolean;
  proposal: MergeProposal | null;
  onApply: (proposal: MergeProposal, decisions: FieldMergeDecision[]) => Promise<void>;
  onClose: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gradient confidence bar
// ─────────────────────────────────────────────────────────────────────────────

function confidenceColor(score: number): string {
  if (score >= 0.75) return 'from-emerald-500 to-teal-400';
  if (score >= 0.45) return 'from-amber-500 to-orange-400';
  return 'from-rose-600 to-red-400';
}

function confidenceLabel(score: number): string {
  if (score >= 0.75) return 'High';
  if (score >= 0.45) return 'Medium';
  return 'Low';
}

function confidenceBadgeClass(score: number): string {
  if (score >= 0.75) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
  if (score >= 0.45) return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
}

interface ConfidenceBarProps {
  score: number;           // 0..1
  label?: string;
  animate?: boolean;
  className?: string;
}

function ConfidenceBar({ score, label, animate = true, className }: ConfidenceBarProps) {
  const [displayed, setDisplayed] = useState(animate ? 0 : score * 100);
  const pct = Math.round(score * 100);

  useEffect(() => {
    if (!animate) return;
    setDisplayed(0);
    const t = setTimeout(() => {
      setDisplayed(score * 100);
    }, 80);
    return () => clearTimeout(t);
  }, [score, animate]);

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {label && (
        <span className="text-[10px] font-semibold text-white/50 w-14 shrink-0">{label}</span>
      )}
      <div className="relative flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full bg-gradient-to-r',
            confidenceColor(score),
            'shadow-[0_0_6px_rgba(16,185,129,0.5)]',
            animate && 'transition-all duration-700 ease-out'
          )}
          style={{ width: `${displayed}%` }}
        />
      </div>
      <span
        className={cn(
          'text-[10px] font-bold px-1.5 py-0.5 rounded border shrink-0',
          confidenceBadgeClass(score)
        )}
      >
        {pct}%
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Field conflict row
// ─────────────────────────────────────────────────────────────────────────────

function ValuePill({
  value,
  active,
  onClick,
}: {
  value: any;
  active: boolean;
  onClick: () => void;
}) {
  const display =
    value === null || value === undefined
      ? 'null'
      : typeof value === 'object'
      ? JSON.stringify(value)
      : String(value);

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex-1 px-3 py-2 rounded-lg text-[11px] font-mono text-left transition-all duration-150',
        'border overflow-hidden text-ellipsis whitespace-nowrap max-w-[180px]',
        active
          ? 'bg-violet-500/20 border-violet-500/60 text-violet-200 shadow-[0_0_12px_rgba(139,92,246,0.3)]'
          : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10 hover:text-white/80'
      )}
      title={display}
    >
      {display}
    </button>
  );
}

function FieldDecisionRow({
  decision,
  onChange,
}: {
  decision: FieldMergeDecision;
  onChange: (updated: FieldMergeDecision) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const choose = (chosen: 'source' | 'target' | 'suggested') => {
    onChange({ ...decision, chosen });
  };

  return (
    <div
      className={cn(
        'rounded-xl border transition-all duration-200',
        decision.confidence < 0.45
          ? 'border-rose-500/30 bg-rose-500/5'
          : decision.confidence < 0.75
          ? 'border-amber-500/20 bg-amber-500/5'
          : 'border-white/8 bg-white/[0.02]'
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Field name */}
        <div className="w-28 shrink-0">
          <span className="text-[11px] font-semibold text-white/70 font-mono">
            {decision.field}
          </span>
        </div>

        {/* Confidence bar */}
        <div className="w-32 shrink-0">
          <ConfidenceBar score={decision.confidence} animate />
        </div>

        {/* Value choices */}
        <div className="flex gap-2 flex-1 min-w-0">
          <ValuePill
            value={decision.source_value}
            active={decision.chosen === 'source'}
            onClick={() => choose('source')}
          />
          <ValuePill
            value={decision.suggested_value}
            active={decision.chosen === 'suggested'}
            onClick={() => choose('suggested')}
          />
          <ValuePill
            value={decision.target_value}
            active={decision.chosen === 'target'}
            onClick={() => choose('target')}
          />
        </div>

        {/* Expand */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-white/30 hover:text-white/60 transition-colors shrink-0"
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
      </div>

      {expanded && (
        <div className="px-4 pb-3 pt-0">
          <div className="flex items-start gap-2 text-[11px] text-white/50 bg-white/5 rounded-lg px-3 py-2 border border-white/8">
            <Info className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />
            <span>{decision.reason}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Quick Apply animation
// ─────────────────────────────────────────────────────────────────────────────

function QuickApplyBtn({
  onApply,
  applying,
  disabled,
}: {
  onApply: () => void;
  applying: boolean;
  disabled?: boolean;
}) {
  const [ripple, setRipple] = useState(false);

  const handleClick = () => {
    if (applying || disabled) return;
    setRipple(true);
    setTimeout(() => setRipple(false), 600);
    onApply();
  };

  return (
    <div className="relative inline-flex">
      {/* Ripple overlay */}
      {ripple && (
        <span className="absolute inset-0 rounded-lg bg-emerald-400/30 animate-ping pointer-events-none" />
      )}
      <Button
        type="button"
        onClick={handleClick}
        disabled={applying || disabled}
        id="merge-quick-apply-btn"
        className={cn(
          'relative z-10 gap-2 px-6 font-bold text-sm',
          'bg-gradient-to-r from-emerald-600 to-teal-500',
          'hover:from-emerald-500 hover:to-teal-400',
          'text-white shadow-[0_0_24px_rgba(16,185,129,0.5)]',
          'transition-all duration-200',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          applying && 'animate-pulse'
        )}
      >
        {applying ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Applying…
          </>
        ) : (
          <>
            <Zap className="w-4 h-4" />
            Quick Apply
          </>
        )}
      </Button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main MergeDialog
// ─────────────────────────────────────────────────────────────────────────────

const MergeDialog: React.FC<MergeDialogProps> = ({ open, proposal, onApply, onClose }) => {
  const [decisions, setDecisions] = useState<FieldMergeDecision[]>([]);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  useEffect(() => {
    if (proposal) {
      setDecisions(proposal.field_decisions.map((d) => ({ ...d })));
      setApplied(false);
    }
  }, [proposal]);

  if (!proposal) return null;

  const updateDecision = (index: number, updated: FieldMergeDecision) => {
    setDecisions((prev) => prev.map((d, i) => (i === index ? updated : d)));
  };

  const handleApply = async () => {
    setApplying(true);
    try {
      await onApply(proposal, decisions);
      setApplied(true);
      toast.success(`Merged "${proposal.source_label}" → "${proposal.target_label}"`);
      setTimeout(() => onClose(), 800);
    } catch (err: any) {
      toast.error(err?.message || 'Merge failed');
    } finally {
      setApplying(false);
    }
  };

  const conflictsRemaining = decisions.filter(
    (d) =>
      d.source_value !== d.target_value &&
      d.chosen === d.suggested_value && // still on AI suggestion — may be worth reviewing
      d.confidence < 0.5
  ).length;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !applying && onClose()}>
      <DialogContent
        className={cn(
          'relative overflow-hidden max-w-2xl w-full rounded-2xl p-0',
          'bg-zinc-900/96 backdrop-blur-2xl border border-white/10',
          'shadow-[0_0_100px_rgba(0,0,0,0.9)]',
          '[background:linear-gradient(135deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.98)_100%)]'
        )}
      >
        {/* Top gradient accent */}
        <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-emerald-500/60 to-transparent" />

        {/* Success overlay */}
        {applied && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-2xl bg-emerald-950/80 backdrop-blur-sm animate-in fade-in duration-200">
            <CheckCircle2 className="w-16 h-16 text-emerald-400 mb-3 animate-in zoom-in duration-300" />
            <p className="text-lg font-semibold text-emerald-300">Merge Applied!</p>
          </div>
        )}

        {/* Header */}
        <DialogHeader className="px-6 pt-5 pb-4 border-b border-white/8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <DialogTitle className="text-base font-semibold text-white flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-emerald-400" />
                Entity Merge Proposal
              </DialogTitle>
              <p className="text-[12px] text-white/40 mt-1 font-mono">
                {proposal.source_label}{' '}
                <span className="text-emerald-400/70">→</span>{' '}
                {proposal.target_label}
              </p>
            </div>

            {/* Overall confidence */}
            <div className="text-right shrink-0">
              <span className="text-[10px] font-semibold text-white/40 uppercase tracking-wider block mb-1">
                Overall Confidence
              </span>
              <ConfidenceBar
                score={proposal.overall_confidence}
                className="w-48"
                animate
              />
            </div>
          </div>

          {/* AI Summary */}
          <div className="mt-3 flex items-start gap-2 bg-white/5 rounded-xl px-4 py-3 border border-white/8">
            <Shield className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
            <p className="text-[12px] text-white/60 leading-relaxed">{proposal.ai_summary}</p>
          </div>

          {/* Conflict warning */}
          {conflictsRemaining > 0 && (
            <div className="mt-2 flex items-center gap-2 text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>
                {conflictsRemaining} low-confidence field
                {conflictsRemaining !== 1 ? 's' : ''} may need manual review
              </span>
            </div>
          )}
        </DialogHeader>

        {/* Field decisions */}
        <div className="px-6 py-4 max-h-[50vh] overflow-y-auto custom-scrollbar space-y-2">
          {/* Column labels */}
          <div className="flex items-center gap-3 px-4 pb-1">
            <div className="w-28 shrink-0" />
            <div className="w-32 shrink-0" />
            <div className="flex gap-2 flex-1 text-[9px] font-bold uppercase tracking-widest text-white/30">
              <span className="flex-1 text-center">SOURCE</span>
              <span className="flex-1 text-center">AI SUGGESTED</span>
              <span className="flex-1 text-center">TARGET</span>
            </div>
            <div className="w-4 shrink-0" />
          </div>

          {decisions.map((decision, i) => (
            <FieldDecisionRow
              key={decision.field}
              decision={decision}
              onChange={(updated) => updateDecision(i, updated)}
            />
          ))}
        </div>

        {/* Footer */}
        <DialogFooter className="px-6 py-4 border-t border-white/8 flex-row justify-between items-center">
          <div className="text-[11px] text-white/30">
            {decisions.length} field{decisions.length !== 1 ? 's' : ''} · {proposal.conflict_count} conflict
            {proposal.conflict_count !== 1 ? 's' : ''}
          </div>
          <div className="flex gap-2 items-center">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={applying}
              id="merge-dialog-cancel-btn"
              className="text-white/50 hover:text-white hover:bg-white/5 h-9"
            >
              <XCircle className="w-4 h-4 mr-1.5" />
              Cancel
            </Button>
            <QuickApplyBtn
              onApply={handleApply}
              applying={applying}
              disabled={applied}
            />
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MergeDialog;

