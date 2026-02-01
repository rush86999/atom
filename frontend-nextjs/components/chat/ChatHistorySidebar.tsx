'use client';

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatSession {
    id: string;
    title: string;
    date: string;
    preview: string;
}

interface ChatHistorySidebarProps {
    selectedSessionId: string | null;
    onSelectSession: (id: string) => void;
}

const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = ({ selectedSessionId, onSelectSession }) => {
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    useEffect(() => {
        fetchChatHistory();
    }, []);

    const fetchChatHistory = async () => {
        try {
            setLoading(true);
            const { apiClient } = await import('../../lib/api-client');
            // Use correct backend endpoint for sessions
            const response = await apiClient.get("/api/chat/sessions?user_id=default_user") as any;
            if (response.status !== 200) {
                throw new Error("Failed to fetch chat history");
            }
            const data = response.data;
            // Backend can return sessions as array OR dict
            let sessionsArray: any[] = [];
            if (data.sessions) {
                if (Array.isArray(data.sessions)) {
                    sessionsArray = data.sessions;
                } else if (typeof data.sessions === 'object') {
                    // Convert dict {session_id: {...}} to array
                    sessionsArray = Object.keys(data.sessions).map(key => ({
                        session_id: key,
                        ...data.sessions[key]
                    }));
                }
            }

            if (sessionsArray.length > 0) {
                // Filter out sessions with ID "new" - it conflicts with the new chat sentinel value
                const validSessions = sessionsArray.filter((s: any) => {
                    const id = s.session_id || s.id;
                    return id && id !== "new";
                });

                setHistory(validSessions.map((s: any) => {
                    // Get last message from history array if available
                    const lastHistoryItem = s.history && s.history.length > 0
                        ? s.history[s.history.length - 1]
                        : null;
                    const lastMessage = lastHistoryItem?.message || lastHistoryItem?.response?.message || "";
                    const messageCount = s.history?.length || s.message_count || 0;

                    // Handle different date field names
                    const dateStr = s.last_updated || s.last_active || s.created_at;

                    return {
                        id: s.session_id || s.id,
                        title: s.title || (lastMessage ? lastMessage.substring(0, 40) + "..." : "Untitled Chat"),
                        date: dateStr ? new Date(dateStr).toLocaleDateString() : "Unknown",
                        preview: lastMessage ? lastMessage.substring(0, 50) : `${messageCount} messages`
                    };
                }));
            } else {
                setHistory([]);
            }
        } catch (error) {
            console.error("Error fetching chat history:", error);
            setHistory([]);
        } finally {
            setLoading(false);
        }
    };

    const handleNewChat = () => {
        onSelectSession("new");
    };

    const filteredHistory = history.filter(session =>
        session.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        session.preview.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full border-r border-slate-800 bg-[#0F172A]">
            <div className="p-4 border-b border-slate-800 space-y-4">
                <Button className="w-full justify-start gap-2 bg-indigo-600 hover:bg-indigo-700" onClick={handleNewChat}>
                    <Plus className="h-4 w-4" /> New Chat
                </Button>
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-slate-500" />
                    <Input
                        placeholder="Search chats..."
                        className="pl-8 bg-slate-900 border-slate-700 text-slate-200"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                    {loading ? (
                        <div className="p-4 text-center text-slate-500 text-sm">
                            Loading history...
                        </div>
                    ) : filteredHistory.length === 0 ? (
                        <div className="p-4 text-center text-slate-500 text-sm">
                            {searchQuery ? "No matches found." : "No chat history."}
                        </div>
                    ) : (
                        filteredHistory.map((session) => (
                            <div
                                key={session.id}
                                onClick={() => onSelectSession(session.id)}
                                className={cn(
                                    "flex flex-col gap-1 p-3 rounded-xl cursor-pointer transition-all hover:bg-slate-800/50",
                                    selectedSessionId === session.id ? "bg-slate-800 border border-indigo-500/30 shadow-lg shadow-indigo-500/5" : "border border-transparent"
                                )}
                            >
                                <div className="flex items-center justify-between">
                                    <span className={`font-medium text-sm truncate ${selectedSessionId === session.id ? 'text-indigo-300' : 'text-slate-200'}`}>{session.title}</span>
                                    <span className="text-[10px] text-slate-500">{session.date}</span>
                                </div>
                                <p className="text-xs text-slate-400 truncate opacity-60">{session.preview}</p>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};

export default ChatHistorySidebar;
