"use client";

import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Layout as LayoutIcon, FileText, Mail, Table, Code, Terminal, Plus, Search, X, Trash2, RotateCcw } from "lucide-react";

interface CanvasSummary {
    canvas_id: string;
    canvas_type: string;
    action_type: string;
    title: string | null;
    // Server-derived human title (email subject, first line of a doc,
    // Canvas.name) — present on the current backend; older payloads fall
    // back through title → canvas_id below.
    display_title?: string | null;
    snippet?: string | null;
    deleted: boolean;
    last_updated: string | null;
}

const CANVAS_TYPE_ICONS: Record<string, React.ReactNode> = {
    sheets: <Table className="h-5 w-5" />,
    email: <Mail className="h-5 w-5" />,
    docs: <FileText className="h-5 w-5" />,
    coding: <Code className="h-5 w-5" />,
    terminal: <Terminal className="h-5 w-5" />,
    orchestration: <LayoutIcon className="h-5 w-5" />,
    generic: <FileText className="h-5 w-5" />,
};

// Never surface a raw UUID: prefer the server's derived title, then an
// explicit title, and only then the id.
const displayTitle = (c: CanvasSummary) => c.display_title || c.title || c.canvas_id;

export default function CanvasIndexPage() {
    const [canvases, setCanvases] = useState<CanvasSummary[]>([]);
    const [allCanvases, setAllCanvases] = useState<CanvasSummary[]>([]);
    const [total, setTotal] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [filterType, setFilterType] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [debouncedQ, setDebouncedQ] = useState("");

    // Deleted canvases are hidden by default; the toggle fetches them so a
    // delete is always reversible from the gallery (soft delete = tombstone
    // row in the audit trail, never a hard delete).
    const [showDeleted, setShowDeleted] = useState(false);
    const [busyId, setBusyId] = useState<string | null>(null);


    // Debounce the search box so typing doesn't fire a request per keystroke.
    useEffect(() => {
        const t = setTimeout(() => setDebouncedQ(search.trim()), 300);
        return () => clearTimeout(t);
    }, [search]);

    const fetchCanvases = useCallback(async () => {
        try {
            const { apiClient } = await import("../../lib/api-client");
            // Always fetch the unfiltered-by-type list (server-side search
            // applies) to keep type-count buttons stable regardless of active
            // filter (BUG-073: previously the filter refetch returned only
            // the filtered type, making other buttons vanish).
            const params = new URLSearchParams();
            if (debouncedQ) params.set("q", debouncedQ);
            if (showDeleted) params.set("include_deleted", "true");
            const qs = params.toString();
            const url = qs ? `/api/canvas/?${qs}` : "/api/canvas/";
            const allResp = await apiClient.get(url);
            const allData = (allResp as any).data || allResp;
            const all = allData.canvases || [];
            setAllCanvases(all);
            setTotal(typeof allData.total === "number" ? allData.total : all.length);

            if (filterType) {
                setCanvases(all.filter((c: CanvasSummary) => c.canvas_type === filterType));
            } else {
                setCanvases(all);
            }
        } catch {
            setCanvases([]);
            setAllCanvases([]);
            setTotal(null);
        } finally {
            setLoading(false);
        }
    }, [filterType, debouncedQ, showDeleted]);

    useEffect(() => { fetchCanvases(); }, [fetchCanvases]);

    const handleDelete = async (canvasId: string) => {
        if (!confirm("Delete this canvas? Its audit history is preserved and it can be restored from the \"Deleted\" filter.")) return;
        setBusyId(canvasId);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.delete(`/api/canvas/${canvasId}`);
            await fetchCanvases();
        } catch (e) {
            console.error("Delete failed:", e);
        } finally {
            setBusyId(null);
        }
    };

    const handleRestore = async (canvasId: string) => {
        setBusyId(canvasId);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.post(`/api/canvas/${canvasId}/undelete`);
            await fetchCanvases();
        } catch (e) {
            console.error("Restore failed:", e);
        } finally {
            setBusyId(null);
        }
    };



    // Derive type counts from ALL canvases (not the filtered subset) so the
    // filter buttons persist regardless of the active filter.
    const typeCounts = allCanvases.reduce((acc, c) => {
        acc[c.canvas_type] = (acc[c.canvas_type] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    const isSearching = debouncedQ.length > 0;

    return (
        // _app.tsx already wraps every non-standalone page in <Layout> — a
        // second wrapper here rendered a duplicate navigation sidebar.
        <>
            <Head><title>Canvases | Atom</title></Head>
            <div className="container mx-auto max-w-5xl py-8">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold">Canvases</h1>
                        <p className="text-muted-foreground mt-1">Standalone workspace for charts, sheets, docs, and more — with live agent co-editing.</p>
                    </div>
                </div>

                {/* Search — matches titles, canvas content, type, and id */}
                <div className="relative mb-4">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="text"
                        placeholder="Search canvases by title, content, type, or id…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9 pr-9"
                        aria-label="Search canvases"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label="Clear"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    )}
                </div>

                {isSearching && !loading && (
                    <p className="text-sm text-muted-foreground mb-4" data-testid="search-results-count">
                        {total} result{total === 1 ? "" : "s"} for &ldquo;{debouncedQ}&rdquo;
                    </p>
                )}

                {/* Type filter */}
                <div className="flex gap-2 mb-6 flex-wrap items-center">
                    <Button
                        variant={showDeleted ? "default" : "outline"}
                        size="sm"
                        onClick={() => setShowDeleted(v => !v)}
                        title="Deleted canvases stay in the audit trail — show and restore them"
                        data-testid="show-deleted-toggle"
                    >
                        <Trash2 className="h-4 w-4" />
                        Show deleted
                    </Button>
                    <Button
                        variant={filterType === null ? "default" : "outline"}
                        size="sm"
                        onClick={() => setFilterType(null)}
                    >
                        All ({allCanvases.length})
                    </Button>
                    {Object.entries(typeCounts).map(([type, count]) => (
                        <Button
                            key={type}
                            variant={filterType === type ? "default" : "outline"}
                            size="sm"
                            onClick={() => setFilterType(type)}
                            className="flex items-center gap-1.5"
                        >
                            {CANVAS_TYPE_ICONS[type]}
                            <span className="capitalize">{type}</span>
                            <Badge variant="secondary" className="ml-1">{count}</Badge>
                        </Button>
                    ))}
                </div>

                {/* Canvas grid */}
                {loading ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {[1,2,3].map(i => (
                            <Card key={i}>
                                <CardContent className="pt-6">
                                    <div className="h-20 rounded animate-pulse bg-muted" />
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : canvases.length === 0 ? (
                    <Card>
                        <CardContent className="py-16 text-center">
                            {isSearching ? (
                                <>
                                    <Search className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                                    <p className="text-muted-foreground mb-1">No canvases match &ldquo;{debouncedQ}&rdquo;.</p>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Search covers titles, canvas content, types, and ids.
                                    </p>
                                    <Button variant="outline" size="sm" onClick={() => setSearch("")}>
                                        Clear search
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <Plus className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                                    <p className="text-muted-foreground mb-1">No canvases yet.</p>
                                    <p className="text-sm text-muted-foreground">
                                        Ask an agent to create one from chat, or canvases created in chat will appear here.
                                    </p>
                                </>
                            )}
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {canvases.map(c => (
                            <div key={c.canvas_id} className="relative">
                                {c.action_type === "delete" ? (
                                    <button
                                        onClick={() => handleRestore(c.canvas_id)}
                                        disabled={busyId === c.canvas_id}
                                        className="absolute top-2 right-2 z-10 p-1.5 rounded-md bg-background/80 border hover:bg-accent transition-colors"
                                        title="Restore this deleted canvas"
                                        data-testid={`restore-${c.canvas_id}`}
                                    >
                                        <RotateCcw className="h-3.5 w-3.5" />
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => handleDelete(c.canvas_id)}
                                        disabled={busyId === c.canvas_id}
                                        className="absolute top-2 right-2 z-10 p-1.5 rounded-md bg-background/80 border hover:bg-accent text-red-500 transition-colors"
                                        title="Delete this canvas (restorable)"
                                        data-testid={`delete-${c.canvas_id}`}
                                    >
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                )}
                                <Link href={`/canvas/${c.canvas_id}`}>
                                <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                                    <CardHeader>
                                        <div className="flex items-center gap-3">
                                            <div className="text-primary">
                                                {CANVAS_TYPE_ICONS[c.canvas_type] || <FileText className="h-5 w-5" />}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <CardTitle className="text-sm truncate">
                                                    {displayTitle(c)}
                                                </CardTitle>
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    {c.last_updated
                                                        ? new Date(c.last_updated).toLocaleDateString()
                                                        : "Unknown date"}
                                                </p>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        {c.snippet && (
                                            <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
                                                {c.snippet}
                                            </p>
                                        )}
                                        <div className="flex gap-1.5">
                                            <Badge variant="secondary" className="text-[10px]">
                                                {c.canvas_type}
                                            </Badge>
                                            {c.action_type === "update" && (
                                                <Badge variant="outline" className="text-[10px]">Edited</Badge>
                                            )}
                                            {c.action_type === "delete" && (
                                                <Badge variant="destructive" className="text-[10px]">Deleted</Badge>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                                </Link>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </>
    );
}
