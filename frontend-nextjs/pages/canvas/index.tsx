"use client";

import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Layout as LayoutIcon, FileText, Mail, Table, Code, Terminal, Plus } from "lucide-react";
import Layout from "@/components/layout/Layout";

interface CanvasSummary {
    canvas_id: string;
    canvas_type: string;
    action_type: string;
    title: string | null;
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

export default function CanvasIndexPage() {
    const [canvases, setCanvases] = useState<CanvasSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [filterType, setFilterType] = useState<string | null>(null);

    const fetchCanvases = useCallback(async () => {
        try {
            const { apiClient } = await import("../../lib/api-client");
            const params = filterType ? `?canvas_type=${filterType}` : "";
            const resp = await apiClient.get(`/api/canvas/${params}`);
            const data = (resp as any).data || resp;
            setCanvases(data.canvases || []);
        } catch {
            setCanvases([]);
        } finally {
            setLoading(false);
        }
    }, [filterType]);

    useEffect(() => { fetchCanvases(); }, [fetchCanvases]);

    const typeCounts = canvases.reduce((acc, c) => {
        acc[c.canvas_type] = (acc[c.canvas_type] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    return (
        <Layout>
            <Head><title>Canvases | Atom</title></Head>
            <div className="container mx-auto max-w-5xl py-8">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold">Canvases</h1>
                        <p className="text-muted-foreground mt-1">Standalone workspace for charts, sheets, docs, and more — with live agent co-editing.</p>
                    </div>
                </div>

                {/* Type filter */}
                <div className="flex gap-2 mb-6 flex-wrap">
                    <Button
                        variant={filterType === null ? "default" : "outline"}
                        size="sm"
                        onClick={() => setFilterType(null)}
                    >
                        All ({canvases.length})
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
                            <Plus className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                            <p className="text-muted-foreground mb-1">No canvases yet.</p>
                            <p className="text-sm text-muted-foreground">
                                Ask an agent to create one from chat, or canvases created in chat will appear here.
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {canvases.map(c => (
                            <Link key={c.canvas_id} href={`/canvas/${c.canvas_id}`}>
                                <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                                    <CardHeader>
                                        <div className="flex items-center gap-3">
                                            <div className="text-primary">
                                                {CANVAS_TYPE_ICONS[c.canvas_type] || <FileText className="h-5 w-5" />}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <CardTitle className="text-sm truncate">
                                                    {c.title || c.canvas_id}
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
                        ))}
                    </div>
                )}
            </div>
        </Layout>
    );
}
