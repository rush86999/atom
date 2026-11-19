import React, { useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';

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

interface ScopedMessages {
    scope: string;
    items: Message[];
}

interface ScopedStatus {
    scope: string;
    loading: boolean;
    error: string | null;
}

interface ScopedNotice {
    scope: string;
    message: string;
}

const HISTORY_LIMIT = 50;
const MESSAGE_MAX_LENGTH = 8000;
const ACCESS_REVOKED_MESSAGE =
    'You no longer have access to this conversation. Please refresh to reload messages.';
const UNCONFIRMED_SEND_MESSAGE =
    'Message could not be confirmed. Please refresh the conversation before retrying.';
// Push used to arrive over a shared websocket. Until a private, authorized
// transport is qualified, this panel refreshes its authorized HTTP history on
// a timer. Every request is scoped to the team/context currently on screen.
const HISTORY_REFRESH_MS = 15000;

const scopeFor = (teamId?: string, contextType?: string, contextId?: string) =>
    `${teamId ?? ''}\u0000${contextType ?? ''}\u0000${contextId ?? ''}`;

const readAuthToken = (): string | null => {
    if (typeof window === 'undefined') return null;
    try {
        return window.localStorage.getItem('auth_token');
    } catch {
        return null;
    }
};

const messageTimestamp = (message: Message): number => {
    const parsed = Date.parse(message?.created_at ?? '');
    return Number.isFinite(parsed) ? parsed : 0;
};

const messageKey = (message: Message): string => {
    if (message.id !== undefined && message.id !== null && String(message.id) !== '') {
        return `id:${String(message.id)}`;
    }
    return `fallback:${message.team_id ?? ''}:${message.user_id ?? ''}:${message.created_at ?? ''}:${message.content ?? ''}`;
};

/**
 * Combine history and locally persisted POST results without rendering the same
 * message twice. Keep the newest HISTORY_LIMIT messages but render them oldest
 * first, matching the original panel.
 */
const mergeMessages = (current: Message[], incoming: Message[]): Message[] => {
    const byKey = new Map<string, Message>();

    [...current, ...incoming].forEach((message) => {
        if (!message || typeof message !== 'object') return;
        const key = messageKey(message);
        const existing = byKey.get(key);
        byKey.set(key, existing ? { ...existing, ...message } : message);
    });

    const ordered = Array.from(byKey.values())
        .map((message, index) => ({ message, index }))
        .sort((a, b) => {
            const byDate = messageTimestamp(a.message) - messageTimestamp(b.message);
            return byDate !== 0 ? byDate : a.index - b.index;
        })
        .map(({ message }) => message);

    return ordered.slice(-HISTORY_LIMIT);
};

const initialsFor = (name?: string): string => {
    const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return '?';
    return parts.map((part) => part[0]).join('').toUpperCase().slice(0, 2);
};

/**
 * A successful POST is only usable when the server returned a real persisted
 * message. Never synthesize a local id, sender, or timestamp: doing so would
 * make an unconfirmed result look delivered and could duplicate it on retry.
 */
const persistedMessageFrom = (
    payload: unknown,
    fallback: {
        teamId: string;
        contextType?: string;
        contextId?: string;
    }
): Message | null => {
    const root = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
    const raw =
        root.message && typeof root.message === 'object'
            ? (root.message as Record<string, unknown>)
            : root;
    const asString = (value: unknown): string | undefined =>
        typeof value === 'string' && value.length > 0 ? value : undefined;

    const id =
        raw.id !== undefined && raw.id !== null ? String(raw.id).trim() : '';
    const teamId = asString(raw.team_id);
    const content = asString(raw.content);
    const senderName = asString(raw.sender_name);
    const createdAt = asString(raw.created_at);

    if (
        !id ||
        !teamId ||
        teamId !== fallback.teamId ||
        !content ||
        !content.trim() ||
        !senderName ||
        !senderName.trim() ||
        !createdAt ||
        !Number.isFinite(Date.parse(createdAt))
    ) {
        return null;
    }

    return {
        id,
        team_id: teamId,
        user_id: asString(raw.user_id) ?? '',
        sender_name: senderName,
        content,
        context_type: asString(raw.context_type) ?? fallback.contextType,
        context_id: asString(raw.context_id) ?? fallback.contextId,
        created_at: createdAt,
    };
};

export default function TeamChatPanel({
    teamId,
    contextType,
    contextId,
    className = ''
}: TeamChatPanelProps) {
    const scope = scopeFor(teamId, contextType, contextId);

    const [messageState, setMessageState] = useState<ScopedMessages>({
        scope,
        items: [],
    });
    const [status, setStatus] = useState<ScopedStatus>({
        scope,
        loading: Boolean(teamId),
        error: null,
    });
    const [newMessage, setNewMessage] = useState('');
    const [sendError, setSendError] = useState<ScopedNotice | null>(null);
    const [sending, setSending] = useState<{ scope: string; seq: number } | null>(null);
    const [refreshKey, setRefreshKey] = useState(0);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const historySeqRef = useRef(0);
    const loadedScopeRef = useRef<string | null>(null);
    // Set when history or a send is rejected as unauthorized/revoked. Only a
    // newer, successful history response may clear it.
    const revokedHistorySeqRef = useRef<{ scope: string; seq: number } | null>(null);
    const scopeRef = useRef(scope);
    const pendingSendRef = useRef<{ scope: string; seq: number } | null>(null);
    const sendSeqRef = useRef(0);

    // Only state belonging to the team/context currently on screen may render.
    // This also prevents a late response from the previous team leaking through
    // during the render before the load effect has run.
    const messages = messageState.scope === scope ? messageState.items : [];
    const loading = status.scope === scope ? status.loading : Boolean(teamId);
    const loadError = status.scope === scope ? status.error : null;
    const currentSendError = sendError?.scope === scope ? sendError.message : null;
    const isSending = sending?.scope === scope;

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Changing team or context invalidates any request/draft tied to the old
    // scope. An in-flight send may still resolve, but it must not clear the new
    // draft or append its message to the new team.
    useEffect(() => {
        scopeRef.current = scope;
        sendSeqRef.current += 1;
        pendingSendRef.current = null;
        setSending(null);
        setSendError(null);
        setNewMessage('');
    }, [scope]);

    // Authorized HTTP history load/refresh, scoped to the visible team/context.
    useEffect(() => {
        if (!teamId) {
            setStatus({ scope, loading: false, error: null });
            setMessageState({ scope, items: [] });
            return;
        }

        const token = readAuthToken();
        if (!token) {
            loadedScopeRef.current = scope;
            setStatus({ scope, loading: false, error: null });
            setMessageState({ scope, items: [] });
            return;
        }

        const isRefresh = loadedScopeRef.current === scope;
        const seq = ++historySeqRef.current;
        let cancelled = false;
        const controller = new AbortController();

        if (!isRefresh) {
            setStatus({ scope, loading: true, error: null });
        }
        setMessageState((previous) =>
            previous.scope === scope ? previous : { scope, items: [] }
        );

        const params = new URLSearchParams({ limit: String(HISTORY_LIMIT) });
        if (contextType) params.set('context_type', contextType);
        if (contextId) params.set('context_id', contextId);

        const url = `/api/teams/${encodeURIComponent(teamId)}/messages?${params.toString()}`;

        fetch(url, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
            signal: controller.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    const error = new Error(
                        `History request failed with ${response.status}`
                    ) as Error & { status?: number };
                    error.status = response.status;
                    throw error;
                }
                return response.json();
            })
            .then((data) => {
                if (
                    cancelled ||
                    seq !== historySeqRef.current ||
                    scopeRef.current !== scope
                ) {
                    return;
                }

                // A response started before access was revoked is not a fresh
                // confirmation and must not repopulate the cleared panel.
                const revoked = revokedHistorySeqRef.current;
                if (revoked && revoked.scope === scope && seq <= revoked.seq) {
                    return;
                }

                revokedHistorySeqRef.current = null;
                const history = Array.isArray(data) ? (data as Message[]) : [];
                setMessageState((previous) => ({
                    scope,
                    items: mergeMessages(
                        previous.scope === scope ? previous.items : [],
                        history
                    ),
                }));
                loadedScopeRef.current = scope;
                setStatus({ scope, loading: false, error: null });
            })
            .catch((error) => {
                if (
                    cancelled ||
                    controller.signal.aborted ||
                    seq !== historySeqRef.current ||
                    scopeRef.current !== scope
                ) {
                    return;
                }

                const status = (error as { status?: number }).status;
                if (status === 401 || status === 403 || status === 404) {
                    revokedHistorySeqRef.current = { scope, seq };
                    loadedScopeRef.current = null;
                    setMessageState({ scope, items: [] });
                    setStatus({
                        scope,
                        loading: false,
                        error: ACCESS_REVOKED_MESSAGE,
                    });
                    return;
                }

                console.error('Failed to load messages:', error);
                setStatus({ scope, loading: false, error: 'Could not load messages.' });
            });

        return () => {
            cancelled = true;
            controller.abort();
        };
    }, [teamId, contextType, contextId, scope, refreshKey]);

    // Refresh the authorized HTTP history while this team remains visible.
    useEffect(() => {
        if (!teamId) return;

        const interval = window.setInterval(() => {
            if (
                typeof document !== 'undefined' &&
                document.visibilityState === 'hidden'
            ) {
                return;
            }
            setRefreshKey((value) => value + 1);
        }, HISTORY_REFRESH_MS);

        return () => window.clearInterval(interval);
    }, [teamId, contextType, contextId]);

    const retryLoad = () => {
        loadedScopeRef.current = null;
        setRefreshKey((value) => value + 1);
    };

    const sendMessage = async () => {
        if (!teamId) return;
        const content = newMessage.trim();
        if (!content) return;
        if (pendingSendRef.current?.scope === scope) return;

        const token = readAuthToken();
        if (!token) {
            setSendError({ scope, message: 'Please sign in to send messages.' });
            return;
        }

        const requestScope = scope;
        const seq = ++sendSeqRef.current;
        pendingSendRef.current = { scope: requestScope, seq };
        setSending({ scope: requestScope, seq });
        setSendError(null);

        try {
            const response = await fetch(
                `/api/teams/${encodeURIComponent(teamId)}/messages`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${token}`,
                    },
                    body: JSON.stringify({
                        content,
                        context_type: contextType,
                        context_id: contextId,
                    }),
                }
            );

            if (!response.ok) {
                if (
                    response.status === 401 ||
                    response.status === 403 ||
                    response.status === 404
                ) {
                    if (
                        scopeRef.current !== requestScope ||
                        sendSeqRef.current !== seq
                    ) {
                        return;
                    }
                    // Access was revoked. Hide everything currently displayed
                    // and require a fresh authorized history response before
                    // this screen can show messages again.
                    revokedHistorySeqRef.current = {
                        scope: requestScope,
                        seq: historySeqRef.current,
                    };
                    loadedScopeRef.current = null;
                    setMessageState({ scope: requestScope, items: [] });
                    setStatus({
                        scope: requestScope,
                        loading: false,
                        error: ACCESS_REVOKED_MESSAGE,
                    });
                    setSendError({
                        scope: requestScope,
                        message: ACCESS_REVOKED_MESSAGE,
                    });
                    return;
                }
                throw new Error(`Send request failed with ${response.status}`);
            }

            let payload: unknown = null;
            try {
                payload = await response.json();
            } catch {
                payload = null;
            }

            if (scopeRef.current !== requestScope || sendSeqRef.current !== seq) {
                return;
            }

            const revoked = revokedHistorySeqRef.current;
            if (revoked && revoked.scope === requestScope) {
                // A stale in-flight send must not repopulate a revoked screen.
                setSendError({
                    scope: requestScope,
                    message: UNCONFIRMED_SEND_MESSAGE,
                });
                return;
            }

            const persisted = persistedMessageFrom(payload, {
                teamId,
                contextType,
                contextId,
            });

            if (!persisted) {
                // Do not invent a local message or clear the draft. The POST may
                // have succeeded, so ask for a refresh before retrying.
                setSendError({
                    scope: requestScope,
                    message: UNCONFIRMED_SEND_MESSAGE,
                });
                return;
            }

            setMessageState((previous) => ({
                scope: requestScope,
                items: mergeMessages(
                    previous.scope === requestScope ? previous.items : [],
                    [persisted]
                ),
            }));
            // Keep any text typed while the request was pending; only clear the
            // exact draft that was successfully sent.
            setNewMessage((previous) => (previous.trim() === content ? '' : previous));
            setSendError(null);
        } catch (error) {
            if (scopeRef.current !== requestScope || sendSeqRef.current !== seq) {
                return;
            }
            console.error('Failed to send message:', error);
            // The draft is deliberately retained so the user can retry.
            setSendError({
                scope: requestScope,
                message: 'Message could not be sent. Please try again.',
            });
        } finally {
            if (sendSeqRef.current === seq) {
                pendingSendRef.current = null;
                setSending((current) =>
                    current && current.seq === seq ? null : current
                );
            }
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            void sendMessage();
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
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {!teamId ? (
                    <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
                        Select a team to start chatting.
                    </div>
                ) : loading ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : loadError && messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-3">
                        <p className="text-gray-600 dark:text-gray-300">{loadError}</p>
                        <button
                            type="button"
                            onClick={retryLoad}
                            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                ) : messages.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
                        No messages yet. Start the conversation!
                    </div>
                ) : (
                    <>
                        {loadError && (
                            <div className="flex items-center justify-between gap-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                                <span>{loadError}</span>
                                <button
                                    type="button"
                                    onClick={retryLoad}
                                    className="font-medium underline"
                                >
                                    Retry
                                </button>
                            </div>
                        )}
                        {messages.map((msg) => (
                            <div key={msg.id} className="flex items-start space-x-3">
                                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-semibold">
                                    {initialsFor(msg.sender_name)}
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
                        ))}
                    </>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                {currentSendError && (
                    <p role="alert" className="mb-2 text-sm text-red-600 dark:text-red-400">
                        {currentSendError}
                    </p>
                )}
                <div className="flex items-end space-x-2">
                    <div className="flex-1 relative">
                        <textarea
                            value={newMessage}
                            onChange={(e) => setNewMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Type a message..."
                            rows={1}
                            maxLength={MESSAGE_MAX_LENGTH}
                            disabled={!teamId}
                            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white resize-none"
                        />
                    </div>
                    <button
                        type="button"
                        onClick={() => void sendMessage()}
                        disabled={!teamId || !newMessage.trim() || isSending}
                        aria-label="Send message"
                        className="p-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
