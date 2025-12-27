import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Hash, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

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
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [ws, setWs] = useState<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Determine WebSocket URL based on current environment
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' ? 'localhost:5059' : window.location.host;
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
            { id: '1', sender: 'Rushi Parikh', senderType: 'user', content: `Welcome to the ${channel} discussion.`, timestamp: '10:00 AM' },
            { id: '2', sender: 'Atom Agent', senderType: 'agent', content: `I'm monitoring this channel for any automated tasks.`, timestamp: '10:05 AM' }
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
            sender: 'Rushi Parikh', // In real app, from auth
            senderType: 'user'
        };

        ws.send(JSON.stringify(newMessage));

        // Optimistic UI update
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            sender: 'Rushi Parikh',
            senderType: 'user',
            content: input,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);

        setInput('');
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
                {messages.map((msg) => (
                    <div key={msg.id} className={cn(
                        "flex flex-col gap-1 max-w-[85%]",
                        msg.senderType === 'agent' ? "mr-auto" : "ml-auto items-end"
                    )}>
                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-medium uppercase px-1">
                            {msg.senderType === 'agent' ? <Bot className="w-3 h-3 text-primary" /> : <User className="w-3 h-3" />}
                            {msg.sender} • {msg.timestamp}
                        </div>
                        <div className={cn(
                            "p-3 rounded-2xl text-sm shadow-sm",
                            msg.senderType === 'agent'
                                ? "bg-white/5 text-white rounded-tl-none border border-white/5"
                                : "bg-primary text-primary-foreground rounded-tr-none shadow-primary/20"
                        )}>
                            {msg.content}
                        </div>
                    </div>
                ))}
            </div>

            <div className="p-4 border-t border-white/5 bg-black/20">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder={`Discuess ${channel}...`}
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
