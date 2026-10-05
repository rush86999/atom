/**
 * A generation-guarded raw WebSocket, for surfaces that need a socket
 * `useWebSocket` does not provide.
 *
 * WHY THIS EXISTS. `useWebSocket` (hooks/useWebSocket.ts) guards a socket by
 * generation: a callback belonging to a superseded socket cannot mutate shared
// state, deliver frames, or clear the current socket. Several surfaces still
 * open a raw `new WebSocket(...)` because they need something the hook does not
 * do — a different URL (`/ws/boards/{id}`, a per-channel subscription, a
 * cursor/presence protocol). Those surfaces had NO guard, and the hazard is
// the one the hook already documents:
 *
 *   - a component whose effect re-runs (team switched, canvas switched,
 *     presence id changed) closes the old socket and opens a new one, but the
 *     close is asynchronous — the OLD socket's `onmessage` can still fire and
 *     append another room's messages to the room now on screen, and its
 *     `onclose` can run against state that has already moved on;
 *   - a `null` assignment in an `onclose` orphans the socket that replaced it.
 *
 * A guard is PER OWNER, not global: two independent surfaces may each hold a
 * live socket (a comment thread per canvas, a cursor per document), so opening
 * one must not make the other's callbacks stale.
 *
 * Usage:
 *
 *   const guard = useRef(createSocketGuard()).current;
 *   useEffect(() => {
 *     const token = localStorage.getItem('auth_token');
 *     if (!token) return;
 *     return guard.open(url, {
 *       onOpen: (ws) => ws.send(JSON.stringify({ type: 'subscribe', channel })),
 *       onMessage: (data) => { ... },
 *     });
 *   }, [url, channel]);
 *
 * The returned function closes the socket AND retires its generation, and is
 * exactly what an effect should return as cleanup.
 */

export type GuardedSocketHandlers = {
    /** Called once, only if this socket is still current when it opens. */
    onOpen?: (socket: WebSocket) => void;
    /** Called for every frame, only while this socket is still current. */
    onMessage: (data: any, event: MessageEvent) => void;
    /** Called only if this socket is still current when it closes. */
    onClose?: (event: CloseEvent) => void;
    /** Called only if this socket is still current. */
    onError?: (event: Event) => void;
    /**
     * A frame arrived that was not JSON. The guard swallows it — a single
     * keepalive / proxy-error / partial frame must not kill the handler — and
     * reports it here so the frame is not invisible. The raw text is NOT
     * passed on: it could carry content.
     */
    onParseError?: (event: MessageEvent) => void;
    /**
     * Run just before THIS socket is retired (effect cleanup, or a replacement
     * socket superseding it), and only while it is still current. Use it for
     * teardown the server expects — an `unsubscribe` frame, say. A superseded
     * socket is not asked: it was already replaced, and the frame would go to a
     * connection nobody reads.
     */
    onRetire?: (socket: WebSocket) => void;
};

export type SocketGuard = {
    /**
     * Open a socket. Any socket this guard opened earlier is retired first, so
     * its late callbacks become no-ops.
     * Returns a cleanup function suitable for a `useEffect`.
     */
    open: (url: string, handlers: GuardedSocketHandlers) => () => void;
    /** Retire the current socket and close it. Same as the cleanup `open` returns. */
    close: () => void;
    /** The socket this guard currently owns, or null. */
    current: () => WebSocket | null;
    /** True while `socket` is the one this guard owns. */
    isCurrent: (socket: WebSocket | null) => boolean;
};

export function createSocketGuard(): SocketGuard {
    let generation = 0;
    let socket: WebSocket | null = null;
    let onRetire: ((socket: WebSocket) => void) | undefined;

    const retire = () => {
        if (!socket) return;
        // Retire BEFORE closing: the close frame is asynchronous, and its
        // onclose would otherwise run against a generation that is still
        // current and mutate state that has already moved on.
        generation += 1;
        const dying = socket;
        socket = null;
        try {
            // Teardown the server expects, while the socket is still the one we
            // own. A send here can throw if it is already closing; that is
            // harmless, the connection is going away regardless.
            onRetire?.(dying);
        } catch {
            // ignored — see above
        }
        try {
            dying.close();
        } catch {
            // A socket that is already CLOSED throws on some runtimes; the
            // teardown is already complete either way.
        }
    };

    return {
        open(url, handlers) {
            // A second open supersedes the first: retire it so its callbacks
            // cannot touch state that now belongs to the new socket.
            retire();
            const myGeneration = ++generation;
            const ws = new WebSocket(url);
            socket = ws;
            onRetire = handlers.onRetire;
            const isCurrent = () => myGeneration === generation && socket === ws;

            ws.onopen = () => {
                if (!isCurrent()) return;
                handlers.onOpen?.(ws);
            };
            ws.onmessage = (event: MessageEvent) => {
                // The core guard: a superseded socket's buffered frames are not
                // part of this conversation.
                if (!isCurrent()) return;
                let data: any;
                try {
                    data = JSON.parse(event.data);
                } catch {
                    // A non-JSON frame (keepalive, proxy error, partial) must
                    // not kill the handler and permanently deafen the surface.
                    try {
                        handlers.onParseError?.(event);
                    } catch { /* the report must not break the loop */ }
                    return;
                }
                try {
                    handlers.onMessage(data, event);
                } catch {
                    // A faulty consumer must not kill the socket loop.
                }
            };
            ws.onclose = (event: CloseEvent) => {
                if (!isCurrent()) return;
                socket = null;
                onRetire = undefined;
                handlers.onClose?.(event);
            };
            ws.onerror = (event: Event) => {
                if (!isCurrent()) return;
                handlers.onError?.(event);
            };

            return () => {
                if (myGeneration === generation) retire();
            };
        },
        close: retire,
        current: () => socket,
        isCurrent: (candidate) => candidate !== null && candidate === socket,
    };
}

/**
 * The query-string token, with the credential kept out of anything loggable.
 * Returns a redacted URL for diagnostics.
 */
export const redactSocketUrl = (url: string): string => url.split("?")[0];
