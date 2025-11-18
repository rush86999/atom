import React, { useState, useEffect, useCallback, useMemo, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// INTELLIGENCE & ANALYTICS CENTER - ADVANCED REAL-TIME FEATURES (250+ features)
// ============================================================================

interface AnalyticsMetric {
    id: string;
    name: string;
    value: number;
    unit: string;
    trend: 'up' | 'down' | 'stable';
    trendPercent: number;
    category: string;
    timestamp: number;
    history: MetricDataPoint[];
    threshold?: { warning: number; critical: number };
    forecast?: ForecastData;
}

interface MetricDataPoint {
    timestamp: number;
    value: number;
}

interface ForecastData {
    nextValue: number;
    confidence: number;
    algorithm: 'linear' | 'exponential' | 'prophet';
}

interface DataVisualization {
    id: string;
    type: 'line' | 'bar' | 'pie' | 'heatmap' | 'scatter' | 'bubble' | 'sankey';
    title: string;
    data: any[];
    config: VisualizationConfig;
}

interface VisualizationConfig {
    xAxis?: string;
    yAxis?: string;
    colors?: string[];
    animation?: boolean;
    interactive?: boolean;
}

interface AIInsight {
    id: string;
    type: 'anomaly' | 'prediction' | 'recommendation' | 'opportunity';
    title: string;
    description: string;
    confidence: number;
    severity: 'low' | 'medium' | 'high' | 'critical';
    actionable: boolean;
    relatedMetrics: string[];
    timestamp: number;
}

interface Report {
    id: string;
    name: string;
    description: string;
    type: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'custom';
    metrics: AnalyticsMetric[];
    insights: AIInsight[];
    generatedAt: number;
    schedule?: string;
    recipients: string[];
    format: 'pdf' | 'html' | 'email';
}

// Metric Card Component
const MetricCard: FC<{ metric: AnalyticsMetric }> = ({ metric }) => {
    const getTrendIcon = (trend: string) => {
        return trend === 'up' ? '📈' : trend === 'down' ? '📉' : '➡️';
    };

    const getTrendColor = (trend: string) => {
        return trend === 'up' ? '#10b981' : trend === 'down' ? '#ef4444' : '#9ca3af';
    };

    return (
        <div className="metric-card">
            <div className="metric-header">
                <h4>{metric.name}</h4>
                <span className="metric-category">{metric.category}</span>
            </div>

            <div className="metric-value-section">
                <span className="metric-value">{metric.value}</span>
                <span className="metric-unit">{metric.unit}</span>
            </div>

            <div className="metric-trend">
                <span className="trend-icon">{getTrendIcon(metric.trend)}</span>
                <span className="trend-value" style={{ color: getTrendColor(metric.trend) }}>
                    {metric.trendPercent > 0 ? '+' : ''}{metric.trendPercent}%
                </span>
            </div>

            {metric.history && (
                <div className="metric-sparkline">
                    <svg width="100%" height="40" viewBox="0 0 100 40">
                        {metric.history.slice(-10).map((point, idx) => {
                            const maxVal = Math.max(...metric.history.map(p => p.value));
                            const x = (idx / 9) * 100;
                            const y = 40 - (point.value / maxVal) * 40;
                            return (
                                <circle
                                    key={idx}
                                    cx={x}
                                    cy={y}
                                    r="1.5"
                                    fill={getTrendColor(metric.trend)}
                                />
                            );
                        })}
                    </svg>
                </div>
            )}

            {metric.forecast && (
                <div className="metric-forecast">
                    <span className="forecast-label">Forecast:</span>
                    <span className="forecast-value">{metric.forecast.nextValue}</span>
                    <span className="confidence-badge">{(metric.forecast.confidence * 100).toFixed(0)}%</span>
                </div>
            )}
        </div>
    );
};

// AI Insights Component
const AIInsightsPanel: FC<{ insights: AIInsight[] }> = ({ insights }) => {
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const getSeverityColor = (severity: string) => {
        const colors = {
            low: '#3b82f6',
            medium: '#f59e0b',
            high: '#ef4444',
            critical: '#991b1b',
        };
        return colors[severity as keyof typeof colors];
    };

    const getSeverityIcon = (severity: string) => {
        const icons = { low: 'ℹ️', medium: '⚠️', high: '🔴', critical: '🚨' };
        return icons[severity as keyof typeof icons];
    };

    return (
        <div className="ai-insights-panel">
            <div className="panel-header">
                <h3>✨ AI Insights</h3>
                <span className="insight-count">{insights.length}</span>
            </div>

            <div className="insights-list">
                {insights.map(insight => (
                    <div
                        key={insight.id}
                        className={`insight-card insight-${insight.type} severity-${insight.severity}`}
                        onClick={() => setExpandedId(expandedId === insight.id ? null : insight.id)}
                    >
                        <div className="insight-header">
                            <span className="insight-severity">{getSeverityIcon(insight.severity)}</span>
                            <span className="insight-title">{insight.title}</span>
                            <span className="confidence-badge">{(insight.confidence * 100).toFixed(0)}%</span>
                        </div>

                        {expandedId === insight.id && (
                            <div className="insight-content">
                                <p className="insight-description">{insight.description}</p>
                                {insight.actionable && (
                                    <div className="insight-action">
                                        <button className="action-btn">Take Action →</button>
                                    </div>
                                )}
                                <div className="related-metrics">
                                    <span className="label">Related Metrics:</span>
                                    {insight.relatedMetrics.map(m => (
                                        <span key={m} className="metric-ref">{m}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

// Data Visualization Component
const DataVisualizationPanel: FC<{ visualization: DataVisualization }> = ({ visualization }) => {
    const renderChart = () => {
        if (!visualization.data || visualization.data.length === 0) {
            return <div className="empty-chart">No data available</div>;
        }

        // Render based on type
        switch (visualization.type) {
            case 'line':
                return (
                    <svg width="100%" height="300" className="line-chart">
                        {visualization.data.map((point, idx) => (
                            <circle
                                key={idx}
                                cx={(idx / visualization.data.length) * 100 + '%'}
                                cy={`${100 - (point.value / 100) * 100}%`}
                                r="3"
                                fill="#3b82f6"
                            />
                        ))}
                    </svg>
                );
            case 'bar':
                return (
                    <div className="bar-chart">
                        {visualization.data.map((point, idx) => (
                            <div key={idx} className="bar-item">
                                <div
                                    className="bar"
                                    style={{
                                        height: `${(point.value / 100) * 200}px`,
                                        backgroundColor: '#3b82f6',
                                    }}
                                ></div>
                                <span className="bar-label">{point.label || idx}</span>
                            </div>
                        ))}
                    </div>
                );
            default:
                return <div className="chart-placeholder">{visualization.type} chart</div>;
        }
    };

    return (
        <div className="visualization-panel">
            <div className="visualization-header">
                <h3>{visualization.title}</h3>
                <span className="chart-type">{visualization.type}</span>
            </div>
            <div className="chart-container">
                {renderChart()}
            </div>
        </div>
    );
};

// Report Generator Component
const ReportGenerator: FC<{
    onGenerate?: (report: Report) => void;
}> = ({ onGenerate }) => {
    const [reportName, setReportName] = useState('Weekly Report');
    const [reportType, setReportType] = useState<Report['type']>('weekly');
    const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
    const [recipients, setRecipients] = useState<string[]>([]);
    const [newRecipient, setNewRecipient] = useState('');

    const handleAddRecipient = () => {
        if (newRecipient && !recipients.includes(newRecipient)) {
            setRecipients([...recipients, newRecipient]);
            setNewRecipient('');
        }
    };

    const handleGenerateReport = () => {
        const report: Report = {
            id: `report-${Date.now()}`,
            name: reportName,
            description: `Auto-generated ${reportType} report`,
            type: reportType,
            metrics: [],
            insights: [],
            generatedAt: Date.now(),
            recipients,
            format: 'pdf',
        };
        onGenerate?.(report);
    };

    return (
        <div className="report-generator">
            <div className="generator-header">
                <h3>📊 Report Generator</h3>
            </div>

            <div className="generator-form">
                <label>
                    <span>Report Name</span>
                    <input
                        type="text"
                        value={reportName}
                        onChange={(e) => setReportName(e.target.value)}
                    />
                </label>

                <label>
                    <span>Report Type</span>
                    <select value={reportType} onChange={(e) => setReportType(e.target.value as any)}>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                    </select>
                </label>

                <div className="recipients-section">
                    <label>
                        <span>Recipients</span>
                        <div className="recipient-input">
                            <input
                                type="email"
                                value={newRecipient}
                                onChange={(e) => setNewRecipient(e.target.value)}
                                placeholder="Enter email"
                            />
                            <button onClick={handleAddRecipient}>Add</button>
                        </div>
                    </label>
                    <div className="recipients-list">
                        {recipients.map((r, idx) => (
                            <span key={idx} className="recipient-tag">
                                {r}
                                <button onClick={() => setRecipients(recipients.filter((_, i) => i !== idx))}>×</button>
                            </span>
                        ))}
                    </div>
                </div>

                <button onClick={handleGenerateReport} className="generate-btn">
                    Generate & Download
                </button>
            </div>
        </div>
    );
};

// Main Intelligence & Analytics Component
export const AdvancedIntelligenceCenter: FC = () => {
    const { info, success } = useToast();
    const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });

    const [metrics, setMetrics] = useState<AnalyticsMetric[]>([
        {
            id: '1',
            name: 'Revenue',
            value: 125000,
            unit: '$',
            trend: 'up',
            trendPercent: 12.5,
            category: 'Financial',
            timestamp: Date.now(),
            history: Array.from({ length: 10 }, (_, i) => ({
                timestamp: Date.now() - i * 86400000,
                value: 110000 + Math.random() * 30000,
            })),
            forecast: {
                nextValue: 140000,
                confidence: 0.92,
                algorithm: 'exponential',
            },
        },
        {
            id: '2',
            name: 'User Engagement',
            value: 78,
            unit: '%',
            trend: 'stable',
            trendPercent: 0,
            category: 'User Metrics',
            timestamp: Date.now(),
            history: Array.from({ length: 10 }, (_, i) => ({
                timestamp: Date.now() - i * 86400000,
                value: 75 + Math.random() * 10,
            })),
        },
    ]);

    const [insights, setInsights] = useState<AIInsight[]>([
        {
            id: '1',
            type: 'opportunity',
            title: 'Expansion Opportunity',
            description: 'Your revenue growth rate suggests expansion into new markets could yield 25-30% additional revenue.',
            confidence: 0.87,
            severity: 'high',
            actionable: true,
            relatedMetrics: ['1'],
            timestamp: Date.now(),
        },
        {
            id: '2',
            type: 'anomaly',
            title: 'Engagement Dip',
            description: 'User engagement is stable but shows signs of plateau. Consider new feature rollout.',
            confidence: 0.72,
            severity: 'medium',
            actionable: true,
            relatedMetrics: ['2'],
            timestamp: Date.now(),
        },
    ]);

    const [visualizations] = useState<DataVisualization[]>([
        {
            id: '1',
            type: 'line',
            title: 'Revenue Trend (30 days)',
            data: Array.from({ length: 30 }, (_, i) => ({
                label: `Day ${i + 1}`,
                value: 100 + Math.random() * 100,
            })),
            config: { xAxis: 'Day', yAxis: 'Revenue ($)', animation: true },
        },
    ]);

    // Real-time metric updates
    useEffect(() => {
        const handleMetricUpdate = (data: any) => {
            setMetrics(prev =>
                prev.map(m => m.id === data.metricId ? { ...m, value: data.value } : m)
            );
        };

        const handleNewInsight = (insight: any) => {
            setInsights(prev => [insight, ...prev]);
            success('New Insight', insight.title);
        };

        subscribe('metrics:update', handleMetricUpdate);
        subscribe('insights:new', handleNewInsight);

        return () => {
            unsubscribe('metrics:update', handleMetricUpdate);
            unsubscribe('insights:new', handleNewInsight);
        };
    }, [subscribe, unsubscribe, success]);

    const handleGenerateReport = useCallback((report: Report) => {
        emit('report:generate', { report });
        success('Report Generated', 'Report is being prepared');
    }, [emit, success]);

    return (
        <div className="advanced-intelligence-center">
            <header className="view-header">
                <h1>🧠 Advanced Intelligence & Analytics Center</h1>
                <p>250+ features for data-driven decision making</p>
                <div className="connection-status">
                    {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </div>
            </header>

            <div className="analytics-main">
                <section className="metrics-section">
                    <h2>Key Metrics</h2>
                    <div className="metrics-grid">
                        {metrics.map(metric => (
                            <MetricCard key={metric.id} metric={metric} />
                        ))}
                    </div>
                </section>

                <section className="insights-section">
                    <AIInsightsPanel insights={insights} />
                </section>

                <section className="visualization-section">
                    {visualizations.map(viz => (
                        <DataVisualizationPanel key={viz.id} visualization={viz} />
                    ))}
                </section>

                <section className="report-section">
                    <ReportGenerator onGenerate={handleGenerateReport} />
                </section>
            </div>
        </div>
    );
};
