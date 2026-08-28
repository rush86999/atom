import { useState, useEffect, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";

interface WebSocketMessage {
    type: string;
    data?: any;
    workspace_id?: string;
    timestamp?: string;
    // Flat fields some emitters broadcast without the `data` wrapper
    // (e.g. agent_routes task streaming sends agent_id/step at top level).
    agent_id?: string;
    status?: string;
    session_id?: string;
    execution_id?: string;
    step?: any;
}

interface UseWebSocketOptions {
    url?: string;
    autoConnect?: boolean;
    initialChannels?: string[];
    /** Enable automatic reconnection with exponential backoff (default: true). */
    reconnect?: boolean;
    /** Max reconnect attempts before giving up (default: 3). */
    maxReconnectAttempts?: number;
    /** Initial reconnect delay in ms; doubles each attempt, capped at 10s (default: 1000). */
    reconnectDelay?: number;
}

// Close codes that should NOT trigger a reconnect — they are terminal and
// retrying would either loop on an immutable failure (auth) or violate a
// policy decision. Auth (4001) recovery is handled by the session-driven
// effect (NextAuth refreshes the token → connect() re-runs).
const TERMINAL_CLOSE_CODES = new Set([4001, 1008]);
const RECONNECT_MAX_DELAY_MS = 10000;

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
    const { data: session } = useSession();
    const {
        url = "",  // Empty default — uses resolveWsBase() derived from NEXT_PUBLIC_API_URL.
                    // Previously hardcoded "ws://localhost:8000/ws" which bypassed
                    // resolveWsBase() and broke WebSocket in non-localhost deploys.
        autoConnect = true,
        reconnect = true,
        maxReconnectAttempts = 3,
        reconnectDelay = 1000,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [streamingContent, setStreamingContent] = useState<Map<string, string>>(new Map());
    const wsRef = useRef<WebSocket | null>(null);

    // Reconnect bookkeeping. These are REFS (not state) so the setTimeout
    // callback reads live values — avoiding the stale-closure bug seen in
    // useWhatsAppWebSocket.ts where the counter was captured from a prior render.
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectAttemptsRef = useRef<number>(0);
    // Tracks whether the close was intentional (disconnect() / unmount) so the
    // onclose handler doesn't kick off a reconnect loop for a deliberate teardown.
    const manualCloseRef = useRef<boolean>(false);

    // Use deep comparison key for channels array to avoid ref instability
    const channelKey = JSON.stringify(options.initialChannels || []);

    // Derive the default WebSocket host from NEXT_PUBLIC_API_URL so the client
    // talks to the same backend the REST API uses (and respects wss in prod).
    const resolveWsBase = (): string => {
        const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
        return apiBase.replace(/^http/, "ws"); // http:// -> ws://, https:// -> wss://
    };

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        // A fresh connect() is an auto-connect unless disconnect() sets this
        // again immediately before. Reset so the onclose handler treats the
        // next close as a candidate for reconnect.
        manualCloseRef.current = false;

        // Resolve JWT token: check localStorage first (set by login page),
        // then fall back to NextAuth session.
        let token = session?.backendToken || (session as any)?.accessToken;

        // Check localStorage for auth_token (written by pages/login.tsx)
        if (!token && typeof window !== "undefined") {
            token = localStorage.getItem("auth_token") || undefined;
        }

        if (!token) {
            console.warn("[useWebSocket] No auth token found — skipping connection");
            return;
        }

        const wsBase = resolveWsBase();
        let socketUrl = `${wsBase}/ws`;
        if (url) {
            if (url.startsWith("ws://") || url.startsWith("wss://")) {
                socketUrl = url;
            } else {
                socketUrl = `${wsBase}${url.startsWith("/") ? "" : "/"}${url}`;
            }
        }

        const hasParams = socketUrl.includes("?");
        socketUrl = `${socketUrl}${hasParams ? "&" : "?"}token=${token}`;

        const ws = new WebSocket(socketUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            // A successful connection resets the backoff window and cancels
            // any pending retry from a prior transient failure.
            reconnectAttemptsRef.current = 0;
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }

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

                // Handle streaming messages
                if (message.type === "streaming:update" || message.type === "streaming:complete") {
                    setStreamingContent(prev => {
                        const newMap = new Map(prev);
                        const currentContent = newMap.get(message.id) || "";
                        const updatedContent = message.type === "streaming:complete"
                            ? message.content
                            : currentContent + (message.delta || "");

                        if (message.type === "streaming:complete") {
                            // Don't store completed streams, they'll be in regular messages
                            newMap.delete(message.id);
                        } else {
                            newMap.set(message.id, updatedContent);
                        }
                        return newMap;
                    });
                }

                setLastMessage(message);
            } catch (e) {
                // Silent catch
            }
        };

        ws.onclose = (event: CloseEvent) => {
            setIsConnected(false);
            wsRef.current = null;

            // Intentional teardown (disconnect()/unmount) — never reconnect.
            if (manualCloseRef.current) return;

            // Terminal close codes (auth/policy) — retrying is futile; the
            // session-driven effect handles auth recovery when NextAuth
            // refreshes the token. Mirrors lib/api.ts 401→no-retry convention.
            if (TERMINAL_CLOSE_CODES.has(event.code)) {
                console.warn(
                    `[useWebSocket] Terminal close (code ${event.code}) — not reconnecting. ` +
                    `Auth recovery will occur on session refresh.`
                );
                return;
            }

            // Transient close — schedule a reconnect with exponential backoff.
            if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
                const attempt = reconnectAttemptsRef.current; // 0-indexed
                reconnectAttemptsRef.current += 1;
                // delay * 2^attempt + jitter, capped. Jitter prevents retry
                // storms when many clients drop simultaneously.
                const jitter = Math.random() * 250;
                const delay = Math.min(
                    reconnectDelay * Math.pow(2, attempt) + jitter,
                    RECONNECT_MAX_DELAY_MS
                );
                reconnectTimeoutRef.current = setTimeout(() => {
                    reconnectTimeoutRef.current = null;
                    connect();
                }, delay);
            }
        };

        ws.onerror = (error) => {
            // Silent error or toast? For now silent.
        };
    }, [url, session, channelKey]); // Use channelKey instead of array ref

    const disconnect = useCallback(() => {
        // Mark the close as intentional so onclose doesn't schedule a reconnect.
        manualCloseRef.current = true;
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
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
        streamingContent,
        subscribe,
        unsubscribe,
        // Exposed so consumers can drive a "reconnecting…" indicator. No
        // existing consumer reads it; it's additive.
        reconnectAttempts: reconnectAttemptsRef.current,
        // Exposed so consumers can intentionally tear down without triggering
        // the auto-reconnect loop.
        disconnect,
        sendMessage: (msg: any) => {
            // Guard on OPEN state, matching subscribe/unsubscribe. A real
            // WebSocket.send() throws InvalidStateError while CONNECTING, and a
            // component that sends immediately on mount (before onopen) would
            // crash without this guard.
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify(msg));
            }
        },
    };
};
