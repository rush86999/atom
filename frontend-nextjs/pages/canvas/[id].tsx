"use client";

import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Send, ArrowLeft, RefreshCw, History, Trash2 } from "lucide-react";
import { CanvasPanel } from "@/components/canvas/CanvasPanel";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useCanvasStateRegistration } from "@/hooks/useCanvasStateRegistration";
import Layout from "@/components/layout/Layout";

interface CanvasMessage {
    id: string;
    type: "user" | "assistant" | "system";
    content: string;
    timestamp: Date;
}

export default function CanvasDetailPage() {
    const router = useRouter();
    const { id: canvasId } = router.query;
    const userId = typeof window !== "undefined" ? (localStorage.getItem("user_id") || "default_user") : "default_user";

    // Canvas state
    const [canvasData, setCanvasData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [showHistory, setShowHistory] = useState(false);
    const [history, setHistory] = useState<any[]>([]);

    // Chat panel state
    const [messages, setMessages] = useState<CanvasMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [isAgentResponding, setIsAgentResponding] = useState(false);

    // WebSocket — page-agnostic, auto-subscribes to user:{userId}
    const { lastMessage, isConnected } = useWebSocket({});

    // Register canvas state for AI accessibility
    const canvasState = canvasData ? {
        type: canvasData.canvas_type || "generic",
        component: canvasData.canvas_type || "generic",
        title: canvasData.title || canvasId as string,
        data: canvasData.content,
    } : null;
    useCanvasStateRegistration(canvasId as string, canvasState as any);

    // Load canvas content by ID
    const loadCanvas = useCallback(async () => {
        if (!canvasId) return;
        try {
            const { apiClient } = await import("../../lib/api-client");
            const resp = await apiClient.get(`/api/canvas/${canvasId}`);
            const data = (resp as any).data || resp;
            if (data.success !== false) {
                setCanvasData(data);
            }
        } catch (e) {
            console.error("Failed to load canvas:", e);
        } finally {
            setLoading(false);
        }
    }, [canvasId]);

    useEffect(() => {
        loadCanvas();
    }, [loadCanvas]);

    // Listen for live canvas updates via WebSocket
    useEffect(() => {
        if (!lastMessage) return;
        const msg = typeof lastMessage === "string" ? JSON.parse(lastMessage) : lastMessage;
        if (msg.type === "canvas:update" || msg.type === "canvas:present") {
            const data = msg.data || msg;
            if (data.canvas_id === canvasId && data.action !== "close") {
                setCanvasData((prev: any) => ({
                    ...prev,
                    content: data.data || data.content,
                    title: data.title || prev?.title,
                    canvas_type: data.component || data.canvas_type || prev?.canvas_type,
                }));
            }
            if (data.action === "close" && data.canvas_id === canvasId) {
                setCanvasData(null);
            }
        }
    }, [lastMessage, canvasId]);

    // Load version history
    const loadHistory = async () => {
        if (!canvasId) return;
        try {
            const { apiClient } = await import("../../lib/api-client");
            const resp = await apiClient.get(`/api/canvas/${canvasId}/history`);
            const data = (resp as any).data || resp;
            setHistory(data.history || []);
            setShowHistory(!showHistory);
        } catch (e) {
            console.error("Failed to load history:", e);
        }
    };

    // Delete canvas
    const handleDelete = async () => {
        if (!canvasId) return;
        if (!confirm("Delete this canvas? The audit history is preserved.")) return;
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.delete(`/api/canvas/${canvasId}`);
            router.push("/canvas");
        } catch (e) {
            console.error("Delete failed:", e);
        }
    };

    // Send message to agent about this canvas
    const handleSendMessage = async () => {
        if (!chatInput.trim()) return;
        const userMsg: CanvasMessage = {
            id: `u_${Date.now()}`,
            type: "user",
            content: chatInput,
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, userMsg]);
        setChatInput("");
        setIsAgentResponding(true);

        try {
            const { apiClient } = await import("../../lib/api-client");
            const resp = await apiClient.post("/api/chat/message", {
                message: chatInput,
                user_id: userId,
                session_id: "new",
                context: {
                    current_page: `/canvas/${canvasId}`,
                    canvas_id: canvasId,
                    canvas_type: canvasData?.canvas_type,
                    canvas_content: canvasData?.content,
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content,
                    })),
                },
            });
            const data = (resp as any).data || resp;
            if (data.success && data.message) {
                setMessages(prev => [...prev, {
                    id: `a_${Date.now()}`,
                    type: "assistant",
                    content: data.message,
                    timestamp: new Date(),
                }]);
            } else if (data.error_code === "no_llm_provider") {
                setMessages(prev => [...prev, {
                    id: "sys",
                    type: "system",
                    content: "⚠️ No AI provider configured. Add an API key in Settings.",
                    timestamp: new Date(),
                }]);
            }
        } catch (e) {
            setMessages(prev => [...prev, {
                id: "err",
                type: "system",
                content: "⚠️ Could not reach the agent. Please try again.",
                timestamp: new Date(),
            }]);
        } finally {
            setIsAgentResponding(false);
        }
    };

    const canvasLastMessage = canvasData ? {
        type: "canvas:update",
        data: {
            action: "present",
            component: canvasData.canvas_type || "markdown",
            canvas_id: canvasId,
            data: canvasData.content,
            title: canvasData.title,
        },
    } : lastMessage;

    return (
        <Layout>
            <Head>
                <title>{canvasData?.title || "Canvas"} | Atom</title>
            </Head>
            <div className="h-[calc(100vh-3.5rem)] flex flex-col">
                {/* Canvas header bar */}
                <div className="flex items-center justify-between border-b px-4 py-2 shrink-0">
                    <div className="flex items-center gap-3">
                        <Link href="/canvas">
                            <Button variant="ghost" size="sm">
                                <ArrowLeft className="h-4 w-4 mr-1" /> All Canvases
                            </Button>
                        </Link>
                        <h1 className="text-lg font-semibold truncate max-w-xs md:max-w-md">
                            {canvasData?.title || `Canvas ${canvasId}`}
                        </h1>
                        {canvasData?.canvas_type && (
                            <span className="text-[10px] uppercase bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                                {canvasData.canvas_type}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={loadCanvas} title="Refresh">
                            <RefreshCw className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={loadHistory} title="Version history">
                            <History className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={handleDelete} title="Delete">
                            <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                    </div>
                </div>

                {/* Main content: canvas + side chat */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Canvas panel (left/center, takes most space) */}
                    <div className="flex-1 overflow-hidden">
                        {loading ? (
                            <div className="flex items-center justify-center h-full">
                                <p className="text-muted-foreground">Loading canvas…</p>
                            </div>
                        ) : canvasData ? (
                            <CanvasPanel lastMessage={canvasLastMessage} />
                        ) : (
                            <div className="flex items-center justify-center h-full">
                                <Card className="max-w-md text-center">
                                    <CardContent className="pt-6">
                                        <p className="text-muted-foreground mb-4">Canvas not found or deleted.</p>
                                        <Link href="/canvas"><Button>Browse Canvases</Button></Link>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </div>

                    {/* Side chat panel (right, collapsible) */}
                    <div className="w-80 border-l flex flex-col bg-muted/30 shrink-0">
                        {/* Chat header */}
                        <div className="px-3 py-2 border-b bg-background/50 shrink-0">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-green-500" title={isConnected ? "Connected" : "Disconnected"} />
                                <span className="text-sm font-medium">Agent Co-Editor</span>
                            </div>
                            <p className="text-[10px] text-muted-foreground mt-0.5">
                                Chat with the agent while editing this canvas
                            </p>
                        </div>

                        {/* Chat messages */}
                        <div className="flex-1 overflow-y-auto p-3 space-y-3">
                            {messages.length === 0 && (
                                <div className="text-center text-muted-foreground text-sm py-8">
                                    <p className="mb-2">💬 Ask the agent to modify this canvas</p>
                                    <p className="text-xs">e.g. "Add a new row to the spreadsheet" or "Change the chart to a bar chart"</p>
                                </div>
                            )}
                            {messages.map(msg => (
                                <div key={msg.id} className={`text-sm ${msg.type === "user" ? "text-right" : ""}`}>
                                    <div className={`inline-block max-w-[85%] px-3 py-2 rounded-lg ${
                                        msg.type === "user"
                                            ? "bg-primary text-primary-foreground"
                                            : msg.type === "system"
                                            ? "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200"
                                            : "bg-background border"
                                    }`}>
                                        {msg.content}
                                    </div>
                                </div>
                            ))}
                            {isAgentResponding && (
                                <div className="text-sm text-muted-foreground">
                                    <span className="animate-pulse">●●● Agent is working…</span>
                                </div>
                            )}
                        </div>

                        {/* Chat input */}
                        <div className="p-3 border-t shrink-0">
                            <div className="flex gap-2">
                                <Input
                                    value={chatInput}
                                    onChange={(e: any) => setChatInput(e.target.value)}
                                    onKeyDown={(e: any) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSendMessage())}
                                    placeholder="Ask the agent to edit…"
                                    disabled={isAgentResponding}
                                    className="text-sm"
                                />
                                <Button size="icon" onClick={handleSendMessage} disabled={isAgentResponding || !chatInput.trim()}>
                                    <Send className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Version history slide-out */}
                {showHistory && (
                    <div className="absolute right-80 top-12 bottom-0 w-64 bg-background border-l shadow-lg z-10 overflow-y-auto">
                        <div className="p-3 border-b flex justify-between items-center">
                            <h3 className="text-sm font-semibold">Version History</h3>
                            <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>
                                <ArrowLeft className="h-3 w-3" />
                            </Button>
                        </div>
                        <div className="divide-y">
                            {history.length === 0 ? (
                                <p className="text-sm text-muted-foreground p-4">No history available.</p>
                            ) : (
                                history.map((h, i) => (
                                    <div key={i} className="p-3 text-xs">
                                        <div className="flex justify-between mb-1">
                                            <span className="font-medium uppercase">{h.action_type}</span>
                                            <span className="text-muted-foreground">
                                                {h.created_at ? new Date(h.created_at).toLocaleString() : ""}
                                            </span>
                                        </div>
                                        <span className="text-muted-foreground">{h.canvas_type}</span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>
        </Layout>
    );
}
