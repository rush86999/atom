import { useState, useEffect } from 'react';
import { Message } from '@/components/shared/CommunicationHub';

// Raw response from API
interface RawUnifiedMessage {
    id: string;
    content: string;
    sender: string;
    timestamp: string;
    provider: 'slack' | 'gmail' | 'discord' | 'teams' | 'zoho' | 'outlook';
    status: 'read' | 'unread';
    metadata?: any;
}

interface LiveInboxResponse {
    ok: boolean;
    count: number;
    messages: RawUnifiedMessage[];
    providers: Record<string, boolean>;
}

export function useLiveCommunication() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeProviders, setActiveProviders] = useState<Record<string, boolean>>({});

    const fetchLiveInbox = async () => {
        try {
            const res = await fetch('/api/atom/communication/live/inbox?limit=50');
            if (res.ok) {
                const data: LiveInboxResponse = await res.json();

                // Map Raw API Data to UI Message Model
                const uiMessages: Message[] = data.messages.map(raw => ({
                    id: raw.id,
                    platform: raw.provider === 'gmail' ? 'email' : (raw.provider as any), // Map 'gmail' -> 'email'
                    from: raw.sender,       // backend 'sender' -> frontend 'from'
                    subject: raw.provider === 'slack' || raw.provider === 'discord' ? 'Message' : 'No Subject', // Default subject
                    preview: raw.content.substring(0, 100),
                    content: raw.content,
                    timestamp: new Date(raw.timestamp), // String to Date
                    unread: raw.status === 'unread',
                    priority: 'normal',
                    status: 'received'
                }));

                setMessages(uiMessages);
                setActiveProviders(data.providers);
            }
        } catch (error) {
            console.error("Failed to fetch live inbox:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLiveInbox();

        // Optional: Poll every 30s
        const interval = setInterval(fetchLiveInbox, 30000);
        return () => clearInterval(interval);
    }, []);

    return {
        messages,
        isLoading,
        activeProviders,
        refresh: fetchLiveInbox
    };
}
