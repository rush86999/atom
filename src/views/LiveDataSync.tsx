import React, { useState, useEffect, useCallback, FC } from 'react';
import { useWebSocket, useRealtimeSync } from '../hooks/useWebSocket';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

interface SyncStatus {
    dataType: string;
    lastSyncTime: number;
    itemCount: number;
    syncStatus: 'synced' | 'syncing' | 'failed';
    changesPending: number;
    syncSpeed: number; // items per second
}

interface ConflictItem {
    id: string;
    dataType: string;
    local: any;
    remote: any;
    timestamp: number;
    resolution: 'local' | 'remote' | 'manual' | null;
}

interface SyncLog {
    id: string;
    timestamp: number;
    action: string;
    dataType: string;
    itemsAffected: number;
    duration: number; // ms
    status: 'success' | 'failed' | 'partial';
}

// Sync Status Card Component
const SyncStatusCard: FC<{ status: SyncStatus; onManualSync: (dataType: string) => void }> = ({ status, onManualSync }) => {
    const statusColors = {
        synced: '#10b981',
        syncing: '#f59e0b',
        failed: '#ef4444',
    };

    const timeSinceSync = Date.now() - status.lastSyncTime;
    const syncTimeString =
        timeSinceSync < 60000
            ? `${Math.floor(timeSinceSync / 1000)}s ago`
            : `${Math.floor(timeSinceSync / 60000)}m ago`;

    return (
        <div className="sync-status-card">
            <div className="card-header">
                <h4>{status.dataType}</h4>
                <span className="status-badge" style={{ backgroundColor: statusColors[status.syncStatus] }}>
                    {status.syncStatus === 'syncing' ? '🔄' : status.syncStatus === 'synced' ? '✅' : '❌'}
                </span>
            </div>

            <div className="card-stats">
                <div className="stat">
                    <label>Items</label>
                    <span className="value">{status.itemCount}</span>
                </div>
                <div className="stat">
                    <label>Pending Changes</label>
                    <span className="value">{status.changesPending}</span>
                </div>
                <div className="stat">
                    <label>Sync Speed</label>
                    <span className="value">{status.syncSpeed.toFixed(2)} items/s</span>
                </div>
                <div className="stat">
                    <label>Last Sync</label>
                    <span className="value">{syncTimeString}</span>
                </div>
            </div>

            {status.changesPending > 0 && (
                <button onClick={() => onManualSync(status.dataType)} className="sync-btn">
                    🔄 Sync Now
                </button>
            )}
        </div>
    );
};

// Conflict Resolution Component
const ConflictResolver: FC<{ conflict: ConflictItem; onResolve: (id: string, resolution: 'local' | 'remote') => void }> = ({
    conflict,
    onResolve,
}) => {
    return (
        <div className="conflict-item">
            <div className="conflict-header">
                <h4>{conflict.dataType} Conflict</h4>
                <span className="conflict-id">{conflict.id.substring(0, 8)}</span>
            </div>

            <div className="conflict-comparison">
                <div className="version local">
                    <h5>Local Version</h5>
                    <pre>{JSON.stringify(conflict.local, null, 2)}</pre>
                    <button onClick={() => onResolve(conflict.id, 'local')} className="resolve-btn local">
                        ✓ Keep Local
                    </button>
                </div>

                <div className="conflict-divider">VS</div>

                <div className="version remote">
                    <h5>Remote Version</h5>
                    <pre>{JSON.stringify(conflict.remote, null, 2)}</pre>
                    <button onClick={() => onResolve(conflict.id, 'remote')} className="resolve-btn remote">
                        ✓ Use Remote
                    </button>
                </div>
            </div>

            <p className="conflict-time">Detected: {new Date(conflict.timestamp).toLocaleString()}</p>
        </div>
    );
};

// Sync Log Component
const SyncLogViewer: FC<{ logs: SyncLog[] }> = ({ logs }) => {
    return (
        <div className="sync-log-viewer">
            <h3>📋 Sync Activity Log</h3>
            <div className="log-table">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Data Type</th>
                            <th>Items</th>
                            <th>Duration</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.slice(0, 10).map((log) => (
                            <tr key={log.id}>
                                <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
                                <td>{log.action}</td>
                                <td>{log.dataType}</td>
                                <td>{log.itemsAffected}</td>
                                <td>{log.duration}ms</td>
                                <td>
                                    <span className={`status-badge status-${log.status}`}>
                                        {log.status === 'success' ? '✅' : log.status === 'failed' ? '❌' : '⚠️'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// Bandwidth Monitor Component
const BandwidthMonitor: FC<{ bandwidthHistory: number[] }> = ({ bandwidthHistory }) => {
    const max = Math.max(...bandwidthHistory, 1);

    return (
        <div className="bandwidth-monitor">
            <h3>📡 Sync Bandwidth Usage</h3>
            <div className="bandwidth-chart">
                {bandwidthHistory.slice(-50).map((value, i) => (
                    <div
                        key={i}
                        className="bandwidth-bar"
                        style={{
                            height: `${(value / max) * 100}%`,
                            backgroundColor: value > max * 0.8 ? '#ef4444' : value > max * 0.5 ? '#f59e0b' : '#10b981',
                        }}
                        title={`${value.toFixed(2)} MB/s`}
                    />
                ))}
            </div>
            <div className="bandwidth-stats">
                <span>Max: {Math.max(...bandwidthHistory).toFixed(2)} MB/s</span>
                <span>Avg: {(bandwidthHistory.reduce((a, b) => a + b, 0) / bandwidthHistory.length).toFixed(2)} MB/s</span>
            </div>
        </div>
    );
};

export const LiveDataSync: FC = () => {
    const { success, warning } = useToast();
    const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });
    useRealtimeSync();
    const { tasks, notes, workflows, messages } = useAppStore();

    const [syncStatuses, setSyncStatuses] = useState<SyncStatus[]>([
        {
            dataType: 'Tasks',
            lastSyncTime: Date.now() - 5000,
            itemCount: tasks.length,
            syncStatus: 'synced',
            changesPending: 0,
            syncSpeed: 45.2,
        },
        {
            dataType: 'Messages',
            lastSyncTime: Date.now() - 15000,
            itemCount: messages.length,
            syncStatus: 'synced',
            changesPending: 2,
            syncSpeed: 120.5,
        },
        {
            dataType: 'Notes',
            lastSyncTime: Date.now() - 30000,
            itemCount: notes.length,
            syncStatus: 'synced',
            changesPending: 1,
            syncSpeed: 32.8,
        },
        {
            dataType: 'Workflows',
            lastSyncTime: Date.now() - 45000,
            itemCount: workflows.length,
            syncStatus: 'synced',
            changesPending: 0,
            syncSpeed: 15.3,
        },
    ]);

    const [conflicts, setConflicts] = useState<ConflictItem[]>([
        {
            id: 'conflict-1',
            dataType: 'Task',
            local: { title: 'Update documentation', status: 'in_progress' },
            remote: { title: 'Update documentation', status: 'completed' },
            timestamp: Date.now() - 120000,
            resolution: null,
        },
    ]);

    const [syncLogs, setSyncLogs] = useState<SyncLog[]>([
        {
            id: '1',
            timestamp: Date.now() - 5000,
            action: 'Auto-sync',
            dataType: 'Tasks',
            itemsAffected: 3,
            duration: 245,
            status: 'success',
        },
        {
            id: '2',
            timestamp: Date.now() - 30000,
            action: 'Full Sync',
            dataType: 'All Data',
            itemsAffected: 127,
            duration: 1850,
            status: 'success',
        },
    ]);

    const [bandwidthHistory, setBandwidthHistory] = useState<number[]>(
        Array.from({ length: 50 }, () => Math.random() * 2)
    );

    const [syncMode, setSyncMode] = useState<'auto' | 'manual'>('auto');
    const [syncInterval, setSyncInterval] = useState(30000); // 30 seconds

    // Auto-sync simulation
    useEffect(() => {
        if (syncMode !== 'auto') return;

        const interval = setInterval(() => {
            handleAutoSync();
        }, syncInterval);

        return () => clearInterval(interval);
    }, [syncMode, syncInterval]);

    // Simulate bandwidth changes
    useEffect(() => {
        const interval = setInterval(() => {
            setBandwidthHistory((prev) => [...prev.slice(1), Math.random() * 2]);
        }, 500);

        return () => clearInterval(interval);
    }, []);

    const handleAutoSync = useCallback(() => {
        setSyncStatuses((prev) =>
            prev.map((status) => ({
                ...status,
                lastSyncTime: Date.now(),
                syncStatus: 'syncing' as const,
            }))
        );

        setTimeout(() => {
            setSyncStatuses((prev) =>
                prev.map((status) => ({
                    ...status,
                    syncStatus: 'synced' as const,
                }))
            );

            const log: SyncLog = {
                id: `log-${Date.now()}`,
                timestamp: Date.now(),
                action: 'Auto-sync',
                dataType: 'All Data',
                itemsAffected: tasks.length + messages.length + notes.length + workflows.length,
                duration: Math.random() * 500 + 100,
                status: 'success',
            };

            setSyncLogs((prev) => [log, ...prev]);
            success('Auto-Sync', 'All data synchronized');
        }, 1500);
    }, [tasks, messages, notes, workflows, success]);

    const handleManualSync = useCallback(
        (dataType: string) => {
            setSyncStatuses((prev) =>
                prev.map((status) =>
                    status.dataType === dataType ? { ...status, syncStatus: 'syncing' as const } : status
                )
            );

            setTimeout(() => {
                setSyncStatuses((prev) =>
                    prev.map((status) =>
                        status.dataType === dataType ? { ...status, syncStatus: 'synced' as const, lastSyncTime: Date.now() } : status
                    )
                );

                emit('sync:completed', { dataType, timestamp: Date.now() });
                success('Sync Completed', `${dataType} synchronized`);
            }, 1000);
        },
        [emit, success]
    );

    const handleResolveConflict = useCallback(
        (id: string, resolution: 'local' | 'remote') => {
            setConflicts((prev) => prev.filter((c) => c.id !== id));
            emit('conflict:resolved', { conflictId: id, resolution, timestamp: Date.now() });
            success('Conflict Resolved', `Used ${resolution} version`);
        },
        [emit, success]
    );

    const handleSyncAll = useCallback(() => {
        handleAutoSync();
    }, [handleAutoSync]);

    return (
        <div className="live-data-sync">
            <header className="view-header">
                <h1>⚡ Live Data Sync</h1>
                <p>Monitor and manage real-time data synchronization across devices and networks.</p>
            </header>

            <div className="sync-controls">
                <div className="control-group">
                    <label>Sync Mode</label>
                    <select value={syncMode} onChange={(e) => setSyncMode(e.target.value as 'auto' | 'manual')}>
                        <option value="auto">Auto</option>
                        <option value="manual">Manual</option>
                    </select>
                </div>

                {syncMode === 'auto' && (
                    <div className="control-group">
                        <label>Interval (seconds)</label>
                        <input
                            type="number"
                            min="5"
                            max="300"
                            value={syncInterval / 1000}
                            onChange={(e) => setSyncInterval(parseInt(e.target.value) * 1000)}
                        />
                    </div>
                )}

                <button onClick={handleSyncAll} className="sync-btn-primary">
                    🔄 Sync All Now
                </button>

                <div className="connection-status">
                    {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </div>
            </div>

            {/* Conflicts Section */}
            {conflicts.length > 0 && (
                <section className="conflicts-section">
                    <h2>⚠️ Sync Conflicts ({conflicts.length})</h2>
                    <div className="conflicts-list">
                        {conflicts.map((conflict) => (
                            <ConflictResolver
                                key={conflict.id}
                                conflict={conflict}
                                onResolve={handleResolveConflict}
                            />
                        ))}
                    </div>
                </section>
            )}

            {/* Sync Status Section */}
            <section className="sync-status-section">
                <h2>📊 Sync Status Overview</h2>
                <div className="sync-status-grid">
                    {syncStatuses.map((status) => (
                        <SyncStatusCard
                            key={status.dataType}
                            status={status}
                            onManualSync={handleManualSync}
                        />
                    ))}
                </div>
            </section>

            {/* Bandwidth Monitor */}
            <section className="bandwidth-section">
                <BandwidthMonitor bandwidthHistory={bandwidthHistory} />
            </section>

            {/* Sync Logs */}
            <section className="logs-section">
                <SyncLogViewer logs={syncLogs} />
            </section>

            {/* Sync Statistics */}
            <section className="stats-section">
                <h2>📈 Sync Statistics</h2>
                <div className="stats-grid">
                    <div className="stat-card">
                        <label>Total Items Synced</label>
                        <div className="stat-value">
                            {syncStatuses.reduce((sum, status) => sum + status.itemCount, 0)}
                        </div>
                    </div>
                    <div className="stat-card">
                        <label>Pending Changes</label>
                        <div className="stat-value">
                            {syncStatuses.reduce((sum, status) => sum + status.changesPending, 0)}
                        </div>
                    </div>
                    <div className="stat-card">
                        <label>Average Sync Speed</label>
                        <div className="stat-value">
                            {(syncStatuses.reduce((sum, status) => sum + status.syncSpeed, 0) / syncStatuses.length).toFixed(1)}
                        </div>
                        <span className="stat-unit">items/s</span>
                    </div>
                    <div className="stat-card">
                        <label>Success Rate</label>
                        <div className="stat-value">
                            {(
                                (syncLogs.filter((log) => log.status === 'success').length / syncLogs.length) *
                                100
                            ).toFixed(0)}%
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
};
