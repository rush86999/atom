
import React, { useState, useEffect } from 'react';
import { DevProject, DevMetrics } from '../types';
import { DEV_PROJECT_DATA } from '../data';
import { ChatView } from './ChatView';

const BuildMonitor: React.FC<{ project: DevProject }> = ({ project }) => {
    const agentTasks = [
        { name: 'Full-stack Engineer', status: 'complete', task: 'Creating Next.js pages' },
        { name: 'UI Designer', status: 'in_progress', task: 'Optimizing responsive layout' },
        { name: 'Performance Agent', status: 'pending', task: 'Adding lazy loading' },
        { name: 'SEO Specialist', status: 'pending', task: 'Writing meta descriptions' },
    ] as const;
    const getStatusIcon = (status: 'complete' | 'in_progress' | 'pending') => {
        if (status === 'complete') return '✅';
        if (status === 'in_progress') return '🔄';
        return '⏳';
    }
    return (
        <div className="build-monitor">
            <h3>Real-time Cloud Build Status</h3>
            <div className="progress-bar-container">
                <div className="progress-bar" style={{ width: `${project.progress}%` }}></div>
                <span>{project.progress}%</span>
            </div>
            <div className="build-links">
                <p>Live: <a href={project.liveUrl} target="_blank" rel="noopener noreferrer">{project.liveUrl}</a></p>
                <p>Preview: <a href={project.previewUrl} target="_blank" rel="noopener noreferrer">{project.previewUrl}</a></p>
            </div>
            <div className="agent-tasks-monitor">
                <h4>{agentTasks.filter(t=>t.status !== 'pending').length}/{agentTasks.length} Agents Active</h4>
                {agentTasks.map(agent => (
                    <div key={agent.name} className={`agent-task-row status-${agent.status}`}>
                        <span>{getStatusIcon(agent.status)}</span>
                        <strong>{agent.name}:</strong>
                        <span>{agent.task}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

const MetricsPanel: React.FC<{ metrics: DevMetrics }> = ({ metrics }) => (
    <div className="metrics-panel">
        <h3>Live Metrics</h3>
        <div className="metrics-grid">
            <div className="metric-card"><h4>Performance</h4><p>{metrics.performance}/100</p></div>
            <div className="metric-card"><h4>Mobile</h4><p>{metrics.mobile}/100</p></div>
            <div className="metric-card"><h4>SEO</h4><p>{metrics.seo}/100</p></div>
            <div className="metric-card"><h4>Rebuild Time</h4><p>{metrics.rebuildTime}s</p></div>
        </div>
    </div>
);

export const DevStudioView = () => {
    const [project, setProject] = useState(DEV_PROJECT_DATA);
    // Mimic build progress
    useEffect(() => {
        if (project.status === 'building') {
            const interval = setInterval(() => {
                setProject(p => {
                    const newProgress = p.progress + 5;
                    if (newProgress >= 100) {
                        clearInterval(interval);
                        return { ...p, progress: 100, status: 'live' };
                    }
                    return { ...p, progress: newProgress };
                });
            }, 1000);
            return () => clearInterval(interval);
        }
    }, [project.status]);
    return (
        <div className="dev-studio-view">
             <header className="view-header">
                <h1>AI Web Development Studio</h1>
                <p>Build and manage web applications through conversation.</p>
            </header>
            <div className="dev-studio-main">
                <div className="dev-studio-left">
                    <BuildMonitor project={project} />
                    <MetricsPanel metrics={project.metrics} />
                </div>
                <div className="dev-studio-right">
                    <ChatView />
                </div>
            </div>
        </div>
    );
};
