'use client';

// WORKBOOK RESULT CARD (2026-09-30 presentation pass): a clean rendering
// of a structured workbook/spreadsheet read — one row per requested item
// (value + basis), provenance under an expander (sheet!row, identity
// cells, alternate bases; ambiguous items list candidates), source and
// coverage in the footer. The chat message's markdown stays the
// authoritative text (copy/export/fallback) and is reachable through the
// "detailed text" toggle. Everything here is structural — no domain or
// business vocabulary.

import React from 'react';
import { ChevronDown, FileSpreadsheet } from 'lucide-react';

export interface WorkbookResultCandidate {
    ref?: string;
    value?: string | null;
    basis?: string | null;
    identity_cells?: string[];
}

export interface WorkbookResultItem {
    item: string;
    status: 'found' | 'ambiguous' | 'absent';
    value?: string | null;
    basis?: string | null;
    ref?: string;
    identity_cells?: string[];
    other_bases?: { basis?: string | null; display?: string | null }[];
    candidates?: WorkbookResultCandidate[];
    more_candidates?: number;
}

export interface WorkbookResultData {
    schema?: string;
    file?: string;
    source_note?: string | null;
    coverage?: string | null;
    items?: WorkbookResultItem[];
}

const StatusBadge: React.FC<{ status: WorkbookResultItem['status'] }> = ({ status }) => {
    const map: Record<string, { label: string; cls: string }> = {
        found: { label: 'found', cls: 'bg-green-500/10 text-green-600' },
        ambiguous: { label: 'needs your pick', cls: 'bg-amber-500/10 text-amber-600' },
        absent: { label: 'not found', cls: 'bg-muted text-muted-foreground' },
    };
    const { label, cls } = map[status] || map.absent;
    return (
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${cls}`}>
            {label}
        </span>
    );
};

const WorkbookResultCard: React.FC<{
    result: WorkbookResultData;
    rawText?: string;
}> = ({ result, rawText }) => {
    const [expanded, setExpanded] = React.useState<Record<number, boolean>>({});
    const [showRaw, setShowRaw] = React.useState(false);
    const items = result.items || [];
    return (
        <div
            className="my-2 rounded-lg border bg-card text-card-foreground shadow-sm overflow-hidden"
            data-testid="workbook-result-card"
        >
            <div className="flex items-center gap-2 border-b bg-muted/40 px-3 py-2">
                <FileSpreadsheet className="h-4 w-4 text-primary shrink-0" />
                <span className="font-medium text-sm truncate" data-testid="workbook-result-file">
                    {result.file || 'Workbook'}
                </span>
                {result.source_note && (
                    <span className="text-[11px] text-muted-foreground truncate">
                        · {result.source_note}
                    </span>
                )}
            </div>
            <div className="divide-y divide-border">
                {items.map((it, i) => (
                    <div key={`${it.item}-${i}`} className="px-3 py-2" data-testid="workbook-result-row">
                        <div className="flex items-baseline gap-2 flex-wrap">
                            <span className="text-sm font-medium">{it.item}</span>
                            <StatusBadge status={it.status} />
                            {it.status === 'found' && (
                                <span className="ml-auto text-sm font-semibold tabular-nums">
                                    {it.value}
                                    {it.basis && (
                                        <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                                            ({it.basis})
                                        </span>
                                    )}
                                </span>
                            )}
                            {it.status === 'ambiguous' && (
                                <span className="ml-auto text-[11px] text-muted-foreground">
                                    {(it.candidates || []).length + (it.more_candidates || 0)} candidate rows
                                </span>
                            )}
                        </div>
                        {it.status !== 'absent' && (
                            <>
                                <button
                                    type="button"
                                    onClick={() => setExpanded(p => ({ ...p, [i]: !p[i] }))}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                                    data-testid={`workbook-result-toggle-${i}`}
                                    aria-expanded={!!expanded[i]}
                                >
                                    <ChevronDown
                                        className={`h-3 w-3 transition-transform ${expanded[i] ? 'rotate-180' : ''}`}
                                    />
                                    {expanded[i] ? 'hide evidence' : 'evidence'}
                                </button>
                                {expanded[i] && (
                                    <div className="mt-1 space-y-1 text-[11px] text-muted-foreground" data-testid={`workbook-result-evidence-${i}`}>
                                        {it.status === 'found' && (
                                            <>
                                                <div>
                                                    matched at <span className="font-mono">{it.ref}</span>
                                                    {it.identity_cells?.length ? (
                                                        <> · identity <span className="font-mono">{it.identity_cells.join(', ')}</span></>
                                                    ) : null}
                                                </div>
                                                {!!it.other_bases?.length && (
                                                    <div>
                                                        other bases:{' '}
                                                        {it.other_bases
                                                            .map(b => `${b.basis} ${b.display}`)
                                                            .join('; ')}
                                                    </div>
                                                )}
                                            </>
                                        )}
                                        {it.status === 'ambiguous' && (
                                            <ul className="space-y-0.5">
                                                {(it.candidates || []).map((c, j) => (
                                                    <li key={j}>
                                                        <span className="font-mono">{c.ref}</span>
                                                        {c.value ? ` — ${c.value}` : ''}
                                                        {c.basis ? ` (${c.basis})` : ''}
                                                        {c.identity_cells?.length ? (
                                                            <> · identity <span className="font-mono">{c.identity_cells.join(', ')}</span></>
                                                        ) : null}
                                                    </li>
                                                ))}
                                                {!!it.more_candidates && (
                                                    <li>+{it.more_candidates} more</li>
                                                )}
                                            </ul>
                                        )}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                ))}
            </div>
            {(result.coverage || rawText) && (
                <div className="border-t bg-muted/20 px-3 py-2 flex items-center gap-3 flex-wrap">
                    {result.coverage && (
                        <span className="text-[11px] text-muted-foreground" data-testid="workbook-result-coverage">
                            {result.coverage} · not an absence claim on the live file
                        </span>
                    )}
                    {rawText && (
                        <button
                            type="button"
                            onClick={() => setShowRaw(v => !v)}
                            className="ml-auto text-[11px] text-muted-foreground underline-offset-2 hover:underline"
                            data-testid="workbook-result-raw-toggle"
                        >
                            {showRaw ? 'hide detailed text' : 'detailed text'}
                        </button>
                    )}
                </div>
            )}
            {showRaw && rawText && (
                <pre
                    className="max-h-72 overflow-auto border-t px-3 py-2 text-[11px] whitespace-pre-wrap text-muted-foreground"
                    data-testid="workbook-result-raw"
                >
                    {rawText}
                </pre>
            )}
        </div>
    );
};

export default WorkbookResultCard;
