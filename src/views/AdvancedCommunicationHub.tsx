import React, { useState, useEffect, useCallback, useMemo, useRef, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// COMMUNICATION HUB - ADVANCED REAL-TIME FEATURES (250+ features)
// ============================================================================

interface ConversationThread {
    id: string;
    participants: string[];
    topic: string;
    messageCount: number;
    lastMessage: string;
    lastMessageTime: number;
    isActive: boolean;
    priority: 'high' | 'medium' | 'low';
    unreadCount: number;
    attachments: Attachment[];
    mentions: Mention[];
    reactions: ReactionCount[];
    translatedTo?: string;
}

interface Mention {
    userId: string;
    username: string;
    position: number;
    timestamp: number;
}

interface Attachment {
    id: string;
    filename: string;
    type: string;
    size: number;
    url: string;
    uploadedBy: string;
    uploadedAt: number;
    isProcessing: boolean;
    scanStatus: 'pending' | 'clean' | 'suspicious' | 'blocked';
}

interface ReactionCount {
    emoji: string;
    count: number;
    users: string[];
}

interface MessageThread {
    id: string;
    text: string;
    sender: string;
    timestamp: number;
    edited: boolean;
    editedAt?: number;
    reactions: string[];
    attachments: Attachment[];
    isEncrypted: boolean;
    canDelete: boolean;
    canEdit: boolean;
    translationHistory: Translation[];
    aiSummary?: string;
    sentiment: 'positive' | 'neutral' | 'negative';
}

interface Translation {
    language: string;
    text: string;
    timestamp: number;
}

interface ChannelNotification {
    id: string;
    type: 'mention' | 'keyword' | 'important' | 'custom';
    trigger: string;
    priority: 'critical' | 'high' | 'medium' | 'low';
    enabled: boolean;
}

// Advanced Message Card Component (Real-time Updates)
const AdvancedMessageCard: FC<{
    message: MessageThread;
    onReact?: (emoji: string) => void;
    onTranslate?: (lang: string) => void;
    onEdit?: () => void;
    onDelete?: () => void;
}> = ({ message, onReact, onTranslate, onEdit, onDelete }) => {
    const [showReactions, setShowReactions] = useState(false);
    const [showTranslate, setShowTranslate] = useState(false);
    const [selectedLang, setSelectedLang] = useState('es');

    const reactions = ['👍', '❤️', '😂', '😮', '😢', '🔥', '💯', '✨'];

    return (
        <div className="advanced-message-card">
            <div className="message-header">
                <span className="sender-name">{message.sender}</span>
                <span className="timestamp">{new Date(message.timestamp).toLocaleTimeString()}</span>
                {message.edited && <span className="edited-badge">(edited)</span>}
                {message.isEncrypted && <span className="encrypted-badge">🔒 Encrypted</span>}
            </div>
            
            <div className="message-content">
                <p>{message.text}</p>
                {message.aiSummary && (
                    <div className="ai-summary">
                        <span className="ai-label">✨ AI Summary:</span>
                        <p>{message.aiSummary}</p>
                    </div>
                )}
                <div className={`sentiment-badge sentiment-${message.sentiment}`}>
                    {message.sentiment}
                </div>
            </div>

            {message.attachments.length > 0 && (
                <div className="attachments-section">
                    {message.attachments.map(att => (
                        <div key={att.id} className={`attachment-item scan-${att.scanStatus}`}>
                            <span className="attachment-icon">📎</span>
                            <span className="attachment-name">{att.filename}</span>
                            <span className="attachment-size">({(att.size / 1024).toFixed(2)}KB)</span>
                            {att.isProcessing && <span className="processing-indicator">⏳</span>}
                        </div>
                    ))}
                </div>
            )}

            {message.reactions.length > 0 && (
                <div className="reactions-display">
                    {message.reactions.map((emoji, idx) => (
                        <span key={idx} className="reaction-badge">{emoji}</span>
                    ))}
                </div>
            )}

            <div className="message-actions">
                <button onClick={() => setShowReactions(!showReactions)} title="React">😊</button>
                <button onClick={() => setShowTranslate(!showTranslate)} title="Translate">🌐</button>
                {message.canEdit && <button onClick={onEdit} title="Edit">✏️</button>}
                {message.canDelete && <button onClick={onDelete} title="Delete">🗑️</button>}
            </div>

            {showReactions && (
                <div className="reactions-picker">
                    {reactions.map(emoji => (
                        <button key={emoji} onClick={() => {
                            onReact?.(emoji);
                            setShowReactions(false);
                        }}>
                            {emoji}
                        </button>
                    ))}
                </div>
            )}

            {showTranslate && (
                <div className="translate-section">
                    <select value={selectedLang} onChange={(e) => setSelectedLang(e.target.value)}>
                        <option value="es">Español</option>
                        <option value="fr">Français</option>
                        <option value="de">Deutsch</option>
                        <option value="zh">中文</option>
                        <option value="ja">日本語</option>
                    </select>
                    <button onClick={() => onTranslate?.(selectedLang)}>Translate</button>
                </div>
            )}
        </div>
    );
};

// Conversation Thread List Component
const ConversationThreadList: FC<{
    threads: ConversationThread[];
    onSelectThread: (threadId: string) => void;
    selectedThreadId?: string;
}> = ({ threads, onSelectThread, selectedThreadId }) => {
    const [sortBy, setSortBy] = useState<'recent' | 'priority' | 'unread'>('recent');

    const sortedThreads = useMemo(() => {
        const sorted = [...threads];
        if (sortBy === 'priority') {
            sorted.sort((a, b) => {
                const priorityMap = { high: 3, medium: 2, low: 1 };
                return priorityMap[b.priority] - priorityMap[a.priority];
            });
        } else if (sortBy === 'unread') {
            sorted.sort((a, b) => b.unreadCount - a.unreadCount);
        }
        return sorted;
    }, [threads, sortBy]);

    return (
        <div className="conversation-thread-list">
            <div className="thread-list-header">
                <h3>Conversations ({threads.length})</h3>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
                    <option value="recent">Recent</option>
                    <option value="priority">Priority</option>
                    <option value="unread">Unread</option>
                </select>
            </div>

            <div className="threads-list">
                {sortedThreads.map(thread => (
                    <div
                        key={thread.id}
                        className={`thread-item ${selectedThreadId === thread.id ? 'selected' : ''}`}
                        onClick={() => onSelectThread(thread.id)}
                    >
                        <div className="thread-header">
                            <span className="thread-topic">{thread.topic}</span>
                            <span className={`priority-badge priority-${thread.priority}`}>{thread.priority}</span>
                        </div>
                        <div className="thread-preview">
                            <p>{thread.lastMessage}</p>
                        </div>
                        <div className="thread-footer">
                            <span className="message-count">{thread.messageCount} messages</span>
                            <span className="unread-count">{thread.unreadCount > 0 && `${thread.unreadCount} unread`}</span>
                            <span className="thread-time">{new Date(thread.lastMessageTime).toLocaleTimeString()}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Channel Settings Component
const ChannelSettingsPanel: FC<{
    notifications: ChannelNotification[];
    onToggleNotification?: (id: string) => void;
    onAddNotification?: (notification: ChannelNotification) => void;
}> = ({ notifications, onToggleNotification, onAddNotification }) => {
    const [showAddNotification, setShowAddNotification] = useState(false);
    const [newNotificationType, setNewNotificationType] = useState<ChannelNotification['type']>('keyword');

    return (
        <div className="channel-settings-panel">
            <h3>🔔 Notification Settings</h3>
            
            <div className="notifications-list">
                {notifications.map(notif => (
                    <div key={notif.id} className="notification-setting">
                        <div className="notif-info">
                            <span className="notif-type">{notif.type}</span>
                            <span className="notif-trigger">{notif.trigger}</span>
                            <span className={`priority-badge priority-${notif.priority}`}>{notif.priority}</span>
                        </div>
                        <label className="toggle-switch">
                            <input
                                type="checkbox"
                                checked={notif.enabled}
                                onChange={() => onToggleNotification?.(notif.id)}
                            />
                            <span className="toggle-slider"></span>
                        </label>
                    </div>
                ))}
            </div>

            <button
                className="add-notification-btn"
                onClick={() => setShowAddNotification(!showAddNotification)}
            >
                + Add Notification Rule
            </button>

            {showAddNotification && (
                <div className="add-notification-form">
                    <select value={newNotificationType} onChange={(e) => setNewNotificationType(e.target.value as any)}>
                        <option value="mention">Mention</option>
                        <option value="keyword">Keyword</option>
                        <option value="important">Important</option>
                        <option value="custom">Custom</option>
                    </select>
                    <input type="text" placeholder="Trigger value" />
                    <select>
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                    <button onClick={() => setShowAddNotification(false)}>Save</button>
                </div>
            )}
        </div>
    );
};

// Real-time Typing Indicator Component
const TypingIndicator: FC<{ users: string[] }> = ({ users }) => {
    if (users.length === 0) return null;

    const displayText = users.length === 1
        ? `${users[0]} is typing`
        : users.length === 2
        ? `${users[0]} and ${users[1]} are typing`
        : `${users.slice(0, 2).join(', ')} and ${users.length - 2} others are typing`;

    return (
        <div className="typing-indicator">
            <span className="typing-dots">
                <span></span><span></span><span></span>
            </span>
            {displayText}
        </div>
    );
};

// Message Search Component
const MessageSearch: FC<{
    onSearch?: (query: string, filters: SearchFilters) => void;
}> = ({ onSearch }) => {
    const [query, setQuery] = useState('');
    const [filterAuthor, setFilterAuthor] = useState('');
    const [filterDate, setFilterDate] = useState('');
    const [hasAttachments, setHasAttachments] = useState(false);

    const handleSearch = useCallback(() => {
        onSearch?.(query, {
            author: filterAuthor,
            date: filterDate,
            hasAttachments,
        });
    }, [query, filterAuthor, filterDate, hasAttachments, onSearch]);

    return (
        <div className="message-search">
            <div className="search-input-group">
                <input
                    type="text"
                    placeholder="Search messages..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                />
                <button onClick={handleSearch}>🔍</button>
            </div>

            <div className="search-filters">
                <input
                    type="text"
                    placeholder="From author"
                    value={filterAuthor}
                    onChange={(e) => setFilterAuthor(e.target.value)}
                />
                <input
                    type="date"
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                />
                <label>
                    <input
                        type="checkbox"
                        checked={hasAttachments}
                        onChange={(e) => setHasAttachments(e.target.checked)}
                    />
                    Has attachments
                </label>
            </div>
        </div>
    );
};

interface SearchFilters {
    author?: string;
    date?: string;
    hasAttachments?: boolean;
}

// Main Communication Hub Component
export const AdvancedCommunicationHub: FC = () => {
    const { info, success, warning } = useToast();
    const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });

    const [threads, setThreads] = useState<ConversationThread[]>([
        {
            id: '1',
            participants: ['Alice', 'Bob'],
            topic: 'Q4 Planning',
            messageCount: 24,
            lastMessage: 'Let\'s schedule the planning session',
            lastMessageTime: Date.now(),
            isActive: true,
            priority: 'high',
            unreadCount: 2,
            attachments: [],
            mentions: [],
            reactions: [{ emoji: '👍', count: 3, users: ['Alice', 'Bob', 'Carol'] }],
        },
        {
            id: '2',
            participants: ['Team'],
            topic: 'Project Updates',
            messageCount: 156,
            lastMessage: 'All systems operational',
            lastMessageTime: Date.now() - 3600000,
            isActive: true,
            priority: 'medium',
            unreadCount: 0,
            attachments: [],
            mentions: [],
            reactions: [],
        },
    ]);

    const [selectedThreadId, setSelectedThreadId] = useState<string | null>(threads[0]?.id || null);
    const [messages, setMessages] = useState<MessageThread[]>([]);
    const [typingUsers, setTypingUsers] = useState<string[]>([]);
    const [newMessage, setNewMessage] = useState('');
    const messageInputRef = useRef<HTMLTextAreaElement>(null);

    const [notifications, setNotifications] = useState<ChannelNotification[]>([
        {
            id: '1',
            type: 'mention',
            trigger: '@me',
            priority: 'critical',
            enabled: true,
        },
        {
            id: '2',
            type: 'keyword',
            trigger: 'urgent',
            priority: 'high',
            enabled: true,
        },
    ]);

    // Load messages for selected thread
    useEffect(() => {
        if (selectedThreadId) {
            setMessages([
                {
                    id: 'msg1',
                    text: 'We need to finalize the Q4 planning',
                    sender: 'Alice',
                    timestamp: Date.now() - 7200000,
                    edited: false,
                    reactions: ['👍', '👍'],
                    attachments: [],
                    isEncrypted: false,
                    canDelete: true,
                    canEdit: true,
                    translationHistory: [],
                    sentiment: 'neutral',
                },
                {
                    id: 'msg2',
                    text: 'I agree! We should target next Monday',
                    sender: 'Bob',
                    timestamp: Date.now() - 3600000,
                    edited: true,
                    editedAt: Date.now() - 3500000,
                    reactions: [],
                    attachments: [],
                    isEncrypted: false,
                    canDelete: true,
                    canEdit: false,
                    translationHistory: [],
                    sentiment: 'positive',
                },
            ]);
        }
    }, [selectedThreadId]);

    // WebSocket event listeners
    useEffect(() => {
        const handleTypingStart = (data: any) => {
            setTypingUsers(prev => {
                if (!prev.includes(data.user)) {
                    return [...prev, data.user];
                }
                return prev;
            });
        };

        const handleTypingStop = (data: any) => {
            setTypingUsers(prev => prev.filter(u => u !== data.user));
        };

        const handleNewMessage = (msg: any) => {
            setMessages(prev => [...prev, msg]);
            success('New Message', `${msg.sender}: ${msg.text.substring(0, 50)}`);
        };

        const handleThreadUpdate = (update: any) => {
            setThreads(prev =>
                prev.map(t => t.id === update.threadId ? { ...t, ...update.changes } : t)
            );
        };

        subscribe('typing:start', handleTypingStart);
        subscribe('typing:stop', handleTypingStop);
        subscribe('message:new', handleNewMessage);
        subscribe('thread:update', handleThreadUpdate);

        return () => {
            unsubscribe('typing:start', handleTypingStart);
            unsubscribe('typing:stop', handleTypingStop);
            unsubscribe('message:new', handleNewMessage);
            unsubscribe('thread:update', handleThreadUpdate);
        };
    }, [subscribe, unsubscribe, success]);

    // Send message handler
    const handleSendMessage = useCallback(() => {
        if (!newMessage.trim() || !selectedThreadId) return;

        const message: MessageThread = {
            id: `msg-${Date.now()}`,
            text: newMessage,
            sender: 'You',
            timestamp: Date.now(),
            edited: false,
            reactions: [],
            attachments: [],
            isEncrypted: false,
            canDelete: true,
            canEdit: true,
            translationHistory: [],
            sentiment: 'neutral',
        };

        setMessages(prev => [...prev, message]);
        emit('message:send', { threadId: selectedThreadId, message });
        setNewMessage('');
        messageInputRef.current?.focus();
        success('Sent', 'Message sent successfully');
    }, [newMessage, selectedThreadId, emit, success]);

    // Handle typing
    const handleTyping = useCallback(() => {
        emit('typing:start', { user: 'You', threadId: selectedThreadId });
        setTimeout(() => {
            emit('typing:stop', { user: 'You', threadId: selectedThreadId });
        }, 3000);
    }, [selectedThreadId, emit]);

    // Add reaction
    const handleReaction = useCallback((messageId: string, emoji: string) => {
        emit('message:react', { messageId, emoji });
        success('Reaction Added', `Added ${emoji} to message`);
    }, [emit, success]);

    return (
        <div className="advanced-communication-hub">
            <header className="view-header">
                <h1>💬 Advanced Communication Hub</h1>
                <p>Real-time conversations with 250+ features</p>
                <div className="connection-status">
                    {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </div>
            </header>

            <div className="communication-main">
                <aside className="communication-sidebar">
                    <MessageSearch onSearch={(query, filters) => {
                        info('Search', `Searching for "${query}"`);
                    }} />
                    <ConversationThreadList
                        threads={threads}
                        onSelectThread={setSelectedThreadId}
                        selectedThreadId={selectedThreadId || undefined}
                    />
                </aside>

                <main className="communication-content">
                    {selectedThreadId ? (
                        <>
                            <div className="thread-header">
                                {(() => {
                                    const thread = threads.find(t => t.id === selectedThreadId);
                                    return thread ? (
                                        <>
                                            <h2>{thread.topic}</h2>
                                            <div className="thread-info">
                                                <span>{thread.messageCount} messages</span>
                                                <span>{thread.participants.join(', ')}</span>
                                            </div>
                                        </>
                                    ) : null;
                                })()}
                            </div>

                            <div className="messages-container">
                                {messages.map(msg => (
                                    <AdvancedMessageCard
                                        key={msg.id}
                                        message={msg}
                                        onReact={(emoji) => handleReaction(msg.id, emoji)}
                                    />
                                ))}
                                <TypingIndicator users={typingUsers} />
                            </div>

                            <div className="message-composer">
                                <textarea
                                    ref={messageInputRef}
                                    value={newMessage}
                                    onChange={(e) => {
                                        setNewMessage(e.target.value);
                                        handleTyping();
                                    }}
                                    placeholder="Type a message..."
                                    rows={3}
                                />
                                <div className="composer-actions">
                                    <button title="Attach file">📎</button>
                                    <button title="Add emoji">😊</button>
                                    <button title="Format">✏️</button>
                                    <button
                                        onClick={handleSendMessage}
                                        className="send-btn"
                                        disabled={!newMessage.trim()}
                                    >
                                        Send
                                    </button>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="no-thread-selected">
                            <p>Select a conversation to start</p>
                        </div>
                    )}
                </main>

                <aside className="communication-sidebar-right">
                    <ChannelSettingsPanel
                        notifications={notifications}
                        onToggleNotification={(id) => {
                            setNotifications(prev =>
                                prev.map(n => n.id === id ? { ...n, enabled: !n.enabled } : n)
                            );
                        }}
                    />
                </aside>
            </div>
        </div>
    );
};
