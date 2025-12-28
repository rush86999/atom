import React, { useState, useEffect, useRef } from 'react';
import { Send, MessageSquare } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ChatMessage, ChatMessageData, ChatAction } from '@/components/GlobalChat/ChatMessage';
import { useToast } from '@/components/ui/use-toast';

interface Message {
    id: string;
    sender: string;
    senderType: 'user' | 'agent';
    content: string;
    timestamp: string;
}

interface CommentSectionProps {
    channel: string;
    title?: string;
}

export const CommentSection: React.FC<CommentSectionProps> = ({ channel, title = "Team Discussion" }) => {
    const { data: session } = useSession();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [ws, setWs] = useState<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const { toast } = useToast();

    useEffect(() => {
        // Determine WebSocket URL based on current environment
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
        // In a real app, token would be fetched from auth context
        const token = 'demo-token';
        const socket = new WebSocket(`${protocol}//${host}/ws?token=${token}`);

        socket.onopen = () => {
            console.log(`Connected to WebSocket for channel: ${channel}`);
            socket.send(JSON.stringify({ type: 'subscribe', channel }));
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'comment' || data.type === 'message') {
                setMessages(prev => [...prev, {
                    id: data.id || Date.now().toString(),
                    sender: data.sender || 'System',
                    senderType: data.senderType || 'user',
                    content: data.content,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }]);
            }
        };

        setWs(socket);

        // Initial mock messages
        setMessages([
            { id: '1', sender: 'System Agent', senderType: 'agent', content: `Welcome to the ${channel} discussion.`, timestamp: '10:00 AM' },
            { id: '2', sender: 'Atom Agent', senderType: 'agent', content: `I'm monitoring this channel for any automated tasks.`, timestamp: '10:05 AM' },
            { id: '3', sender: 'Finance Analyst', senderType: 'agent', content: `I noticed a discrepancy in the Q3 report. Shall I flag it?`, timestamp: '10:12 AM' }
        ]);

        return () => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'unsubscribe', channel }));
                socket.close();
            }
        };
    }, [channel]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = () => {
        if (!input.trim() || !ws) return;

        const newMessage = {
            type: 'comment',
            channel,
            content: input,
            sender: session?.user?.name || 'User', // In real app, from auth
            senderType: 'user'
        };

        ws.send(JSON.stringify(newMessage));

        // Optimistic UI update
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            sender: session?.user?.name || 'User',
            senderType: 'user',
            content: input,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);

        setInput('');
    };

    const handleFeedback = async (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => {
        try {
            toast({
                title: comment ? "Correction Received" : (type === 'thumbs_up' ? "Helpful" : "Flagged"),
                description: comment ? "We'll use this to improve our reasoning." : "Thanks for your feedback!",
            });

            const originalMessage = messages.find(m => m.id === messageId);
            const originalContent = originalMessage?.content;
            const senderName = originalMessage?.sender.toLowerCase() || "";

            // Intelligent mapping of agent names to IDs for backend governance
            let agentId = "team_agent_generic";
            if (senderName.includes("atom")) agentId = "atom_meta_agent";
            else if (senderName.includes("finance")) agentId = "finance_specialist";
            else if (senderName.includes("sales")) agentId = "sales_specialist";
            else if (senderName.includes("analyst")) agentId = "data_analyst";
            else if (senderName.includes("legal")) agentId = "legal_specialist";

            await fetch('/api/reasoning/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: agentId,
                    run_id: `team-chat-${channel}-${Date.now()}`, // creating a synthetic run ID
                    step_index: -1,
                    step_content: {
                        thought: `Team Discussion Message in ${channel}`,
                        output: originalContent,
                        context: { channel, sender: originalMessage?.sender }
                    },
                    feedback_type: type,
                    comment: comment
                })
            });
        } catch (e) {
            console.error("Feedback failed", e);
            toast({
                title: "Error",
                description: "Failed to submit feedback",
                variant: "error"
            });
        }
    };

    const handleActionClick = (action: ChatAction) => {
        console.log("Action clicked in comment section:", action);
    };

    return (
        <div className="flex flex-col h-full bg-black/40 border border-white/5 backdrop-blur-xl rounded-xl overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-white/5 bg-white/5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-primary" />
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">{title}</h3>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[10px] text-muted-foreground uppercase font-semibold">Live</span>
                </div>
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide"
            >
                {messages.map((msg) => {
                    // Convert local Message format to ChatMessageData
                    const chatMessage: ChatMessageData = {
                        id: msg.id,
                        type: msg.senderType === 'agent' ? 'assistant' : 'user',
                        content: msg.content,
                        timestamp: new Date(), // using current date for display as the string timestamp is just time
                    };

                    return (
                        <div key={msg.id} className={cn(
                            "flex flex-col",
                            msg.senderType === 'user' ? "items-end" : "items-start"
                        )}>
                            {msg.senderType === 'agent' && (
                                <span className="text-[10px] text-muted-foreground ml-10 mb-1">{msg.sender}</span>
                            )}
                            <ChatMessage
                                message={chatMessage}
                                onActionClick={handleActionClick}
                                onFeedback={msg.senderType === 'agent' ? handleFeedback : undefined}
                            />
                        </div>
                    );
                })}
            </div>

            <div className="p-4 border-t border-white/5 bg-black/20">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder={`Discuss ${channel}...`}
                        className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-white placeholder:text-muted-foreground"
                    />
                    <Button
                        size="icon"
                        onClick={handleSend}
                        disabled={!input.trim()}
                        className="rounded-xl shadow-lg shadow-primary/20 hover:scale-105 active:scale-95 transition-transform"
                    >
                        <Send className="w-4 h-4" />
                    </Button>
                </div>
            </div>
        </div>
    );
};
