/**
 * DELIBERATELY BROKEN VARIANT of useWebSocket — negative control only.
 *
 * This file exists so the stale-callback suite can prove its assertions are
 * load-bearing: every guard that commit 59f6ca6d5 added to `onclose` is
 * REMOVED here, and the single-retry / same-token rules are reverted to their
 * pre-fix shape. It is never imported by production code.
 *
 * Do NOT "fix" this file. If a negative control starts passing, the control has
 * stopped detecting the defect and the suite is worthless.
 *
 * Origin: hooks/useWebSocket.ts, generation guard removed from onopen/onmessage.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { getApiBase } from "@/lib/api-base";
import { useSession } from "next-auth/react";

const TERMINAL_CLOSE_CODES = new Set([4001, 1008]);

export const useWebSocketBroken = (options: any = {}) => {
    const { data: session } = useSession();
    const {
        url = "",
        autoConnect = true,
        reconnect = true,
        maxReconnectAttempts = Number.POSITIVE_INFINITY,
        reconnectDelay = 1000,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<any>(null);
    const [streamingContent, setStreamingContent] = useState<Map<string, string>>(new Map());
    const [reconnectAttempts, setReconnectAttempts] = useState(0);
    const wsRef = useRef<any>(null);
    const generationRef = useRef(0);
    const messageHandlersRef = useRef<Set<any>>(new Set());
    const onMessage = useCallback((handler: any) => {
        messageHandlersRef.current.add(handler);
        return () => { messageHandlersRef.current.delete(handler); };
    }, []);
    const reconnectTimeoutRef = useRef<any>(null);
    const reconnectAttemptsRef = useRef<number>(0);
    const manualCloseRef = useRef<boolean>(false);
    const connectRef = useRef<() => void>(() => {});
    const channelKey = JSON.stringify(options.initialChannels || []);

    const resolveWsBase = (): string => {
        let base = getApiBase();
        if (!base && typeof window !== "undefined") base = window.location.origin;
        return base.replace(/^http/, "ws");
    };

    const connect = useCallback(() => {
        if (wsRef.current && (wsRef.current.readyState === 1 || wsRef.current.readyState === 0)) return;
        manualCloseRef.current = false;
        let token = session?.backendToken || session?.accessToken;
        if (!token && typeof window !== "undefined") {
            token = localStorage.getItem("auth_token") || undefined;
        }
        if (!token) return;
        const wsBase = resolveWsBase();
        let socketUrl = `${wsBase}/ws`;
        if (url && (url.startsWith("ws://") || url.startsWith("wss://"))) socketUrl = url;
        const ws = new WebSocket(`${socketUrl}?token=${token}`);
        // NOTE: no generation is captured. This is the defect under audit.

        // DEFECT 1: unguarded onopen — a retired socket's late accept clears
        // the LIVE generation's pending reconnect timer and re-subscribes on
        // the dead socket.
        ws.onopen = () => {
            setIsConnected(true);
            reconnectAttemptsRef.current = 0;
            setReconnectAttempts(0);
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
            try {
                JSON.parse(channelKey).forEach((c: string) =>
                    ws.send(JSON.stringify({ type: "subscribe", channel: c })));
            } catch { /* ignore */ }
        };

        // DEFECT 2: unguarded onmessage — a retired socket keeps writing state
        // and keeps fanning frames out to every listener.
        ws.onmessage = (event: any) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === "streaming:update" || message.type === "streaming:complete") {
                    setStreamingContent((prev: Map<string, string>) => {
                        const m = new Map(prev);
                        const cur = m.get(message.id) || "";
                        if (message.type === "streaming:complete") m.delete(message.id);
                        else m.set(message.id, cur + (message.delta || ""));
                        return m;
                    });
                }
                setLastMessage(message);
                messageHandlersRef.current.forEach((h: any) => { try { h(message); } catch { /* isolate */ } });
            } catch { /* ignore */ }
        };

        // DEFECT 3: every observed close schedules a NEW timer and overwrites
        // the previous handle, so duplicate close frames leak sockets.
        ws.onclose = (event: any) => {
            setIsConnected(false);
            wsRef.current = null;
            if (manualCloseRef.current) return;
            if (TERMINAL_CLOSE_CODES.has(event.code)) return;
            if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
                const attempt = reconnectAttemptsRef.current;
                reconnectAttemptsRef.current += 1;
                setReconnectAttempts(reconnectAttemptsRef.current);
                const jitter = Math.random() * 250;
                const delay = Math.min(reconnectDelay * Math.pow(2, attempt) + jitter, 10000);
                reconnectTimeoutRef.current = setTimeout(() => {
                    reconnectTimeoutRef.current = null;
                    connectRef.current();
                }, delay);
            }
        };
        ws.onerror = () => { /* silent, as in the original */ };
        wsRef.current = ws;
    }, [url, session, channelKey, reconnect, maxReconnectAttempts, reconnectDelay]);

    useEffect(() => { connectRef.current = connect; }, [connect]);

    const disconnect = useCallback(() => {
        manualCloseRef.current = true;
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (wsRef.current) {
            generationRef.current += 1;
            wsRef.current.close();
            wsRef.current = null;
        }
        setIsConnected(false);
    }, []);

    const subscribe = useCallback((channel: string) => {
        if (wsRef.current?.readyState === 1) {
            wsRef.current.send(JSON.stringify({ type: "subscribe", channel }));
        }
    }, []);

    const unsubscribe = useCallback((channel: string) => {
        if (wsRef.current?.readyState === 1) {
            wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
        }
    }, []);

    // DEFECT 4: `connect` depends on the whole `session` OBJECT, so every
    // next-auth poll (new object, same token) tears the socket down and
    // rebuilds it.
    useEffect(() => {
        if (autoConnect) connect();
        return () => disconnect();
    }, [autoConnect, connect, disconnect]);

    return {
        isConnected,
        lastMessage,
        streamingContent,
        subscribe,
        unsubscribe,
        onMessage,
        reconnectAttempts,
        disconnect,
        sendMessage: (m: any) => {
            if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify(m));
        },
    };
};
