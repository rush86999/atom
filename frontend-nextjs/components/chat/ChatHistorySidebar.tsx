import React from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ScrollArea } from "../ui/scroll-area";
import { Search, MessageSquare, Plus, Clock } from "lucide-react";
import { cn } from "../../lib/utils";

interface ChatHistorySidebarProps {
    selectedSessionId: string | null;
    onSelectSession: (id: string) => void;
}

const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = ({ selectedSessionId, onSelectSession }) => {
    // Mock data - replace with API call
    const history = [
        { id: "1", title: "Project Planning", date: "Today", preview: "Let's outline the Q4 roadmap..." },
        { id: "2", title: "Debug Auth Issue", date: "Yesterday", preview: "I'm getting a 401 error on..." },
        { id: "3", title: "Generate Report", date: "Nov 28", preview: "Create a summary of sales..." },
        { id: "4", title: "Email Draft", date: "Nov 25", preview: "Draft an email to the team..." },
    ];

    return (
        <div className="flex flex-col h-full border-r border-border">
            <div className="p-4 border-b border-border space-y-4">
                <Button className="w-full justify-start gap-2" variant="default">
                    <Plus className="h-4 w-4" /> New Chat
                </Button>
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input placeholder="Search chats..." className="pl-8" />
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                    {history.map((session) => (
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
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
};

export default ChatHistorySidebar;
