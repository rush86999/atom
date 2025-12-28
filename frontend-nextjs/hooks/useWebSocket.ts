import { useState, useEffect, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";

interface WebSocketMessage {
    type: string;
    data?: any;
    workspace_id?: string;
    timestamp?: string;
}

interface UseWebSocketOptions {
    url?: string;
    autoConnect?: boolean;
    initialChannels?: string[];
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
    const { data: session } = useSession();
    const {
        url = "ws://localhost:8000/ws",
        autoConnect = true,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        // @ts-ignore
        const token = session?.backendToken || (session as any)?.accessToken;
        if (!token) return;

        // Native WebSocket Connection URL construction
        const wsUrl = (process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'http://localhost:8000').replace('http', 'ws');
        const socketUrl = `${wsUrl}/ws?token=${token}`;

        const ws = new WebSocket(socketUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket Connected");
            setIsConnected(true);

            // Re-subscribe to channels if any
            if (options.initialChannels) {
                options.initialChannels.forEach(channel => {
                    ws.send(JSON.stringify({ type: "subscribe", channel }));
                });
            }
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                setLastMessage(message);
            } catch (e) {
                console.error("Failed to parse WebSocket message", e);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected");
            setIsConnected(false);
            // Attempt reconnect logic could go here
        };

        ws.onerror = (error) => {
            console.error("WebSocket Error:", error);
        };
    }, [url, session, options.initialChannels]);

    const disconnect = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const subscribe = useCallback((channel: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "subscribe", channel }));
        }
    }, []);

    const unsubscribe = useCallback((channel: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
        }
    }, []);

    useEffect(() => {
        if (autoConnect && session) {
            connect();
        }
        return () => disconnect();
    }, [autoConnect, connect, disconnect, session]);

    return {
        isConnected,
        lastMessage,
        subscribe,
        unsubscribe,
        sendMessage: (msg: any) => wsRef.current?.send(JSON.stringify(msg)),
    };
};
