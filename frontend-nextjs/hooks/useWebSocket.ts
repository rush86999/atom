import { useState, useEffect, useRef, useCallback } from "react";
import { getApiBase } from "@/lib/api-base";
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
    /** Max reconnect attempts before giving up (default: unlimited —
     *  capped-delay retries). Backend restarts (scripts/restart_backend.sh)
     *  take 15–20s; the old cap of 3 fired its 1s/2s/4s retries while the
     *  server was still down and then went silent FOREVER — the page kept
     *  working via REST but every live update (agent replies, canvas
     *  edits) needed a manual refresh. Non-terminal close codes are
     *  transient by definition; auth closes are handled separately. */
    maxReconnectAttempts?: number;
    /** Initial reconnect delay in ms; doubles each attempt, capped at 10s (default: 1000). */
    reconnectDelay?: number;
}

export type WebSocketMessageHandler = (message: WebSocketMessage) => void;

// Close codes that should NOT trigger a reconnect — they are terminal and
// retrying would either loop on an immutable failure (auth) or violate a
// policy decision. Auth (4001) recovery is handled by the session-driven
// effect (NextAuth refreshes the token → connect() re-runs).
const TERMINAL_CLOSE_CODES = new Set([4001, 1008]);
const RECONNECT_MAX_DELAY_MS = 10000;
const parseInitialChannels = (channelKey: string): string[] => {
    try {
        const channels = JSON.parse(channelKey);
        return Array.isArray(channels) ? channels : [];
    } catch {
        return [];
    }
};

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
    const { data: session } = useSession();
    const {
        url = "",  // Empty default — uses resolveWsBase() derived from NEXT_PUBLIC_API_URL.
                    // Previously hardcoded "ws://localhost:8000/ws" which bypassed
                    // resolveWsBase() and broke WebSocket in non-localhost deploys.
        autoConnect = true,
        reconnect = true,
        maxReconnectAttempts = Number.POSITIVE_INFINITY,
        reconnectDelay = 1000,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [streamingContent, setStreamingContent] = useState<Map<string, string>>(new Map());
    const [reconnectAttempts, setReconnectAttempts] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);

    // SOCKET GENERATION. A socket that is CLOSING does not block a new
    // connect() (only OPEN/CONNECTING do), so a reconnect could install
    // socket N+1 and then the OLD socket's onclose would run and null
    // wsRef.current — orphaning a live connection. isConnected would flap
    // and subscribe() would silently no-op on a socket that is actually
    // open. Every socket carries the generation it was created in, and a
    // close/cleanup only mutates shared state if it is still the current
    // generation.
    //
    // THE GENERATION GUARDS ON *EVERY* CALLBACK, NOT JUST onclose. A retired
    // socket can still fire its open and message handlers, and both mutate
    // shared state:
    //   - a stale `onopen` used to clearTimeout() the SHARED reconnect ref, so
    //     a dead connection's late accept cancelled the LIVE generation's only
    //     path back from a real outage, and it re-sent `initialChannels`
    //     subscriptions on the dead socket, leaving the live one unsubscribed;
    //   - a stale `onmessage` used to write `lastMessage`/`streamingContent`
    //     and fan frames out to every `onMessage` handler, so a connection the
    //     hook had already abandoned kept injecting frames into the UI.
    // "A late callback must not change state, deliver tokens, or clear the
    // current socket" — so the guard is checked first in all three handlers.
    const generationRef = useRef(0);

    // Per-message listener registry. `lastMessage` is a SINGLE state slot:
    // under a fast frame burst (chat_token streams deliver hundreds of
    // frames in seconds) React coalesces the setLastMessage calls and the
    // consumer's [lastMessage] effect only ever sees the newest frame —
    // every frame landing between two render commits is silently dropped
    // (measured in hooks/chat/__tests__/useWebSocket.stale-callbacks.test.ts:
    // 50 frames in one commit reach a listener 50 times and a [lastMessage]
    // effect ONCE). Handlers registered here are invoked synchronously for
    // EVERY message, in arrival order, so streaming consumers lose nothing.
    const messageHandlersRef = useRef<Set<WebSocketMessageHandler>>(new Set());
    const onMessage = useCallback((handler: WebSocketMessageHandler) => {
        messageHandlersRef.current.add(handler);
        return () => {
            messageHandlersRef.current.delete(handler);
        };
    }, []);

    // Reconnect bookkeeping. These are REFS (not state) so the setTimeout
    // callback reads live values — avoiding the stale-closure bug seen in
    // useWhatsAppWebSocket.ts where the counter was captured from a prior render.
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectAttemptsRef = useRef<number>(0);
    // Which generation owns the pending retry. A timer left over from a
    // generation that has since been superseded must not open a socket:
    // a superseded retry is exactly a stale callback in time-delay form.
    const reconnectGenerationRef = useRef<number | null>(null);
    // Tracks whether the close was intentional (disconnect() / unmount) so the
    // onclose handler doesn't kick off a reconnect loop for a deliberate teardown.
    const manualCloseRef = useRef<boolean>(false);
    const connectRef = useRef<() => void>(() => {});

    // Use deep comparison key for channels array to avoid ref instability
    const channelKey = JSON.stringify(options.initialChannels || []);

    // AUTH CREDENTIAL AS A VALUE, NOT AN OBJECT IDENTITY.
    // `connect` used to depend on the whole `session` OBJECT. next-auth
    // returns a new object on every session poll, refetch and router event, so
    // an unchanged credential still changed `connect`, re-ran the autoConnect
    // effect, and tore the socket down and rebuilt it (disconnect() then
    // connect()) for reasons unrelated to the credential. Depending on the
    // TOKEN STRING distinguishes the two cases that actually matter: a
    // same-token render is a no-op, and a changed token is a deliberate
    // reconnect. The value is used directly inside connect() so the dependency
    // list stays accurate — no lint suppression and no captured stale session.
    const authToken = (session as any)?.backendToken || (session as any)?.accessToken || "";

    // Derive the default WebSocket host so the client talks to the same
    // backend the REST API uses. MUST mirror lib/api.ts's fallback chain:
    // reading NEXT_PUBLIC_API_URL alone left wsBase empty whenever that one
    // var wasn't inlined into the build, and new WebSocket("/ws?...") throws
    // a SyntaxError inside the connect effect — the socket then silently
    // never existed (badge stuck on "Offline", live logs dead) while REST
    // kept working via its PYTHON_BACKEND_URL fallback.
    const resolveWsBase = (): string => {
        // Shared resolver (lib/api-base.ts) — env first, dev backend port.
        // An EMPTY base is never valid for WebSocket (a relative URL throws
        // SyntaxError), so same-origin deployments resolve from location.
        let base = getApiBase();
        if (!base && typeof window !== "undefined") {
            base = window.location.origin;
        }
        return base.replace(/^http/, "ws"); // http:// -> ws://, https:// -> wss://
    };

    const connect = useCallback(() => {
        // A CONNECTING socket is an in-flight attempt, not a dead one.
        // Creating a second socket then orphaned the first: it kept the
        // handler wiring, finished connecting, and delivered EVERY frame
        // twice (observed live 2026-09-07 on /canvas/[id]: duplicated
        // reasoning steps and a doubled reply bubble). Auth recovery is
        // unaffected — it always goes through disconnect(), which nulls
        // wsRef before reconnecting.
        if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

        // A fresh connect() is an auto-connect unless disconnect() sets this
        // again immediately before. Reset so the onclose handler treats the
        // next close as a candidate for reconnect.
        manualCloseRef.current = false;

        // Resolve JWT token: the session credential first, then the
        // localStorage copy written by pages/login.tsx. `authToken` is the
        // VALUE this hook keys its connection identity on, so reading it here
        // is exact — never a stale capture.
        let token: string | undefined = authToken || undefined;

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
        // NOTE: the token is appended to the URL and must never reach a log.
        // Diagnostics below carry socket generation, close code and the
        // sanitized endpoint only.
        socketUrl = `${socketUrl}${hasParams ? "&" : "?"}token=${token}`;

        const ws = new WebSocket(socketUrl);
        const generation = ++generationRef.current;
        wsRef.current = ws;

        // The URL without its credential, for diagnostics.
        const sanitizedEndpoint = `${socketUrl.split("?")[0]}`;

        ws.onopen = () => {
            // A socket that has been superseded owns nothing: it must not
            // publish a connection, cancel the current generation's pending
            // retry, or re-subscribe channels on a connection nobody reads.
            if (generation !== generationRef.current) {
                console.debug(
                    `[useWebSocket] stale socket opened (gen ${generation}, ` +
                    `current ${generationRef.current}) — ignoring`);
                return;
            }
            setIsConnected(true);
            // A successful connection resets the backoff window and cancels
            // any pending retry from a prior transient failure.
            reconnectAttemptsRef.current = 0;
            setReconnectAttempts(0);
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
            reconnectGenerationRef.current = null;

            // Re-subscribe to channels if any. `ws` is the current generation
            // here, so this subscription belongs to the live connection and
            // cannot multiply across reconnects.
            parseInitialChannels(channelKey).forEach(channel => {
                ws.send(JSON.stringify({ type: "subscribe", channel }));
            });
        };

        ws.onmessage = (event) => {
            // A retired socket's buffered frames are not part of this
            // conversation: dropping them here is what keeps a late frame
            // from overwriting the newest message, from corrupting the
            // streaming accumulator, and from being fanned out to consumers.
            if (generation !== generationRef.current) {
                console.debug(
                    `[useWebSocket] dropped frame from stale socket (gen ${generation}, ` +
                    `current ${generationRef.current})`);
                return;
            }
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
                // Listener delivery — see the registry comment above. A handler
                // must never break the others (or the state update) — isolate it.
                messageHandlersRef.current.forEach(handler => {
                    try {
                        handler(message);
                    } catch {
                        // a faulty consumer must not kill the socket loop
                    }
                });
            } catch (e) {
                // Silent catch
            }
        };

        ws.onclose = (event: CloseEvent) => {
            // Only the CURRENT generation may clear shared state. A stale
            // socket closing must not disconnect or untrack its successor.
            if (generation !== generationRef.current) {
                console.debug(
                    `[useWebSocket] stale socket closed (gen ${generation}, ` +
                    `current ${generationRef.current}) — ignoring`);
                return;
            }
            setIsConnected(false);
            wsRef.current = null;

            // Intentional teardown (disconnect()/unmount) — never reconnect.
            if (manualCloseRef.current) return;

            // Terminal close codes (auth/policy) — retrying is futile; the
            // session-driven effect handles auth recovery when NextAuth
            // refreshes the token. Mirrors lib/api.ts 401→no-retry convention.
            if (TERMINAL_CLOSE_CODES.has(event.code)) {
                console.warn(
                    `[useWebSocket] Terminal close (code ${event.code}) on ${sanitizedEndpoint} — ` +
                    `not reconnecting. Auth recovery will occur on session refresh.`
                );
                return;
            }

            // AT MOST ONE RETRY IS EVER PENDING. A close can be observed more
            // than once (server frame + our own teardown, proxy + client), and
            // each observation used to overwrite the previous timer handle —
            // losing the only cancellable reference and leaking a socket per
            // duplicate. Collapse onto the retry that is already scheduled.
            if (reconnectTimeoutRef.current) return;
            if (!reconnect) return;
            if (reconnectAttemptsRef.current >= maxReconnectAttempts) return;

            // Transient close — schedule a reconnect with exponential backoff.
            const attempt = reconnectAttemptsRef.current; // 0-indexed
            reconnectAttemptsRef.current += 1;
            setReconnectAttempts(reconnectAttemptsRef.current);
            // delay * 2^attempt + jitter, capped. Jitter prevents retry
            // storms when many clients drop simultaneously.
            const jitter = Math.random() * 250;
            const delay = Math.min(
                reconnectDelay * Math.pow(2, attempt) + jitter,
                RECONNECT_MAX_DELAY_MS
            );
            reconnectGenerationRef.current = generation;
            reconnectTimeoutRef.current = setTimeout(() => {
                reconnectTimeoutRef.current = null;
                const owner = reconnectGenerationRef.current;
                reconnectGenerationRef.current = null;
                // A retry that outlived its generation is a stale callback in
                // time-delay form: a successor already owns the connection.
                if (owner !== null && owner !== generationRef.current) {
                    console.debug(
                        `[useWebSocket] dropping retry scheduled by superseded gen ${owner} ` +
                        `(current ${generationRef.current})`);
                    return;
                }
                connectRef.current();
            }, delay);
        };

        ws.onerror = (error) => {
            // Silent error or toast? For now silent.
        };
    }, [url, authToken, channelKey, reconnect, maxReconnectAttempts, reconnectDelay]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    const disconnect = useCallback(() => {
        // Mark the close as intentional so onclose doesn't schedule a reconnect.
        manualCloseRef.current = true;
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        // Retire the pending retry's owner too, so nothing that outlives this
        // call can open a socket on the caller's behalf.
        reconnectGenerationRef.current = null;
        if (wsRef.current) {
            // Retire the generation BEFORE closing: the close is
            // asynchronous, and its onclose would otherwise run against a
            // generation that is still current. Because that close is now
            // correctly ignored, the connected state is cleared HERE
            // rather than left to the ignored handler — otherwise an
            // intentional teardown leaves isConnected stuck true.
            generationRef.current += 1;
            wsRef.current.close();
            wsRef.current = null;
        }
        setIsConnected(false);
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

    // A page that regains visibility/focus/network after its socket died
    // (laptop sleep, backend restart, proxy idle timeout) must not sit
    // silently dead until the next manual refresh — probe and reconnect
    // immediately (standard practice: socket.io reconnection + visibility
    // rejoin). The OPEN/CONNECTING guard makes this a no-op when healthy.
    useEffect(() => {
        if (!autoConnect || !reconnect) return;
        const probe = () => {
            const ws = wsRef.current;
            const healthy = !!ws && (
                ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING
            );
            if (!healthy && !manualCloseRef.current) connect();
        };
        const onVisibility = () => {
            if (document.visibilityState === "visible") probe();
        };
        document.addEventListener("visibilitychange", onVisibility);
        window.addEventListener("focus", probe);
        window.addEventListener("online", probe);
        return () => {
            document.removeEventListener("visibilitychange", onVisibility);
            window.removeEventListener("focus", probe);
            window.removeEventListener("online", probe);
        };
    }, [autoConnect, reconnect, connect]);

    return {
        isConnected,
        lastMessage,
        streamingContent,
        subscribe,
        unsubscribe,
        // Register a handler that sees EVERY message (no coalescing drops).
        // Returns an unsubscribe function — ideal from a useEffect cleanup.
        onMessage,
        // Exposed so consumers can drive a "reconnecting…" indicator. No
        // existing consumer reads it; it's additive.
        reconnectAttempts,
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
