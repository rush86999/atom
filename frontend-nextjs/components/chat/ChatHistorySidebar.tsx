import React, { useState, useEffect } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ScrollArea } from "../ui/scroll-area";
import { Search, MessageSquare, Plus, Clock } from "lucide-react";
import { cn } from "../../lib/utils";

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
            const response = await fetch("/api/atom-agent/sessions");
            if (!response.ok) {
                throw new Error("Failed to fetch chat history");
            }
            const data = await response.json();
            if (data.success && data.sessions) {
                setHistory(data.sessions);
            }
        } catch (error) {
            console.error("Error fetching chat history:", error);
            setHistory([]);
        } finally {
            setLoading(false);
        }
    };

    const handleNewChat = async () => {
        try {
            setLoading(true);
            const response = await fetch("/api/atom-agent/sessions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "default_user" })
            });
            const data = await response.json();
            if (data.success && data.session_id) {
                onSelectSession(data.session_id);
                fetchChatHistory();
            }
        } catch (error) {
            console.error("Error creating new chat:", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredHistory = history.filter(session =>
        session.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        session.preview.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full border-r border-border">
            <div className="p-4 border-b border-border space-y-4">
                <Button className="w-full justify-start gap-2" variant="default" onClick={handleNewChat}>
                    <Plus className="h-4 w-4" /> New Chat
                </Button>
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search chats..."
                        className="pl-8"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                    {loading ? (
                        <div className="p-4 text-center text-muted-foreground">
                            Loading chat history...
                        </div>
                    ) : filteredHistory.length === 0 ? (
                        <div className="p-4 text-center text-muted-foreground">
                            {searchQuery ? "No chats found matching your search." : "No chat history yet."}
                        </div>
                    ) : (
                        filteredHistory.map((session) => (
                            <div
                                key={session.id}
                                onClick={() => onSelectSession(session.id)}
                                className={cn(
                                    "flex flex-col gap-1 p-3 rounded-lg cursor-pointer transition-colors hover:bg-accent",
                                    selectedSessionId === session.id ? "bg-accent" : ""
                                )}
                            >
                                <div className="flex items-center justify-between">
                                    <span className="font-medium text-sm truncate">{session.title}</span>
                                    <span className="text-xs text-muted-foreground">{session.date}</span>
                                </div>
                                <p className="text-xs text-muted-foreground truncate">{session.preview}</p>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};

export default ChatHistorySidebar;
