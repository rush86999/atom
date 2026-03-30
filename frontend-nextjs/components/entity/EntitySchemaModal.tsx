'use client';

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import MonacoSchemaEditor from './MonacoSchemaEditor';
import VisualSchemaBuilder from './VisualSchemaBuilder';
import { validateSchema } from '@/src/lib/validators/jsonSchema';
import {
  LayoutGrid,
  Code2,
  Sparkles,
  Loader2,
  Brain,
  GitCompare,
  CheckCircle2,
  XCircle,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface EntitySchemaModalProps {
  open: boolean;
  entityType?: any;
  onSuccess: (entityType: any) => void;
  onClose: () => void;
  workspaceId: string;
}

type ModalView = 'form' | 'diff';
type EditorMode = 'visual' | 'monaco';

const DEFAULT_SCHEMA = JSON.stringify(
  {
    $schema: 'https://json-schema.org/draft/2020-12/schema',
    type: 'object',
    properties: {
      name: { type: 'string' },
      description: { type: 'string' },
    },
    required: ['name'],
  },
  null,
  2
);

// ─────────────────────────────────────────────────────────────────────────────
// Thinking animation state machine
// ─────────────────────────────────────────────────────────────────────────────

const THINKING_STEPS = [
  'Analyzing entity description…',
  'Inferring field types and constraints…',
  'Generating required properties…',
  'Applying JSON Schema best practices…',
  'Finalizing schema structure…',
];

function useThinkingAnimation(active: boolean) {
  const [stepIndex, setStepIndex] = useState(0);
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!active) {
      setStepIndex(0);
      setDots('');
      return;
    }

    const stepTimer = setInterval(() => {
      setStepIndex((i) => (i + 1) % THINKING_STEPS.length);
    }, 900);

    const dotTimer = setInterval(() => {
      setDots((d) => (d.length >= 3 ? '' : d + '.'));
    }, 350);

    return () => {
      clearInterval(stepTimer);
      clearInterval(dotTimer);
    };
  }, [active]);

  return { step: THINKING_STEPS[stepIndex], dots };
}

// ─────────────────────────────────────────────────────────────────────────────
// Minimal schema diff renderer (token-level)
// ─────────────────────────────────────────────────────────────────────────────

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
}

function computeLineDiff(before: string, after: string): DiffLine[] {
  const bLines = before.split('\n');
  const aLines = after.split('\n');
  const bSet = new Set(bLines);
  const aSet = new Set(aLines);

  const lines: DiffLine[] = [];

  // Simple LCS-based diff — render removed then added for each divergence
  const maxLen = Math.max(bLines.length, aLines.length);
  let bi = 0;
  let ai = 0;

  while (bi < bLines.length || ai < aLines.length) {
    const bLine = bLines[bi];
    const aLine = aLines[ai];

    if (bLine === aLine) {
      lines.push({ type: 'unchanged', content: bLine });
      bi++;
      ai++;
    } else {
      // Look ahead for match in either direction (max 3 lines)  
      let foundInA = -1;
      let foundInB = -1;
      for (let la = 1; la <= 3 && ai + la < aLines.length; la++) {
        if (aLines[ai + la] === bLine) { foundInA = la; break; }
      }
      for (let lb = 1; lb <= 3 && bi + lb < bLines.length; lb++) {
        if (bLines[bi + lb] === aLine) { foundInB = lb; break; }
      }

      if (foundInA !== -1 && (foundInB === -1 || foundInA <= foundInB)) {
        // Skip ahead in 'after' — emit as added
        for (let k = 0; k < foundInA; k++) {
          lines.push({ type: 'added', content: aLines[ai++] });
        }
      } else if (foundInB !== -1) {
        // Skip ahead in 'before' — emit as removed
        for (let k = 0; k < foundInB; k++) {
          lines.push({ type: 'removed', content: bLines[bi++] });
        }
      } else {
        // No match found, emit both as changed
        if (bi < bLines.length) lines.push({ type: 'removed', content: bLines[bi++] });
        if (ai < aLines.length) lines.push({ type: 'added', content: aLines[ai++] });
      }
    }
  }

  return lines;
}

function SchemaDiffPanel({
  before,
  after,
  onAccept,
  onReject,
}: {
  before: string;
  after: string;
  onAccept: () => void;
  onReject: () => void;
}) {
  const diff = computeLineDiff(before, after);
  const addedCount = diff.filter((l) => l.type === 'added').length;
  const removedCount = diff.filter((l) => l.type === 'removed').length;

  return (
    <div className="flex flex-col h-full gap-3 animate-in fade-in slide-in-from-right-4 duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="text-[10px] font-bold">+{addedCount}</span>
            <span className="text-white/30">additions</span>
          </span>
          <span className="flex items-center gap-1 text-rose-400">
            <span className="text-[10px] font-bold">-{removedCount}</span>
            <span className="text-white/30">removals</span>
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={onReject}
            className="h-7 px-3 text-[11px] text-rose-400 border border-rose-500/30 hover:bg-rose-500/10"
            id="schema-diff-reject-btn"
          >
            <XCircle className="w-3 h-3 mr-1" />
            Keep Current
          </Button>
          <Button
            size="sm"
            onClick={onAccept}
            className="h-7 px-3 text-[11px] bg-emerald-500 hover:bg-emerald-600 text-white shadow-[0_0_16px_rgba(16,185,129,0.4)]"
            id="schema-diff-accept-btn"
          >
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Apply AI Schema
          </Button>
        </div>
      </div>

      {/* Diff viewer */}
      <div className="flex-1 overflow-auto rounded-xl border border-white/10 bg-black/40 font-mono text-xs leading-5">
        {diff.map((line, i) => (
          <div
            key={i}
            className={cn(
              'flex px-3 py-[1px] whitespace-pre',
              line.type === 'added' &&
                'bg-emerald-500/10 border-l-2 border-emerald-500 text-emerald-300',
              line.type === 'removed' &&
                'bg-rose-500/10 border-l-2 border-rose-500 text-rose-300 line-through opacity-60',
              line.type === 'unchanged' && 'text-white/40 border-l-2 border-transparent'
            )}
          >
            <span className="w-4 select-none mr-3 text-white/20">
              {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
            </span>
            {line.content}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Thinking Overlay
// ─────────────────────────────────────────────────────────────────────────────

function ThinkingOverlay({ active }: { active: boolean }) {
  const { step, dots } = useThinkingAnimation(active);

  if (!active) return null;

  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-2xl bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      {/* Pulsing brain icon */}
      <div className="relative mb-6">
        <div className="absolute inset-0 rounded-full bg-violet-500/20 animate-ping" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 to-fuchsia-500/30 border border-violet-500/40 shadow-[0_0_40px_rgba(139,92,246,0.4)]">
          <Brain className="h-7 w-7 text-violet-300 animate-pulse" />
        </div>
      </div>

      {/* Step text */}
      <p className="text-sm font-medium text-white/80 mb-1 transition-all duration-300">
        {step}
        <span className="text-violet-400">{dots}</span>
      </p>
      <p className="text-[11px] text-white/30">AI is generating your schema</p>

      {/* Progress bar */}
      <div className="mt-5 h-0.5 w-48 bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full animate-[shimmer_1.5s_ease-in-out_infinite]"
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Modal Component
// ─────────────────────────────────────────────────────────────────────────────

const EntitySchemaModal: React.FC<EntitySchemaModalProps> = ({
  open,
  entityType,
  onSuccess,
  onClose,
  workspaceId,
}) => {
  const [formData, setFormData] = useState({
    slug: entityType?.slug || '',
    display_name: entityType?.display_name || '',
    description: entityType?.description || '',
    json_schema: entityType?.json_schema
      ? JSON.stringify(entityType.json_schema, null, 2)
      : DEFAULT_SCHEMA,
    available_skills: entityType?.available_skills || [],
  });

  const [editorMode, setEditorMode] = useState<EditorMode>('visual');
  const [view, setView] = useState<ModalView>('form');
  const [skills, setSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(true);
  const [pendingSchema, setPendingSchema] = useState<string | null>(null);
  const isEdit = !!entityType;

  // Reset when opened
  useEffect(() => {
    if (open) {
      setView('form');
      setPendingSchema(null);
      setSuggesting(false);
    }
  }, [open]);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const r = await axios.get('/api/skills', {
          headers: { 'X-Workspace-ID': workspaceId },
        });
        setSkills(r.data || []);
      } catch {
        // no-op
      } finally {
        setFetchLoading(false);
      }
    };
    if (open) fetchSkills();
  }, [open, workspaceId]);

  const handleAiSuggest = async () => {
    if (!formData.display_name) {
      toast.error('Please enter a Display Name first');
      return;
    }
    setSuggesting(true);
    try {
      const resp = await axios.post(
        '/api/entity-types/suggest-schema',
        { display_name: formData.display_name, description: formData.description },
        { headers: { 'X-Workspace-ID': workspaceId } }
      );
      const schema = resp.data.success ? resp.data.data : resp.data;
      const newSchemaStr = JSON.stringify(schema, null, 2);

      // Show diff view instead of applying immediately
      setPendingSchema(newSchemaStr);
      setView('diff');
      toast.success('AI schema ready — review changes below');
    } catch {
      toast.error('Failed to get AI suggestion');
    } finally {
      setSuggesting(false);
    }
  };

  const handleAcceptDiff = () => {
    if (pendingSchema) {
      setFormData((prev) => ({ ...prev, json_schema: pendingSchema }));
      toast.success('AI schema applied!');
    }
    setView('form');
    setPendingSchema(null);
  };

  const handleRejectDiff = () => {
    setView('form');
    setPendingSchema(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = JSON.parse(formData.json_schema);
      const validation = validateSchema(parsed);
      if (!validation.valid) {
        toast.error(`Invalid Schema: ${validation.errors[0]}`);
        return;
      }
    } catch (err: any) {
      toast.error(`JSON Parse error: ${err.message}`);
      return;
    }

    setLoading(true);
    try {
      const payload = { ...formData, json_schema: JSON.parse(formData.json_schema) };
      let response;
      if (isEdit) {
        response = await axios.put(`/api/entity-types/${entityType.id}`, payload, {
          headers: { 'X-Workspace-ID': workspaceId },
        });
        toast.success('Entity type updated successfully');
      } else {
        response = await axios.post('/api/entity-types', payload, {
          headers: { 'X-Workspace-ID': workspaceId },
        });
        toast.success('Entity type created successfully');
      }
      onSuccess(response.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save entity type');
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = (skillId: string) => {
    setFormData((prev) => ({
      ...prev,
      available_skills: prev.available_skills.includes(skillId)
        ? prev.available_skills.filter((id: string) => id !== skillId)
        : [...prev.available_skills, skillId],
    }));
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className={cn(
          'relative overflow-hidden',
          'max-w-3xl w-full',
          'bg-zinc-900/95 backdrop-blur-xl',
          'border border-white/10',
          'shadow-[0_0_80px_rgba(0,0,0,0.8)]',
          'rounded-2xl p-0',
          '[background:linear-gradient(135deg,rgba(24,24,27,0.98)_0%,rgba(18,18,22,0.98)_100%)]',
          view === 'diff' && 'max-w-4xl'
        )}
      >
        {/* Gradient accent border */}
        <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-violet-500/60 to-transparent" />

        {/* AI Thinking Overlay */}
        <ThinkingOverlay active={suggesting} />

        {/* Header */}
        <DialogHeader className="px-6 pt-5 pb-3 border-b border-white/8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {view === 'diff' && (
                <button
                  onClick={() => setView('form')}
                  className="text-white/40 hover:text-white transition-colors"
                  id="schema-modal-back-btn"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              )}
              <DialogTitle className="text-base font-semibold text-white">
                {view === 'diff' ? (
                  <span className="flex items-center gap-2">
                    <GitCompare className="w-4 h-4 text-violet-400" />
                    Schema Diff — AI Suggestion vs. Current
                  </span>
                ) : (
                  <>{isEdit ? 'Edit' : 'Create'} Entity Type</>
                )}
              </DialogTitle>
            </div>

            {/* AI Suggest button (shown in form view) */}
            {view === 'form' && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleAiSuggest}
                disabled={suggesting || !formData.display_name}
                id="entity-ai-suggest-btn"
                className={cn(
                  'h-8 px-3 text-[11px] font-bold gap-1.5 rounded-lg transition-all',
                  'border border-violet-500/30 text-violet-300',
                  'hover:bg-violet-500/15 hover:border-violet-500/60',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                  suggesting &&
                    'animate-pulse bg-violet-500/10 text-violet-200 border-violet-400/60'
                )}
              >
                {suggesting ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                {suggesting ? 'THINKING…' : 'AI SUGGEST'}
              </Button>
            )}
          </div>
        </DialogHeader>

        {/* Body */}
        <div className="px-6 py-5 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {view === 'diff' && pendingSchema ? (
            <SchemaDiffPanel
              before={formData.json_schema}
              after={pendingSchema}
              onAccept={handleAcceptDiff}
              onReject={handleRejectDiff}
            />
          ) : (
            <form id="entity-schema-form" onSubmit={handleSubmit} className="space-y-5">
              {/* Name + Slug row */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label
                    htmlFor="modal-display-name"
                    className="text-[12px] font-semibold text-white/70 uppercase tracking-wider"
                  >
                    Display Name
                  </Label>
                  <Input
                    id="modal-display-name"
                    placeholder="e.g. Financial Transaction"
                    value={formData.display_name}
                    onChange={(e) =>
                      setFormData({ ...formData, display_name: e.target.value })
                    }
                    required
                    className="bg-white/5 border-white/10 text-white focus:ring-violet-500/50 focus:border-violet-500/50"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="modal-slug"
                    className="text-[12px] font-semibold text-white/70 uppercase tracking-wider"
                  >
                    Slug
                  </Label>
                  <Input
                    id="modal-slug"
                    placeholder="e.g. financial-transaction"
                    value={formData.slug}
                    onChange={(e) =>
                      setFormData({ ...formData, slug: e.target.value })
                    }
                    required
                    disabled={isEdit}
                    className="bg-white/5 border-white/10 text-white disabled:opacity-50 focus:ring-violet-500/50"
                  />
                </div>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="modal-description"
                  className="text-[12px] font-semibold text-white/70 uppercase tracking-wider"
                >
                  Description
                </Label>
                <Textarea
                  id="modal-description"
                  placeholder="Describe what this entity represents…"
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="bg-white/5 border-white/10 text-white min-h-[72px] focus:ring-violet-500/50"
                />
              </div>

              {/* Schema editor */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-[12px] font-semibold text-white/70 uppercase tracking-wider">
                    Schema Definition
                  </Label>
                  <div className="flex bg-white/5 p-0.5 rounded-lg border border-white/10">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditorMode('visual')}
                      id="schema-mode-visual"
                      className={cn(
                        'h-7 px-3 text-[10px] font-bold gap-1.5 rounded-md transition-all',
                        editorMode === 'visual'
                          ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                          : 'text-muted-foreground hover:text-white'
                      )}
                    >
                      <LayoutGrid className="w-3 h-3" />
                      VISUAL
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditorMode('monaco')}
                      id="schema-mode-code"
                      className={cn(
                        'h-7 px-3 text-[10px] font-bold gap-1.5 rounded-md transition-all',
                        editorMode === 'monaco'
                          ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                          : 'text-muted-foreground hover:text-white'
                      )}
                    >
                      <Code2 className="w-3 h-3" />
                      CODE
                    </Button>
                  </div>
                </div>

                <div className="min-h-[300px]">
                  {editorMode === 'visual' ? (
                    <VisualSchemaBuilder
                      schema={JSON.parse(formData.json_schema || '{}')}
                      onChange={(s) =>
                        setFormData({
                          ...formData,
                          json_schema: JSON.stringify(s, null, 2),
                        })
                      }
                    />
                  ) : (
                    <MonacoSchemaEditor
                      value={formData.json_schema}
                      onChange={(v) => setFormData({ ...formData, json_schema: v })}
                    />
                  )}
                </div>
              </div>

              {/* Skills */}
              <div className="space-y-2">
                <Label className="text-[12px] font-semibold text-white/70 uppercase tracking-wider">
                  Available Skills
                </Label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {fetchLoading ? (
                    <div className="col-span-full text-center py-3 text-white/30 text-xs italic">
                      Loading skills…
                    </div>
                  ) : skills.length === 0 ? (
                    <div className="col-span-full text-center py-3 text-white/30 text-xs italic">
                      No skills available
                    </div>
                  ) : (
                    skills.map((skill) => (
                      <div
                        key={skill.id}
                        onClick={() => toggleSkill(skill.id)}
                        className={cn(
                          'flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all duration-150',
                          formData.available_skills.includes(skill.id)
                            ? 'bg-violet-500/20 border-violet-500/50 text-white shadow-[0_0_10px_rgba(139,92,246,0.15)]'
                            : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10 hover:border-white/20'
                        )}
                      >
                        <div
                          className={cn(
                            'w-2 h-2 rounded-full transition-all',
                            formData.available_skills.includes(skill.id)
                              ? 'bg-violet-400 animate-pulse'
                              : 'bg-white/20'
                          )}
                        />
                        <span className="text-[11px] font-medium truncate">{skill.name}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        {view === 'form' && (
          <DialogFooter className="px-6 py-4 border-t border-white/8">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              id="entity-modal-cancel-btn"
              className="text-white/50 hover:text-white hover:bg-white/5"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="entity-schema-form"
              disabled={loading}
              id="entity-modal-save-btn"
              className={cn(
                'bg-gradient-to-r from-violet-600 to-fuchsia-600',
                'hover:from-violet-500 hover:to-fuchsia-500',
                'text-white px-8 shadow-[0_0_20px_rgba(139,92,246,0.4)]',
                'transition-all duration-200',
                loading && 'opacity-70 cursor-not-allowed'
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving…
                </>
              ) : isEdit ? (
                'Update Type'
              ) : (
                'Create Type'
              )}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default EntitySchemaModal;
