"use client";

import React, { useEffect, useState, useRef } from "react";
import { X, Code, Camera, Globe, Play, Layers, Save, History, Check, Loader2 } from "lucide-react";
import { marked } from "marked";
import Editor from "@monaco-editor/react";

interface CanvasState {
    id?: string;
    visible: boolean;
    component: "markdown" | "code" | "chart" | "form" | "status_panel" | "eval" | "snapshot" | "browser_view" | "email" | "sheet" | "document" | "custom";
    title?: string;
    data: any;
    version?: number;
}

interface CanvasHostProps {
    lastMessage: any;
}

export function CanvasHost({ lastMessage }: CanvasHostProps) {
    const [state, setState] = useState<CanvasState | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const localContentRef = useRef<string>("");
    const [emailMetadata, setEmailMetadata] = useState({ to: "", subject: "" });
    const [sheetData, setSheetData] = useState<any[][]>([]);
    const [showPreview, setShowPreview] = useState(false);

    useEffect(() => {
        if (!lastMessage) return;

        // Check for canvas event type
        if (lastMessage.type === "canvas:update" || lastMessage.type === "canvas:present") {
            const { action, component, data, title, id, version, metadata } = lastMessage.data || lastMessage;

            if (action === "close") {
                setState(null);
            } else {
                const content = typeof data === 'string' ? data : (data.content || JSON.stringify(data, null, 2));
                localContentRef.current = content;

                setState({
                    id,
                    visible: true,
                    component: component === 'eval' ? 'code' : (component || "markdown"),
                    title,
                    data,
                    version
                });

                if (component === "email" && metadata) {
                    setEmailMetadata({ to: metadata.to || "", subject: metadata.subject || "" });
                }

                if (component === "sheet") {
                    setSheetData(Array.isArray(data) ? data : (data.rows || [["", "", ""], ["", "", ""]]));
                }

                setHasUnsavedChanges(false);
            }
        }
    }, [lastMessage]);

    const handleSave = async () => {
        if (!state) return;
        setIsSaving(true);

        const payload: any = {
            id: state.id,
            name: state.title || "Untitled Artifact",
            type: state.component,
            content: localContentRef.current,
            session_id: (lastMessage as any)?.sessionId
        };

        if (state.component === "email") {
            payload.metadata = emailMetadata;
        } else if (state.component === "sheet") {
            payload.content = JSON.stringify(sheetData);
        }

        try {
            const endpoint = state.id ? "/api/artifacts/update" : "/api/artifacts";
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const updated = await response.json();
                setState(prev => prev ? { ...prev, id: updated.id, version: updated.version } : null);
                setHasUnsavedChanges(false);
            }
        } catch (error) {
            console.error("Error saving artifact:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleSendEmail = async () => {
        alert(`Sending email to ${emailMetadata.to}...`);
    };

    if (!state || !state.visible) return null;

    return (
        <div className="absolute top-4 right-4 bottom-4 w-[600px] bg-white dark:bg-[#0F172A] border shadow-2xl z-50 rounded-xl flex flex-col overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10">
            <div className="p-3 border-b flex items-center justify-between bg-zinc-50 dark:bg-slate-900/50 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                    <CanvasIcon component={state.component} />
                    <div className="flex flex-col">
                        <h3 className="font-semibold text-sm truncate max-w-[250px] text-zinc-900 dark:text-zinc-100">
                            {state.title || "Agent Artifact"}
                        </h3>
                        <div className="flex items-center gap-2">
                            {state.version && (
                                <span className="text-[10px] text-zinc-500 font-mono">v{state.version}</span>
                            )}
                            <span className="text-[8px] h-3.5 px-1 uppercase bg-zinc-100 dark:bg-white/5 border border-zinc-200 dark:border-white/10 text-zinc-500 flex items-center rounded">
                                {state.component}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {state.component === "email" && (
                        <button
                            onClick={handleSendEmail}
                            className="h-8 px-3 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-colors flex items-center gap-1.5"
                        >
                            <Play className="h-3 w-3" /> Send
                        </button>
                    )}
                    {(hasUnsavedChanges || state.component === 'sheet') && (
                        <button
                            onClick={handleSave}
                            disabled={isSaving}
                            className="flex items-center gap-1.5 px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-colors disabled:opacity-50"
                        >
                            {isSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                            Save Changes
                        </button>
                    )}
                    <button
                        onClick={() => setState(null)}
                        className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <X className="h-4 w-4 text-zinc-500" />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-hidden relative">
                <CanvasContent
                    component={state.component}
                    data={state.data}
                    emailMetadata={emailMetadata}
                    setEmailMetadata={(m) => { setEmailMetadata(m); setHasUnsavedChanges(true); }}
                    sheetData={sheetData}
                    setSheetData={(d) => { setSheetData(d); setHasUnsavedChanges(true); }}
                    showPreview={showPreview}
                    setShowPreview={setShowPreview}
                    onContentChange={(val) => {
                        localContentRef.current = val;
                        setHasUnsavedChanges(true);
                    }}
                />
            </div>

            <div className="p-2 border-t flex justify-between items-center px-4 bg-zinc-50 dark:bg-slate-900/30">
                <div className="flex gap-4">
                    <button className="text-[10px] text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 flex items-center gap-1 transition-colors">
                        <History className="h-3 w-3" /> History
                    </button>
                    {(state.component === "markdown" || state.component === "document") && (
                        <button
                            onClick={() => setShowPreview(!showPreview)}
                            className={`text-[10px] flex items-center gap-1 transition-colors ${showPreview ? "text-indigo-600 dark:text-indigo-400" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"}`}
                        >
                            <Globe className="h-3 w-3" /> {showPreview ? "Edit Mode" : "Preview Mode"}
                        </button>
                    )}
                </div>
                {!hasUnsavedChanges && state.id && (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                        <Check className="h-3 w-3" /> Synced to cloud
                    </span>
                )}
            </div>
        </div>
    );
}

function CanvasIcon({ component }: { component: string }) {
    switch (component) {
        case "code": return <Code className="h-4 w-4 text-blue-500" />;
        case "email": return <Globe className="h-4 w-4 text-emerald-500" />;
        case "sheet": return <Layers className="h-4 w-4 text-amber-500" />;
        case "document": return <FileText className="h-4 w-4 text-indigo-500" />;
        case "snapshot": return <Camera className="h-4 w-4 text-purple-500" />;
        case "browser_view": return <Globe className="h-4 w-4 text-green-500" />;
        default: return <Layers className="h-4 w-4 text-indigo-500" />;
    }
}

function CanvasContent({
    component,
    data,
    emailMetadata,
    setEmailMetadata,
    sheetData,
    setSheetData,
    showPreview,
    setShowPreview,
    onContentChange
}: {
    component: string;
    data: any;
    emailMetadata: any;
    setEmailMetadata: (m: any) => void;
    sheetData: any[][];
    setSheetData: (d: any[][]) => void;
    showPreview: boolean;
    setShowPreview: (s: boolean) => void;
    onContentChange: (val: string) => void
}) {
    if (!data && component !== "sheet") return <div className="text-zinc-500 p-4">No data to display</div>;

    const content = typeof data === 'string' ? data : (data.content || JSON.stringify(data, null, 2));

    switch (component) {
        case "email":
            return (
                <div className="flex flex-col h-full bg-white dark:bg-[#0F172A]">
                    <div className="p-4 border-b border-zinc-100 dark:border-white/5 space-y-3 bg-zinc-50/50 dark:bg-black/20">
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 w-12 font-bold uppercase tracking-wider">To:</span>
                            <input
                                type="text"
                                value={emailMetadata.to}
                                onChange={(e) => setEmailMetadata({ ...emailMetadata, to: e.target.value })}
                                className="flex-1 bg-transparent border-none text-zinc-900 dark:text-zinc-200 text-sm focus:ring-0 placeholder:text-zinc-300"
                                placeholder="recipient@example.com"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 w-12 font-bold uppercase tracking-wider">Sub:</span>
                            <input
                                type="text"
                                value={emailMetadata.subject}
                                onChange={(e) => setEmailMetadata({ ...emailMetadata, subject: e.target.value })}
                                className="flex-1 bg-transparent border-none text-zinc-900 dark:text-zinc-200 text-sm font-semibold focus:ring-0 placeholder:text-zinc-300"
                                placeholder="Email Subject"
                            />
                        </div>
                    </div>
                    <div className="flex-1">
                        <Editor
                            height="100%"
                            defaultLanguage="markdown"
                            theme="vs-dark"
                            value={content}
                            onChange={(val) => onContentChange(val || "")}
                            options={{
                                minimap: { enabled: false },
                                fontSize: 13,
                                lineNumbers: "off",
                                wordWrap: "on",
                                padding: { top: 20, bottom: 20 }
                            }}
                        />
                    </div>
                </div>
            );

        case "sheet":
            return (
                <div className="h-full overflow-auto bg-white dark:bg-[#020617] p-1 custom-scrollbar">
                    <table className="w-full border-collapse text-[12px] text-zinc-900 dark:text-zinc-300">
                        <thead>
                            <tr>
                                <th className="w-8 border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-[10px] text-zinc-400 font-mono">#</th>
                                {sheetData[0]?.map((_, i) => (
                                    <th key={i} className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 font-bold uppercase tracking-wider">
                                        {String.fromCharCode(65 + i)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {sheetData.map((row, rowIndex) => (
                                <tr key={rowIndex}>
                                    <td className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-center text-[10px] text-zinc-400 font-mono italic">
                                        {rowIndex + 1}
                                    </td>
                                    {row.map((cell, cellIndex) => (
                                        <td
                                            key={cellIndex}
                                            className="border border-zinc-100 dark:border-white/10 p-1 min-w-[80px] hover:bg-zinc-50 dark:hover:bg-white/5 focus-within:bg-indigo-500/10 focus-within:border-indigo-500/50 transition-colors"
                                        >
                                            <input
                                                type="text"
                                                value={cell}
                                                onChange={(e) => {
                                                    const newData = [...sheetData];
                                                    newData[rowIndex][cellIndex] = e.target.value;
                                                    setSheetData(newData);
                                                }}
                                                className="w-full bg-transparent border-none p-0 focus:ring-0 outline-none"
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            {/* Add Row Button */}
                            <tr>
                                <td
                                    colSpan={sheetData[0]?.length + 1}
                                    className="p-1 border border-zinc-100 dark:border-white/5 text-center"
                                >
                                    <button
                                        onClick={() => setSheetData([...sheetData, Array(sheetData[0]?.length || 3).fill("")])}
                                        className="text-[10px] text-zinc-400 hover:text-indigo-600 uppercase font-bold tracking-widest transition-colors py-1 w-full"
                                    >
                                        + Add New Row
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            );

        case "markdown":
        case "document":
        case "code":
            if (showPreview && (component === "markdown" || component === "document")) {
                const htmlContent = marked.parse(content);
                return (
                    <div className="p-8 prose dark:prose-invert max-w-none text-sm leading-relaxed overflow-auto h-full custom-scrollbar bg-zinc-50/10 dark:bg-white/[0.02]">
                        <div dangerouslySetInnerHTML={{ __html: htmlContent as string }} />
                    </div>
                );
            }
            return (
                <Editor
                    height="100%"
                    defaultLanguage={component === "code" ? "javascript" : "markdown"}
                    theme="vs-dark"
                    value={content}
                    onChange={(val) => onContentChange(val || "")}
                    options={{
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 13,
                        lineNumbers: "on",
                        roundedSelection: false,
                        readOnly: false,
                        cursorStyle: "line",
                        automaticLayout: true
                    }}
                />
            );

        case "snapshot":
            return (
                <div className="space-y-4 p-4 overflow-auto h-full custom-scrollbar">
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
                    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden bg-white dark:bg-black/40">
                        <div className="p-2 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex justify-between items-center">
                            <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">State Tree</span>
                        </div>
                        <pre className="p-4 text-[11px] overflow-auto max-h-[400px] bg-zinc-50/50 dark:bg-transparent font-mono text-zinc-600 dark:text-zinc-400">
                            {JSON.stringify(data.state || data, null, 2)}
                        </pre>
                    </div>
                </div>
            );

        case "browser_view":
            return (
                <div className="space-y-4 p-4 overflow-auto h-full custom-scrollbar">
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
                <div className="p-6 border rounded-xl border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/20 flex flex-col items-center justify-center text-center m-4">
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

import { FileText } from "lucide-react";
