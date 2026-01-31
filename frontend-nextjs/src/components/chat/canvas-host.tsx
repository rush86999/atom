"use client";

import React, { useEffect, useState } from "react";
import { X, Code, Camera, Globe, Play, Layers } from "lucide-react";
import { marked } from "marked";

interface CanvasState {
    visible: boolean;
    component: "markdown" | "chart" | "form" | "status_panel" | "eval" | "snapshot" | "browser_view" | "custom";
    title?: string;
    data: any;
}

interface CanvasHostProps {
    lastMessage: any;
}

export function CanvasHost({ lastMessage }: CanvasHostProps) {
    const [state, setState] = useState<CanvasState | null>(null);

    useEffect(() => {
        if (!lastMessage) return;

        // Check for canvas event type
        if (lastMessage.type === "canvas:update" || lastMessage.type === "canvas:present") {
            const { action, component, data, title } = lastMessage.data || lastMessage;

            if (action === "close") {
                setState(null);
            } else {
                setState({
                    visible: true,
                    component: component || "markdown",
                    title,
                    data,
                });
            }
        }
    }, [lastMessage]);

    if (!state || !state.visible) return null;

    return (
        <div className="absolute top-4 right-4 bottom-4 w-[450px] bg-white dark:bg-zinc-900 border shadow-2xl z-50 rounded-xl flex flex-col overflow-hidden ring-1 ring-zinc-200 dark:ring-zinc-800">
            <div className="p-4 border-b flex items-center justify-between bg-zinc-50 dark:bg-zinc-900/50 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                    <CanvasIcon component={state.component} />
                    <h3 className="font-semibold text-sm truncate max-w-[300px] text-zinc-900 dark:text-zinc-100">
                        {state.title || "Agent Canvas"}
                    </h3>
                </div>
                <button
                    onClick={() => setState(null)}
                    className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                >
                    <X className="h-4 w-4 text-zinc-500" />
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4 custom-scrollbar">
                <CanvasContent component={state.component} data={state.data} />
            </div>
        </div>
    );
}

function CanvasIcon({ component }: { component: string }) {
    switch (component) {
        case "eval": return <Code className="h-4 w-4 text-blue-500" />;
        case "snapshot": return <Camera className="h-4 w-4 text-purple-500" />;
        case "browser_view": return <Globe className="h-4 w-4 text-green-500" />;
        default: return <Layers className="h-4 w-4 text-zinc-500" />;
    }
}

function CanvasContent({ component, data }: { component: string; data: any }) {
    if (!data) return <div className="text-zinc-500 p-4">No data to display</div>;

    switch (component) {
        case "markdown":
            const htmlContent = marked.parse(typeof data === 'string' ? data : data.content || '');
            return (
                <div
                    className="prose dark:prose-invert max-w-none text-sm leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: htmlContent as string }}
                />
            );

        case "eval":
            return (
                <div className="space-y-4">
                    <div className="bg-zinc-950 rounded-lg p-4 font-mono text-xs overflow-auto border border-zinc-800 shadow-inner">
                        <div className="flex justify-between items-center mb-2 border-b border-zinc-800 pb-2">
                            <span className="text-zinc-500">javascript</span>
                            <button className="h-6 px-2 text-[10px] text-zinc-400 hover:text-white flex items-center gap-1 hover:bg-zinc-800 rounded">
                                <Play className="h-3 w-3" /> Run
                            </button>
                        </div>
                        <pre className="text-blue-400">{data.code || data}</pre>
                    </div>
                    {data.output && (
                        <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-3 border">
                            <p className="text-[10px] font-bold uppercase text-zinc-500 mb-1">Output</p>
                            <pre className="text-xs text-zinc-700 dark:text-zinc-300">
                                {typeof data.output === 'string' ? data.output : JSON.stringify(data.output, null, 2)}
                            </pre>
                        </div>
                    )}
                </div>
            );

        case "snapshot":
            return (
                <div className="space-y-4">
                    <div className="flex flex-wrap gap-2 mb-4">
                        {data.timestamp && (
                            <span className="px-2 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800 text-[10px] text-zinc-500 border border-zinc-200 dark:border-zinc-700">
                                Captured: {new Date(data.timestamp).toLocaleTimeString()}
                            </span>
                        )}
                        {data.source && (
                            <span className="px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-900/20 text-[10px] text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50">
                                Source: {data.source}
                            </span>
                        )}
                    </div>
                    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden bg-white dark:bg-zinc-950">
                        <div className="p-2 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex justify-between items-center">
                            <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">State Tree</span>
                        </div>
                        <pre className="p-4 text-[11px] overflow-auto max-h-[400px] bg-zinc-50/50 dark:bg-zinc-900/20 font-mono text-zinc-600 dark:text-zinc-400">
                            {JSON.stringify(data.state || data, null, 2)}
                        </pre>
                    </div>
                </div>
            );

        case "browser_view":
            return (
                <div className="space-y-4">
                    <div className="flex items-center gap-2 p-2 bg-zinc-100 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700 text-xs">
                        <Globe className="h-3 w-3 text-zinc-500" />
                        <span className="truncate flex-1 text-zinc-500 italic">{data.url || "about:blank"}</span>
                    </div>
                    {data.screenshot ? (
                        <div className="border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden shadow-sm relative group bg-zinc-900">
                            <img
                                src={data.screenshot.startsWith('data:') ? data.screenshot : `data:image/png;base64,${data.screenshot}`}
                                alt="Browser Snapshot"
                                className="w-full h-auto cursor-zoom-in"
                            />
                            <div className="absolute inset-x-0 bottom-0 bg-black/60 backdrop-blur-sm p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <p className="text-[10px] text-white text-center">Interactive remote control disabled in preview</p>
                            </div>
                        </div>
                    ) : (
                        <div className="h-[300px] border border-dashed border-zinc-300 dark:border-zinc-700 rounded-lg flex flex-col items-center justify-center text-zinc-400">
                            <Globe className="h-8 w-8 mb-2 opacity-20" />
                            <p className="text-xs">Connecting to remote browser...</p>
                        </div>
                    )}
                </div>
            );

        default:
            return (
                <div className="p-6 border rounded-xl border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/20 flex flex-col items-center justify-center text-center">
                    <Layers className="h-10 w-10 text-zinc-300 mb-4" />
                    <p className="text-sm font-medium mb-1 dark:text-zinc-200">Custom Component: {component}</p>
                    <p className="text-xs text-zinc-500 mb-4">Rendering raw data payload</p>
                    <pre className="text-[10px] text-left overflow-auto bg-zinc-100 dark:bg-zinc-800 p-4 rounded-lg w-full max-h-[300px] text-zinc-600 dark:text-zinc-300">
                        {JSON.stringify(data, null, 2)}
                    </pre>
                </div>
            );
    }
}
