"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronDown,
  ClipboardList,
  Code2,
  FileSpreadsheet,
  FileText,
  FileType,
  Gauge,
  LineChart,
  Mail,
  PieChart,
  Presentation,
  Sparkles,
  Table2,
  Terminal,
  Workflow,
} from "lucide-react";
import { CANVAS_APP_TYPE_OPTIONS } from "@/components/canvas/canvasType";

/**
 * Canvas-type picker for "Open latest draft in canvas".
 *
 * A styled popover (native <select> clipped in the narrow chat panel and
 * carried no affordance for the recommendation order). Options are ordered
 * best-match first: Auto (recommended) → Document → Email → the rest of the
 * canvas apps. Opens upward from the bottom row of the chat panel.
 */

const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  document: FileText,
  email: Mail,
  markdown: FileText,
  code: Code2,
  sheet: Table2,
  status_panel: Gauge,
  form: ClipboardList,
  line_chart: LineChart,
  bar_chart: BarChart3,
  pie_chart: PieChart,
  terminal: Terminal,
  orchestration: Workflow,
  office_word: FileType,
  office_excel: FileSpreadsheet,
  office_pptx: Presentation,
};

const RECOMMENDED = new Set(["auto", "document", "email"]);

export function CanvasTypePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on any click outside the picker.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const labelFor = (v: string) => {
    if (v === "auto") return { icon: Sparkles, label: "Auto (recommended)" };
    const opt = CANVAS_APP_TYPE_OPTIONS.find((o) => o.value === v);
    const Icon = (v && TYPE_ICONS[v]) || FileText;
    return { icon: Icon, label: opt ? `${opt.label} canvas` : v };
  };

  const current = labelFor(value);
  const CurrentIcon = current.icon;
  const recommended = [
    { value: "auto", label: "Auto — classify the draft", icon: Sparkles },
    ...CANVAS_APP_TYPE_OPTIONS.filter((o) => RECOMMENDED.has(o.value)).map(
      (o) => ({ value: o.value, label: `${o.label} canvas`, icon: TYPE_ICONS[o.value] || FileText })
    ),
  ];
  const others = CANVAS_APP_TYPE_OPTIONS.filter((o) => !RECOMMENDED.has(o.value)).map(
    (o) => ({ value: o.value, label: `${o.label} canvas`, icon: TYPE_ICONS[o.value] || FileText })
  );

  const renderOption = (opt: { value: string; label: string; icon: React.ComponentType<{ className?: string }> }) => {
    const OptionIcon = opt.icon;
    const active = value === opt.value;
    return (
      <button
        key={opt.value}
        type="button"
        onClick={() => {
          onChange(opt.value);
          setOpen(false);
        }}
        className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs text-left transition-colors ${
          active
            ? "bg-sky-950/60 text-sky-300"
            : "text-slate-300 hover:bg-slate-800/80"
        }`}
        role="option"
        aria-selected={active}
        data-testid={`canvas-type-option-${opt.value}`}
      >
        <OptionIcon className="h-3.5 w-3.5 shrink-0 opacity-80" />
        <span className="flex-1 truncate">{opt.label}</span>
        {active && <Check className="h-3.5 w-3.5 shrink-0 text-sky-400" />}
      </button>
    );
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Canvas type for the draft — recommended first: document and email cover most drafts"
        className="h-7 px-2 flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-200 transition-colors disabled:opacity-50 max-w-[150px]"
        data-testid="canvas-type-select"
      >
        <CurrentIcon className="h-3.5 w-3.5 shrink-0 text-sky-400" />
        <span className="truncate">{current.label}</span>
        <ChevronDown
          className={`h-3 w-3 shrink-0 opacity-60 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <>
          {/* click-away catcher */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            role="listbox"
            aria-label="Canvas type"
            className="absolute bottom-full right-0 mb-1.5 w-56 max-h-[60vh] overflow-y-auto rounded-xl border border-slate-700 bg-[#0F172A] shadow-2xl shadow-black/50 p-1.5 z-50"
            data-testid="canvas-type-menu"
          >
            <p className="px-2 pt-1 pb-1 text-[9px] font-bold uppercase tracking-wider text-slate-500">
              Recommended
            </p>
            {recommended.map(renderOption)}
            {others.length > 0 && (
              <>
                <div className="my-1 border-t border-slate-800" />
                <p className="px-2 pb-1 text-[9px] font-bold uppercase tracking-wider text-slate-500">
                  All canvas apps
                </p>
                {others.map(renderOption)}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default CanvasTypePicker;
