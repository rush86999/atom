import React, { useState, useEffect, useMemo, FC } from 'react';
import { Task, Transaction, CalendarEvent } from '../types';
import { useAppStore } from '../store';

interface AnalyticsMetrics {
    productivityTrend: number[];
    spendingTrend: number[];
    completionRate: number;
    focusHours: number;
    averageTaskDuration: number;
}

// Trend Chart Component
const TrendChart: FC<{ data: number[]; label: string; color: string }> = ({ data, label, color }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    return (
        <div className="trend-chart">
            <h4>{label}</h4>
            <svg width="100%" height="200" viewBox="0 0 300 200">
                {data.map((val, i) => {
                    const x = (i / (data.length - 1)) * 280 + 10;
                    const y = 180 - ((val - min) / range) * 150;
                    return (
                        <circle key={i} cx={x} cy={y} r="3" fill={color} />
                    );
                })}
                <polyline
                    points={data
                        .map((val, i) => {
                            const x = (i / (data.length - 1)) * 280 + 10;
                            const y = 180 - ((val - min) / range) * 150;
                            return `${x},${y}`;
                        })
                        .join(' ')}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                />
            </svg>
        </div>
    );
};

// Distribution Chart
const DistributionChart: FC<{ data: Record<string, number>; label: string }> = ({ data, label }) => {
    const total = Object.values(data).reduce((a, b) => a + b, 0);

    return (
        <div className="distribution-chart">
            <h4>{label}</h4>
            <div className="bars">
                {Object.entries(data).map(([key, value]) => (
                    <div key={key} className="bar-container">
                        <div
                            className="bar"
                            style={{ height: `${(value / total) * 200}px` }}
                        ></div>
                        <label>{key}</label>
                        <span className="bar-value">{value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const AnalyticsView = () => {
    const { tasks, transactions } = useAppStore();
    const [timeRange, setTimeRange] = useState<'week' | 'month' | 'year'>('week');

    const analytics: AnalyticsMetrics = useMemo(() => {
        const completedTasks = tasks.filter(t => t.status === 'completed').length;
        const totalTasks = tasks.length;

        return {
            productivityTrend: [65, 70, 68, 75, 82, 78, 85],
            spendingTrend: [120, 135, 128, 145, 160, 150, 170],
            completionRate: totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0,
            focusHours: 28.5,
            averageTaskDuration: 2.5
        };
    }, [tasks]);

    const taskDistribution = useMemo(() => ({
        Critical: tasks.filter(t => t.priority === 'critical').length,
        High: tasks.filter(t => t.priority === 'high').length,
        Medium: tasks.filter(t => t.priority === 'medium').length,
        Low: tasks.filter(t => t.priority === 'low').length
    }), [tasks]);

    const spendingByCategory = useMemo(() => ({
        Food: 450,
        Transport: 200,
        Entertainment: 150,
        Shopping: 300,
        Other: 100
    }), []);

    return (
        <div className="analytics-view">
            <header className="view-header">
                <h1>Analytics & Insights</h1>
                <p>Visualize your productivity and spending patterns.</p>
                <div className="time-range-selector">
                    <button
                        className={timeRange === 'week' ? 'active' : ''}
                        onClick={() => setTimeRange('week')}
                    >
                        Week
                    </button>
                    <button
                        className={timeRange === 'month' ? 'active' : ''}
                        onClick={() => setTimeRange('month')}
                    >
                        Month
                    </button>
                    <button
                        className={timeRange === 'year' ? 'active' : ''}
                        onClick={() => setTimeRange('year')}
                    >
                        Year
                    </button>
                </div>
            </header>

            <div className="analytics-grid">
                <div className="analytics-card metric-card">
                    <h3>📊 Key Metrics</h3>
                    <div className="metrics-display">
                        <div className="metric">
                            <span className="metric-label">Completion Rate</span>
                            <span className="metric-value">{analytics.completionRate}%</span>
                        </div>
                        <div className="metric">
                            <span className="metric-label">Focus Hours</span>
                            <span className="metric-value">{analytics.focusHours}h</span>
                        </div>
                        <div className="metric">
                            <span className="metric-label">Avg Task Duration</span>
                            <span className="metric-value">{analytics.averageTaskDuration}h</span>
                        </div>
                    </div>
                </div>

                <div className="analytics-card chart-card">
                    <TrendChart
                        data={analytics.productivityTrend}
                        label="Productivity Trend"
                        color="#3b82f6"
                    />
                </div>

                <div className="analytics-card chart-card">
                    <TrendChart
                        data={analytics.spendingTrend}
                        label="Spending Trend"
                        color="#ef4444"
                    />
                </div>

                <div className="analytics-card distribution-card">
                    <DistributionChart
                        data={taskDistribution}
                        label="Tasks by Priority"
                    />
                </div>

                <div className="analytics-card distribution-card">
                    <DistributionChart
                        data={spendingByCategory}
                        label="Spending by Category"
                    />
                </div>

                <div className="analytics-card insights-card">
                    <h3>💡 AI Insights</h3>
                    <div className="insights-list">
                        <div className="insight">
                            <p>✨ Your most productive day is Tuesday. Schedule important tasks then.</p>
                        </div>
                        <div className="insight">
                            <p>💰 Food spending is 15% higher than last month. Consider meal planning.</p>
                        </div>
                        <div className="insight">
                            <p>⏰ You typically complete tasks 20% faster in the morning.</p>
                        </div>
                        <div className="insight">
                            <p>🎯 You've improved task completion by 25% over the last 3 months!</p>
                        </div>
                    </div>
                </div>

                <div className="analytics-card weekly-summary">
                    <h3>📅 Weekly Summary</h3>
                    <div className="weekly-stats">
                        <div className="day-stat">
                            <span className="day">Mon</span>
                            <span className="tasks-completed">8</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Tue</span>
                            <span className="tasks-completed">12</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Wed</span>
                            <span className="tasks-completed">10</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Thu</span>
                            <span className="tasks-completed">9</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Fri</span>
                            <span className="tasks-completed">11</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Sat</span>
                            <span className="tasks-completed">5</span>
                        </div>
                        <div className="day-stat">
                            <span className="day">Sun</span>
                            <span className="tasks-completed">3</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
