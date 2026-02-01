"use client";

import React, { useEffect, useState } from "react";
import { FileText, Code, Globe, Clock, ChevronRight, Layers, LayoutPanelLeft } from "lucide-react";

interface Artifact {
    id: string;
    name: string;
    type: string;
    version: number;
    updated_at: string;
}

interface ArtifactSidebarProps {
    sessionId: string | null;
    onSelectArtifact: (artifactId: string) => void;
}

export function ArtifactSidebar({ sessionId, onSelectArtifact }: ArtifactSidebarProps) {
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (!sessionId) return;

        const fetchArtifacts = async () => {
            setIsLoading(true);
            try {
                const response = await fetch(`/api/artifacts?session_id=${sessionId}`);
                if (response.ok) {
                    const data = await response.json();
                    setArtifacts(data);
                }
            } catch (error) {
                console.error("Failed to fetch artifacts:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchArtifacts();
        const interval = setInterval(fetchArtifacts, 10000);
        return () => clearInterval(interval);
    }, [sessionId]);

    if (!sessionId) return null;

    return (
        <div className="h-full border-l bg-zinc-50 dark:bg-slate-900 border-zinc-200 dark:border-white/5 flex flex-col w-64">
            <div className="p-4 border-b border-zinc-200 dark:border-white/10 flex items-center gap-2">
                <LayoutPanelLeft className="h-4 w-4 text-indigo-500" />
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Team Artifacts</h3>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                {artifacts.length === 0 && !isLoading && (
                    <div className="text-center py-10 px-4">
                        <Layers className="h-8 w-8 text-zinc-300 dark:text-zinc-800 mx-auto mb-2" />
                        <p className="text-[10px] text-zinc-500 italic">No artifacts shared yet.</p>
                    </div>
                )}

                {artifacts.map((artifact) => (
                    <button
                        key={artifact.id}
                        onClick={() => onSelectArtifact(artifact.id)}
                        className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 group transition-all text-left border border-transparent hover:border-zinc-200 dark:hover:border-white/10 bg-white dark:bg-slate-800/40 shadow-sm dark:shadow-none"
                    >
                        <div className="h-8 w-8 rounded bg-zinc-100 dark:bg-white/5 flex items-center justify-center group-hover:bg-indigo-500/10 transition-colors">
                            <ArtifactIcon type={artifact.type} className="h-4 w-4 text-zinc-500 group-hover:text-indigo-500" />
                        </div>
                        <div className="flex-1 overflow-hidden">
                            <div className="flex justify-between items-center mb-0.5">
                                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-200 truncate">{artifact.name}</p>
                                <span className="text-[8px] h-3.5 px-1 bg-zinc-100 dark:bg-black/40 border border-zinc-200 dark:border-white/10 text-zinc-500 flex items-center rounded">
                                    v{artifact.version}
                                </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <Clock className="h-2.5 w-2.5 text-zinc-400" />
                                <span className="text-[10px] text-zinc-400">
                                    {formatDate(artifact.updated_at)}
                                </span>
                            </div>
                        </div>
                        <ChevronRight className="h-3 w-3 text-zinc-300 group-hover:text-zinc-500 opacity-0 group-hover:opacity-100 transition-all" />
                    </button>
                ))}
            </div>

            <div className="p-3 border-t border-zinc-200 dark:border-white/5 bg-zinc-50 dark:bg-black/20">
                <button className="w-full h-8 text-[10px] border border-zinc-200 dark:border-white/10 hover:bg-white/5 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 rounded transition-all">
                    View Full History
                </button>
            </div>
        </div>
    );
}

function ArtifactIcon({ type, className }: { type: string; className: string }) {
    switch (type) {
        case "code": return <Code className={className} />;
        case "markdown": return <FileText className={className} />;
        case "browser_view": return <Globe className={className} />;
        default: return <FileText className={className} />;
    }
}

function formatDate(dateStr: string) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}
