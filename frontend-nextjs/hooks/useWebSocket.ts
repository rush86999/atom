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

    // Use deep comparison key for channels array to avoid ref instability
    const channelKey = JSON.stringify(options.initialChannels || []);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        // Dev Token Fallback: If no session, check if we are in dev/local
        // @ts-ignore
        let token = session?.backendToken || (session as any)?.accessToken;

        // Auto-use dev token if no session is present (for simple local testing)
        if (!token) {
            token = "dev-token";
        }

        // Bypass Next.js Proxy for WebSockets (it doesn't support WS upgrading well)
        // Always connect directly to Backend port 8000 in development
        const socketUrl = `ws://localhost:8000/ws?token=${token}`;

        // Only log connection attempts if not already connecting
        // if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        //     console.log("[useWebSocket] Connecting to:", socketUrl);
        // }

        const ws = new WebSocket(socketUrl);
        wsRef.current = ws;

        ws.onopen = () => {
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
                // Silent catch
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            wsRef.current = null;
        };

        ws.onerror = (error) => {
            // Silent error or toast? For now silent.
        };
    }, [url, session, channelKey]); // Use channelKey instead of array ref

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
        if (autoConnect) {
            connect();
        }
        return () => disconnect();
    }, [autoConnect, connect, disconnect]);

    return {
        isConnected,
        lastMessage,
        subscribe,
        unsubscribe,
        sendMessage: (msg: any) => wsRef.current?.send(JSON.stringify(msg)),
    };
};
