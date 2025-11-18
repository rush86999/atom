import React, { useState, useEffect, useCallback, FC } from 'react';
import { useWebSocket, useRealtimeSync } from '../hooks/useWebSocket';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

interface RealtimeMetric {
    id: string;
    name: string;
    value: number;
    unit: string;
    trend: 'up' | 'down' | 'stable';
    timestamp: number;
    history: { value: number; timestamp: number }[];
}

interface ActiveSession {
    userId: string;
    username: string;
    lastActivity: number;
    cursor?: { x: number; y: number };
    viewPort: string;
}

interface CollaborationEvent {
    id: string;
    type: 'edit' | 'comment' | 'mention' | 'reaction' | 'presence';
    user: string;
    content: string;
    timestamp: number;
    relatedUserId?: string;
}

// Metric Card Component
const MetricCard: FC<{ metric: RealtimeMetric }> = ({ metric }) => {
    const trendIcon = metric.trend === 'up' ? '📈' : metric.trend === 'down' ? '📉' : '➡️';
    const trendColor = metric.trend === 'up' ? '#10b981' : metric.trend === 'down' ? '#ef4444' : '#6b7280';

    return (
        <div className="metric-card">
            <div className="metric-header">
                <h4>{metric.name}</h4>
                <span style={{ color: trendColor }}>{trendIcon}</span>
            </div>
            <div className="metric-value">
                <span className="value">{metric.value}</span>
                <span className="unit">{metric.unit}</span>
            </div>
            <div className="metric-history">
                <svg viewBox="0 0 100 40" className="spark-line">
                    {metric.history.length > 1 && (
                        <polyline
                            points={metric.history
                                .map((point, i) => {
                                    const x = (i / (metric.history.length - 1)) * 100;
                                    const max = Math.max(...metric.history.map(p => p.value));
                                    const min = Math.min(...metric.history.map(p => p.value));
                                    const range = max - min || 1;
                                    const y = 40 - ((point.value - min) / range) * 30 - 5;
                                    return `${x},${y}`;
                                })
                                .join(' ')}
                            fill="none"
                            stroke="#3b82f6"
                            strokeWidth="1.5"
                        />
                    )}
                </svg>
            </div>
            <div className="metric-time">{new Date(metric.timestamp).toLocaleTimeString()}</div>
        </div>
    );
};

// Active Session Card Component
const ActiveSessionCard: FC<{ session: ActiveSession }> = ({ session }) => {
    return (
        <div className="session-card">
            <div className="session-avatar" style={{ background: `hsl(${session.userId.charCodeAt(0) * 10}, 70%, 50%)` }}>
                {session.username.charAt(0).toUpperCase()}
            </div>
            <div className="session-info">
                <h4>{session.username}</h4>
                <p className="session-status">
                    <span className="online-indicator"></span>
                    Active now
                </p>
                <p className="session-view">Viewing: {session.viewPort}</p>
            </div>
            <div className="session-cursor" style={{ left: session.cursor?.x, top: session.cursor?.y }}>
                👆
            </div>
        </div>
    );
};

// Collaboration Timeline Component
const CollaborationTimeline: FC<{ events: CollaborationEvent[] }> = ({ events }) => {
    return (
        <div className="collaboration-timeline">
            <h3>📍 Activity Timeline</h3>
            <div className="timeline-list">
                {events.slice(0, 10).map((event) => (
                    <div key={event.id} className="timeline-item">
                        <div className="timeline-dot" style={{ background: getEventColor(event.type) }}></div>
                        <div className="timeline-content">
                            <p className="timeline-text">
                                <strong>{event.user}</strong>
                                {' '}
                                {getEventDescription(event.type)}
                                {event.relatedUserId && <strong> @{event.relatedUserId}</strong>}
                            </p>
                            <p className="timeline-time">{formatTimeAgo(event.timestamp)}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Network Health Component
const NetworkHealth: FC<{ isConnected: boolean; latency: number; packetLoss: number }> = ({ isConnected, latency, packetLoss }) => {
    const healthStatus = isConnected
        ? packetLoss < 1 ? '✅ Excellent' : packetLoss < 5 ? '⚠️ Good' : '❌ Poor'
        : '❌ Disconnected';

    return (
        <div className="network-health">
            <h3>🌐 Network Health</h3>
            <div className="health-grid">
                <div className="health-item">
                    <label>Connection</label>
                    <div className="health-value">{isConnected ? 'Connected' : 'Disconnected'}</div>
                </div>
                <div className="health-item">
                    <label>Latency</label>
                    <div className="health-value">{latency}ms</div>
                </div>
                <div className="health-item">
                    <label>Packet Loss</label>
                    <div className="health-value">{packetLoss.toFixed(1)}%</div>
                </div>
                <div className="health-item">
                    <label>Status</label>
                    <div className="health-value">{healthStatus}</div>
                </div>
            </div>
        </div>
    );
};

export const AdvancedRealtimeHub: FC = () => {
    const { success } = useToast();
    const { subscribe, unsubscribe, isConnected, emit } = useWebSocket({ enabled: true });
    useRealtimeSync();
    const { tasks, messages, workflows } = useAppStore();

    const [metrics, setMetrics] = useState<RealtimeMetric[]>([
        {
            id: '1',
            name: 'Active Users',
            value: 12,
            unit: 'users',
            trend: 'up',
            timestamp: Date.now(),
            history: [
                { value: 8, timestamp: Date.now() - 60000 },
                { value: 10, timestamp: Date.now() - 45000 },
                { value: 12, timestamp: Date.now() },
            ],
        },
        {
            id: '2',
            name: 'Messages/min',
            value: 45,
            unit: 'msg/min',
            trend: 'stable',
            timestamp: Date.now(),
            history: [
                { value: 42, timestamp: Date.now() - 60000 },
                { value: 44, timestamp: Date.now() - 30000 },
                { value: 45, timestamp: Date.now() },
            ],
        },
        {
            id: '3',
            name: 'Sync Latency',
            value: 45,
            unit: 'ms',
            trend: 'down',
            timestamp: Date.now(),
            history: [
                { value: 120, timestamp: Date.now() - 60000 },
                { value: 75, timestamp: Date.now() - 30000 },
                { value: 45, timestamp: Date.now() },
            ],
        },
        {
            id: '4',
            name: 'Data Throughput',
            value: 2.3,
            unit: 'MB/s',
            trend: 'up',
            timestamp: Date.now(),
            history: [
                { value: 1.2, timestamp: Date.now() - 60000 },
                { value: 1.8, timestamp: Date.now() - 30000 },
                { value: 2.3, timestamp: Date.now() },
            ],
        },
    ]);

    const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([
        {
            userId: '1',
            username: 'Alice Johnson',
            lastActivity: Date.now(),
            viewPort: 'Dashboard',
            cursor: { x: 150, y: 100 },
        },
        {
            userId: '2',
            username: 'Bob Smith',
            lastActivity: Date.now() - 5000,
            viewPort: 'Tasks',
            cursor: { x: 300, y: 250 },
        },
        {
            userId: '3',
            username: 'Carol White',
            lastActivity: Date.now() - 15000,
            viewPort: 'Chat',
            cursor: { x: 200, y: 350 },
        },
    ]);

    const [collaborationEvents, setCollaborationEvents] = useState<CollaborationEvent[]>([
        {
            id: '1',
            type: 'edit',
            user: 'Alice',
            content: 'Updated task "Design Review"',
            timestamp: Date.now() - 30000,
        },
        {
            id: '2',
            type: 'comment',
            user: 'Bob',
            content: 'Commented on workflow',
            timestamp: Date.now() - 60000,
            relatedUserId: 'Alice',
        },
        {
            id: '3',
            type: 'mention',
            user: 'Carol',
            content: 'Mentioned you in Chat',
            timestamp: Date.now() - 120000,
            relatedUserId: 'You',
        },
    ]);

    const [latency, setLatency] = useState(45);
    const [packetLoss, setPacketLoss] = useState(0.5);

    // Update metrics in real-time
    useEffect(() => {
        const metricsInterval = setInterval(() => {
            setMetrics((prev) =>
                prev.map((metric) => {
                    const newValue = metric.value + (Math.random() - 0.5) * 10;
                    return {
                        ...metric,
                        value: Math.max(0, newValue),
                        trend: newValue > metric.value ? 'up' : newValue < metric.value ? 'down' : 'stable',
                        timestamp: Date.now(),
                        history: [...metric.history.slice(-19), { value: newValue, timestamp: Date.now() }],
                    };
                })
            );
        }, 5000);

        return () => clearInterval(metricsInterval);
    }, []);

    // Simulate latency changes
    useEffect(() => {
        const latencyInterval = setInterval(() => {
            setLatency((prev) => Math.max(10, Math.min(200, prev + (Math.random() - 0.5) * 20)));
            setPacketLoss((prev) => Math.max(0, Math.min(10, prev + (Math.random() - 0.5) * 0.5)));
        }, 3000);

        return () => clearInterval(latencyInterval);
    }, []);

    // Real-time event listeners
    useEffect(() => {
        const handleCursorMove = (data: any) => {
            setActiveSessions((prev) =>
                prev.map((session) =>
                    session.userId === data.userId
                        ? { ...session, cursor: data.position, lastActivity: Date.now() }
                        : session
                )
            );
        };

        const handleUserJoined = (data: any) => {
            setActiveSessions((prev) => [
                ...prev,
                {
                    userId: data.userId,
                    username: data.username,
                    lastActivity: Date.now(),
                    viewPort: data.viewPort || 'Dashboard',
                },
            ]);
            success('User Online', `${data.username} joined`);
        };

        const handleUserLeft = (data: any) => {
            setActiveSessions((prev) => prev.filter((s) => s.userId !== data.userId));
        };

        const handleCollaborationEvent = (data: any) => {
            const newEvent: CollaborationEvent = {
                id: `event-${Date.now()}`,
                type: data.type || 'edit',
                user: data.user,
                content: data.content,
                timestamp: Date.now(),
                relatedUserId: data.relatedUserId,
            };
            setCollaborationEvents((prev) => [newEvent, ...prev]);
        };

        subscribe('cursor:move', handleCursorMove);
        subscribe('user:joined', handleUserJoined);
        subscribe('user:left', handleUserLeft);
        subscribe('collaboration:event', handleCollaborationEvent);

        return () => {
            unsubscribe('cursor:move');
            unsubscribe('user:joined');
            unsubscribe('user:left');
            unsubscribe('collaboration:event');
        };
    }, [subscribe, unsubscribe, success]);

    const handleBroadcastMessage = useCallback(() => {
        emit('broadcast:message', {
            from: 'You',
            content: 'Real-time update broadcast',
            timestamp: Date.now(),
        });
        success('Broadcast Sent', 'Message sent to all active users');
    }, [emit, success]);

    const handleSyncRequest = useCallback(() => {
        emit('sync:request', {
            userId: 'current-user',
            timestamp: Date.now(),
            dataTypes: ['tasks', 'messages', 'calendar'],
        });
        success('Sync Initiated', 'Syncing all data...');
    }, [emit, success]);

    const handleHealthCheck = useCallback(() => {
        const startTime = Date.now();
        emit('health:check', { timestamp: startTime });
        success('Health Check', 'Checking connection health...');
    }, [emit, success]);

    return (
        <div className="advanced-realtime-hub">
            <header className="view-header">
                <h1>🚀 Advanced Real-Time Hub</h1>
                <p>Monitor live collaboration, metrics, and network health across your workspace.</p>
            </header>

            <div className="realtime-toolbar">
                <button onClick={handleBroadcastMessage} className="action-btn primary">
                    📢 Broadcast Message
                </button>
                <button onClick={handleSyncRequest} className="action-btn">
                    🔄 Sync All Data
                </button>
                <button onClick={handleHealthCheck} className="action-btn">
                    🏥 Health Check
                </button>
                <div className="connection-status">
                    <span className={`status-indicator ${isConnected ? 'online' : 'offline'}`}></span>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </div>
            </div>

            <div className="realtime-grid">
                {/* Metrics Section */}
                <section className="realtime-section metrics-section">
                    <h2>📊 Real-Time Metrics</h2>
                    <div className="metrics-grid">
                        {metrics.map((metric) => (
                            <MetricCard key={metric.id} metric={metric} />
                        ))}
                    </div>
                </section>

                {/* Active Sessions Section */}
                <section className="realtime-section sessions-section">
                    <h2>👥 Active Sessions ({activeSessions.length})</h2>
                    <div className="sessions-grid">
                        {activeSessions.map((session) => (
                            <ActiveSessionCard key={session.userId} session={session} />
                        ))}
                    </div>
                </section>

                {/* Network Health Section */}
                <section className="realtime-section health-section">
                    <NetworkHealth isConnected={isConnected} latency={latency} packetLoss={packetLoss} />
                </section>

                {/* Collaboration Timeline Section */}
                <section className="realtime-section timeline-section">
                    <CollaborationTimeline events={collaborationEvents} />
                </section>

                {/* Statistics Panel */}
                <section className="realtime-section stats-section">
                    <h3>📈 Current Statistics</h3>
                    <div className="stats-grid">
                        <div className="stat-item">
                            <label>Total Tasks</label>
                            <div className="stat-value">{tasks.length}</div>
                        </div>
                        <div className="stat-item">
                            <label>Active Workflows</label>
                            <div className="stat-value">{workflows.filter((w) => w.enabled).length}</div>
                        </div>
                        <div className="stat-item">
                            <label>Messages Today</label>
                            <div className="stat-value">{messages.length}</div>
                        </div>
                        <div className="stat-item">
                            <label>Collaborators</label>
                            <div className="stat-value">{activeSessions.length}</div>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
};

// Helper functions
function getEventColor(type: string): string {
    const colors: Record<string, string> = {
        edit: '#3b82f6',
        comment: '#8b5cf6',
        mention: '#ec4899',
        reaction: '#f59e0b',
        presence: '#10b981',
    };
    return colors[type] || '#6b7280';
}

function getEventDescription(type: string): string {
    const descriptions: Record<string, string> = {
        edit: 'edited',
        comment: 'commented on',
        mention: 'mentioned',
        reaction: 'reacted to',
        presence: 'joined the session',
    };
    return descriptions[type] || 'updated';
}

function formatTimeAgo(timestamp: number): string {
    const now = Date.now();
    const diff = now - timestamp;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) return `${seconds}s ago`;
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}
