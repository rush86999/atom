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
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
    const { data: session } = useSession();
    const {
        url = "ws://localhost:5059/ws",
        autoConnect = true,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        // In a production app, we'd get the token from the session
        // For this environment, we'll use a dummy token or try to extract it
        const token = (session as any)?.accessToken || "demo-token";
        const socketUrl = `${url}?token=${token}`;

        const ws = new WebSocket(socketUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket Connected");
            setIsConnected(true);
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
        };

        ws.onerror = (error) => {
            console.error("WebSocket Error:", error);
        };
    }, [url, session]);

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

    useEffect(() => {
        if (autoConnect) {
            connect();
        }
        return () => disconnect();
    }, [autoConnect, connect, disconnect]);

    return {
        isConnected,
        lastMessage,
        subscribe,
        sendMessage: (msg: any) => wsRef.current?.send(JSON.stringify(msg)),
    };
};
