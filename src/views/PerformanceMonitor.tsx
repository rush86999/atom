import React, { useState, useEffect, useCallback, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

interface PerformanceMetric {
    timestamp: number;
    cpu: number;
    memory: number;
    network: number;
    renderTime: number;
    apiLatency: number;
}

interface PerformanceAlert {
    id: string;
    type: 'warning' | 'critical' | 'info';
    title: string;
    description: string;
    timestamp: number;
    metric: string;
    threshold: number;
    current: number;
}

interface PageLoadTiming {
    dns: number;
    tcp: number;
    ttfb: number; // Time to first byte
    firstPaint: number;
    firstContentfulPaint: number;
    loadComplete: number;
}

// Performance Chart Component
const PerformanceChart: FC<{ data: PerformanceMetric[]; metric: keyof PerformanceMetric; title: string; unit: string }> = ({
    data,
    metric,
    title,
    unit,
}) => {
    const maxValue = Math.max(...data.map((d) => (d[metric] as number) || 0), 1);
    const minValue = Math.min(...data.map((d) => (d[metric] as number) || 0), 0);

    return (
        <div className="performance-chart">
            <h3>{title}</h3>
            <div className="chart-container">
                <svg viewBox="0 0 500 150" className="chart-svg">
                    {/* Grid */}
                    {[0, 25, 50, 75, 100].map((i) => (
                        <line key={`grid-${i}`} x1="40" x2="490" y1={150 - (i / 100) * 130 + 10} y2={150 - (i / 100) * 130 + 10} stroke="#e5e7eb" strokeDasharray="5,5" />
                    ))}

                    {/* Axis */}
                    <line x1="40" y1="10" x2="40" y2="140" stroke="#374151" strokeWidth="2" />
                    <line x1="40" y1="140" x2="490" y2="140" stroke="#374151" strokeWidth="2" />

                    {/* Data line */}
                    {data.length > 1 && (
                        <polyline
                            points={data
                                .map((point, i) => {
                                    const x = 40 + (i / (data.length - 1)) * 450;
                                    const range = maxValue - minValue || 1;
                                    const y = 140 - (((point[metric] as number) - minValue) / range) * 130;
                                    return `${x},${y}`;
                                })
                                .join(' ')}
                            fill="none"
                            stroke="#3b82f6"
                            strokeWidth="2"
                        />
                    )}

                    {/* Points */}
                    {data.map((point, i) => {
                        const x = 40 + (i / (data.length - 1)) * 450;
                        const range = maxValue - minValue || 1;
                        const y = 140 - (((point[metric] as number) - minValue) / range) * 130;
                        return <circle key={`point-${i}`} cx={x} cy={y} r="3" fill="#3b82f6" />;
                    })}
                </svg>
            </div>
            <div className="chart-stats">
                <span>Max: {maxValue.toFixed(2)}{unit}</span>
                <span>Min: {minValue.toFixed(2)}{unit}</span>
                <span>Avg: {(data.reduce((a, b) => a + (b[metric] as number), 0) / data.length).toFixed(2)}{unit}</span>
            </div>
        </div>
    );
};

// Alert Component
const AlertItem: FC<{ alert: PerformanceAlert; onDismiss: (id: string) => void }> = ({ alert, onDismiss }) => {
    const iconMap = {
        critical: '🔴',
        warning: '🟡',
        info: '🔵',
    };

    const bgMap = {
        critical: 'alert-critical',
        warning: 'alert-warning',
        info: 'alert-info',
    };

    return (
        <div className={`alert-item ${bgMap[alert.type]}`}>
            <div className="alert-icon">{iconMap[alert.type]}</div>
            <div className="alert-content">
                <h4>{alert.title}</h4>
                <p>{alert.description}</p>
                <p className="alert-details">
                    {alert.metric}: {alert.current.toFixed(2)} / {alert.threshold.toFixed(2)}
                </p>
            </div>
            <button onClick={() => onDismiss(alert.id)} className="alert-close">
                ✕
            </button>
        </div>
    );
};

// Page Load Waterfall Chart
const LoadWaterfall: FC<{ timing: PageLoadTiming }> = ({ timing }) => {
    const total = Object.values(timing).reduce((a, b) => a + b, 0);
    const phases = [
        { label: 'DNS', duration: timing.dns, color: '#3b82f6' },
        { label: 'TCP', duration: timing.tcp, color: '#8b5cf6' },
        { label: 'TTFB', duration: timing.ttfb, color: '#ec4899' },
        { label: 'FP', duration: timing.firstPaint, color: '#f59e0b' },
        { label: 'FCP', duration: timing.firstContentfulPaint, color: '#10b981' },
        { label: 'Load', duration: timing.loadComplete, color: '#06b6d4' },
    ];

    return (
        <div className="load-waterfall">
            <h3>⏱️ Page Load Waterfall</h3>
            <div className="waterfall-chart">
                {phases.map((phase) => (
                    <div key={phase.label} className="waterfall-item">
                        <span className="phase-label">{phase.label}</span>
                        <div className="phase-bar-container">
                            <div
                                className="phase-bar"
                                style={{
                                    width: `${(phase.duration / total) * 100}%`,
                                    backgroundColor: phase.color,
                                }}
                            >
                                {phase.duration > 50 && <span className="phase-duration">{phase.duration}ms</span>}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            <p className="total-time">Total: {total}ms</p>
        </div>
    );
};

// Performance Summary Card
const PerformanceSummary: FC<{ metrics: PerformanceMetric[] }> = ({ metrics }) => {
    const latest = metrics[metrics.length - 1];

    const getScore = (metric: number, max: number): string => {
        const percentage = (metric / max) * 100;
        if (percentage < 20) return '🟢 Excellent';
        if (percentage < 40) return '🟡 Good';
        if (percentage < 60) return '🟠 Fair';
        return '🔴 Poor';
    };

    return (
        <div className="performance-summary">
            <h3>📊 Performance Summary</h3>
            <div className="summary-grid">
                <div className="summary-item">
                    <label>CPU Usage</label>
                    <div className="summary-value">{latest?.cpu.toFixed(1)}%</div>
                    <div className="summary-status">{getScore(latest?.cpu || 0, 100)}</div>
                </div>
                <div className="summary-item">
                    <label>Memory Usage</label>
                    <div className="summary-value">{latest?.memory.toFixed(1)}%</div>
                    <div className="summary-status">{getScore(latest?.memory || 0, 100)}</div>
                </div>
                <div className="summary-item">
                    <label>Network Bandwidth</label>
                    <div className="summary-value">{latest?.network.toFixed(2)} MB/s</div>
                    <div className="summary-status">{getScore(latest?.network || 0, 10)}</div>
                </div>
                <div className="summary-item">
                    <label>Render Time</label>
                    <div className="summary-value">{latest?.renderTime.toFixed(2)}ms</div>
                    <div className="summary-status">{latest?.renderTime && latest.renderTime < 16 ? '🟢 60 FPS' : '🟡 <60 FPS'}</div>
                </div>
            </div>
        </div>
    );
};

export const PerformanceMonitor: FC = () => {
    const { success, warning } = useToast();
    const { emit, isConnected } = useWebSocket({ enabled: true });

    const [metrics, setMetrics] = useState<PerformanceMetric[]>([
        {
            timestamp: Date.now() - 30000,
            cpu: 15,
            memory: 35,
            network: 2.1,
            renderTime: 12,
            apiLatency: 85,
        },
        {
            timestamp: Date.now() - 20000,
            cpu: 22,
            memory: 42,
            network: 2.5,
            renderTime: 14,
            apiLatency: 92,
        },
        {
            timestamp: Date.now() - 10000,
            cpu: 18,
            memory: 38,
            network: 2.3,
            renderTime: 13,
            apiLatency: 78,
        },
        {
            timestamp: Date.now(),
            cpu: 25,
            memory: 45,
            network: 2.8,
            renderTime: 15,
            apiLatency: 95,
        },
    ]);

    const [alerts, setAlerts] = useState<PerformanceAlert[]>([
        {
            id: '1',
            type: 'warning',
            title: 'High Memory Usage',
            description: 'Memory usage has exceeded 40% threshold',
            timestamp: Date.now() - 5000,
            metric: 'Memory',
            threshold: 40,
            current: 45,
        },
    ]);

    const [pageLoadTiming] = useState<PageLoadTiming>({
        dns: 45,
        tcp: 120,
        ttfb: 280,
        firstPaint: 150,
        firstContentfulPaint: 280,
        loadComplete: 1200,
    });

    const [isMonitoring, setIsMonitoring] = useState(true);
    const [autoOptimize, setAutoOptimize] = useState(false);

    // Simulate performance metrics updates
    useEffect(() => {
        if (!isMonitoring) return;

        const interval = setInterval(() => {
            setMetrics((prev) => {
                const newMetric: PerformanceMetric = {
                    timestamp: Date.now(),
                    cpu: Math.max(5, Math.min(90, prev[prev.length - 1].cpu + (Math.random() - 0.5) * 20)),
                    memory: Math.max(10, Math.min(95, prev[prev.length - 1].memory + (Math.random() - 0.5) * 15)),
                    network: Math.max(0.5, Math.min(10, prev[prev.length - 1].network + (Math.random() - 0.5) * 1)),
                    renderTime: Math.max(5, Math.min(50, prev[prev.length - 1].renderTime + (Math.random() - 0.5) * 10)),
                    apiLatency: Math.max(20, Math.min(500, prev[prev.length - 1].apiLatency + (Math.random() - 0.5) * 50)),
                };

                // Keep only last 100 data points
                return [...prev.slice(-99), newMetric];
            });

            // Check for alerts
            setMetrics((prev) => {
                const latest = prev[prev.length - 1];
                if (latest.memory > 80) {
                    const newAlert: PerformanceAlert = {
                        id: `alert-${Date.now()}`,
                        type: 'critical',
                        title: 'Critical Memory Usage',
                        description: 'Memory usage is critically high',
                        timestamp: Date.now(),
                        metric: 'Memory',
                        threshold: 80,
                        current: latest.memory,
                    };
                    setAlerts((prev) => [newAlert, ...prev]);
                }
                return prev;
            });
        }, 3000);

        return () => clearInterval(interval);
    }, [isMonitoring]);

    const handleDismissAlert = useCallback((id: string) => {
        setAlerts((prev) => prev.filter((a) => a.id !== id));
    }, []);

    const handleOptimize = useCallback(() => {
        emit('performance:optimize', { metrics: metrics[metrics.length - 1] });
        success('Optimization', 'Performance optimization initiated');
    }, [emit, metrics, success]);

    const handleExportMetrics = useCallback(() => {
        const csv = [
            ['Timestamp', 'CPU %', 'Memory %', 'Network MB/s', 'Render ms', 'API Latency ms'].join(','),
            ...metrics.map((m) => [m.timestamp, m.cpu, m.memory, m.network, m.renderTime, m.apiLatency].join(',')),
        ].join('\n');

        const element = document.createElement('a');
        const file = new Blob([csv], { type: 'text/csv' });
        element.href = URL.createObjectURL(file);
        element.download = `performance-metrics-${Date.now()}.csv`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
        success('Exported', 'Performance metrics exported as CSV');
    }, [metrics, success]);

    const handleClearAlerts = useCallback(() => {
        setAlerts([]);
        success('Cleared', 'All alerts dismissed');
    }, [success]);

    return (
        <div className="performance-monitor">
            <header className="view-header">
                <h1>🎯 Performance Monitor</h1>
                <p>Real-time system performance tracking and optimization.</p>
            </header>

            <div className="monitor-toolbar">
                <button
                    onClick={() => setIsMonitoring(!isMonitoring)}
                    className={`monitor-btn ${isMonitoring ? 'active' : ''}`}
                >
                    {isMonitoring ? '⏸️ Pause' : '▶️ Resume'}
                </button>
                <button onClick={handleOptimize} className="monitor-btn primary">
                    ⚡ Optimize
                </button>
                <button onClick={handleExportMetrics} className="monitor-btn">
                    📊 Export
                </button>
                <button onClick={handleClearAlerts} className="monitor-btn">
                    🗑️ Clear Alerts
                </button>
                <label className="auto-optimize-toggle">
                    <input type="checkbox" checked={autoOptimize} onChange={(e) => setAutoOptimize(e.target.checked)} />
                    Auto Optimize
                </label>
                <div className="connection-indicator">
                    {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </div>
            </div>

            {/* Alerts Section */}
            {alerts.length > 0 && (
                <section className="alerts-section">
                    <h2>⚠️ Alerts ({alerts.length})</h2>
                    <div className="alerts-list">
                        {alerts.slice(0, 5).map((alert) => (
                            <AlertItem key={alert.id} alert={alert} onDismiss={handleDismissAlert} />
                        ))}
                    </div>
                </section>
            )}

            {/* Performance Summary */}
            <PerformanceSummary metrics={metrics} />

            {/* Charts Grid */}
            <div className="charts-grid">
                <PerformanceChart data={metrics} metric="cpu" title="CPU Usage" unit="%" />
                <PerformanceChart data={metrics} metric="memory" title="Memory Usage" unit="%" />
                <PerformanceChart data={metrics} metric="network" title="Network Bandwidth" unit=" MB/s" />
                <PerformanceChart data={metrics} metric="renderTime" title="Render Time" unit=" ms" />
                <PerformanceChart data={metrics} metric="apiLatency" title="API Latency" unit=" ms" />
            </div>

            {/* Page Load Waterfall */}
            <LoadWaterfall timing={pageLoadTiming} />

            {/* Detailed Metrics */}
            <section className="detailed-metrics">
                <h2>🔬 Detailed Metrics</h2>
                <div className="metrics-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>CPU %</th>
                                <th>Memory %</th>
                                <th>Network MB/s</th>
                                <th>Render ms</th>
                                <th>API Latency ms</th>
                            </tr>
                        </thead>
                        <tbody>
                            {metrics
                                .slice(-10)
                                .reverse()
                                .map((metric, i) => (
                                    <tr key={i}>
                                        <td>{new Date(metric.timestamp).toLocaleTimeString()}</td>
                                        <td>{metric.cpu.toFixed(1)}</td>
                                        <td>{metric.memory.toFixed(1)}</td>
                                        <td>{metric.network.toFixed(2)}</td>
                                        <td>{metric.renderTime.toFixed(2)}</td>
                                        <td>{metric.apiLatency.toFixed(0)}</td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* Recommendations */}
            <section className="recommendations-section">
                <h2>💡 Recommendations</h2>
                <div className="recommendations-list">
                    {metrics[metrics.length - 1].memory > 50 && (
                        <div className="recommendation-item">
                            <span className="recommendation-icon">💾</span>
                            <p>High memory usage detected. Consider clearing cache or closing unused tabs.</p>
                        </div>
                    )}
                    {metrics[metrics.length - 1].renderTime > 16 && (
                        <div className="recommendation-item">
                            <span className="recommendation-icon">⚡</span>
                            <p>Render time exceeds 16ms. This may impact frame rates. Optimize rendering logic.</p>
                        </div>
                    )}
                    {metrics[metrics.length - 1].apiLatency > 200 && (
                        <div className="recommendation-item">
                            <span className="recommendation-icon">🌐</span>
                            <p>API latency is high. Check network connection or server response times.</p>
                        </div>
                    )}
                    {metrics[metrics.length - 1].cpu > 75 && (
                        <div className="recommendation-item">
                            <span className="recommendation-icon">🔥</span>
                            <p>CPU usage is high. Consider reducing the number of active processes.</p>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
};
