import React, { useState, useEffect, useRef } from 'react';
import { Send, Paperclip, MoreVertical } from 'lucide-react';

interface Message {
    id: string;
    team_id: string;
    user_id: string;
    sender_name: string;
    content: string;
    context_type?: string;
    context_id?: string;
    created_at: string;
}

interface TeamChatPanelProps {
    teamId: string;
    contextType?: string;
    contextId?: string;
    className?: string;
}

export default function TeamChatPanel({
    teamId,
    contextType,
    contextId,
    className = ''
}: TeamChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [newMessage, setNewMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Load message history
    useEffect(() => {
        const loadMessages = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                if (!token) return;

                let url = `/api/teams/${teamId}/messages?limit=50`;
                if (contextType) url += `&context_type=${contextType}`;
                if (contextId) url += `&context_id=${contextId}`;

                const response = await fetch(url, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    setMessages(data.reverse());
                }
            } catch (error) {
                console.error('Failed to load messages:', error);
            } finally {
                setLoading(false);
            }
        };

        loadMessages();
    }, [teamId, contextType, contextId]);

    // WebSocket connection
    useEffect(() => {
        const token = localStorage.getItem('auth_token');
        if (!token) return;

        const ws = new WebSocket(`ws://localhost:5061/ws?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log('WebSocket connected');
            // Subscribe to team channel
            ws.send(JSON.stringify({
                type: 'subscribe',
                channel: `team:${teamId}`
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'message.received') {
                const msg = data.data;
                // Only add if it matches our context filter (or no filter)
                if (!contextType || (msg.context_type === contextType && msg.context_id === contextId)) {
                    setMessages(prev => [...prev, msg]);
                }
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
        };

        return () => {
            ws.close();
        };
    }, [teamId, contextType, contextId]);

    const sendMessage = async () => {
        if (!newMessage.trim()) return;

        try {
            const token = localStorage.getItem('auth_token');
            if (!token) return;

            const response = await fetch(`/api/teams/${teamId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    content: newMessage,
                    context_type: contextType,
                    context_id: contextId
                })
            });

            if (response.ok) {
                setNewMessage('');
            }
        } catch (error) {
            console.error('Failed to send message:', error);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className={`flex flex-col h-full bg-white dark:bg-gray-900 rounded-lg shadow-lg ${className}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Team Chat
                    </h3>
                    {contextType && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            Discussing: {contextType} #{contextId}
                        </p>
                    )}
                </div>
                <button className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                    <MoreVertical className="w-5 h-5 text-gray-500" />
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {loading ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : messages.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
                        No messages yet. Start the conversation!
                    </div>
                ) : (
                    messages.map((msg) => (
                        <div key={msg.id} className="flex items-start space-x-3">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-semibold">
                                {msg.sender_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                            </div>
                            <div className="flex-1">
                                <div className="flex items-baseline space-x-2">
                                    <span className="font-semibold text-gray-900 dark:text-white">
                                        {msg.sender_name}
                                    </span>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {new Date(msg.created_at).toLocaleTimeString()}
                                    </span>
                                </div>
                                <div className="mt-1 text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                                    {msg.content}
                                </div>
                            </div>
                        </div>
                    ))
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-end space-x-2">
                    <button className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                        <Paperclip className="w-5 h-5 text-gray-500" />
                    </button>
                    <div className="flex-1 relative">
                        <textarea
                            value={newMessage}
                            onChange={(e) => setNewMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Type a message..."
                            rows={1}
                            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white resize-none"
                        />
                    </div>
                    <button
                        onClick={sendMessage}
                        disabled={!newMessage.trim()}
                        className="p-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
