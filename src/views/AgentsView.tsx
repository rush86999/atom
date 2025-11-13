import React, { useState, useEffect } from 'react';
import { Agent, AgentLog } from '../types';
import { AGENTS_DATA, AGENT_LOGS_DATA } from '../data';

export const AgentsView = () => {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [logs] = useState<AgentLog[]>(AGENT_LOGS_DATA);
    const [showConfigModal, setShowConfigModal] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [expandedLogs, setExpandedLogs] = useState(false);

    useEffect(() => {
        setAgents(AGENTS_DATA);
    }, []);

    const handleToggleAgent = (agentId: string) => {
        setAgents(agents.map(agent =>
            agent.id === agentId
                ? { ...agent, status: agent.status === 'online' ? 'offline' : 'online' }
                : agent
        ));
    };

    const openConfigModal = (agent: Agent) => {
        setSelectedAgent(agent);
        setShowConfigModal(true);
    };

    return (
        <div className="agents-view">
            <header className="view-header">
                <h1>AI Agents</h1>
                <p>Manage and monitor your AI assistants.</p>
            </header>
            <div className="agents-grid">
                {agents.map(agent => (
                    <div key={agent.id} className="agent-card">
                        <div className="agent-card-header">
                            <h2>{agent.name}</h2>
                            <div className={`agent-status ${agent.status}`}>
                                <div className="agent-status-dot"></div>
                                {agent.status}
                            </div>
                        </div>
                        <div className="agent-info">
                            <p>{agent.role}</p>
                        </div>
                        <div className="agent-capabilities">
                            {agent.capabilities.map(cap => (
                                <span key={cap} className="capability-tag">{cap.replace('_', ' ')}</span>
                            ))}
                        </div>
                        <div className="agent-performance">
                            <div className="perf-metric">
                                <h3>{agent.performance.tasksCompleted}</h3>
                                <p>Tasks Completed</p>
                            </div>
                            <div className="perf-metric">
                                <h3>{agent.performance.successRate}%</h3>
                                <p>Success Rate</p>
                            </div>
                            <div className="perf-metric">
                                <h3>{agent.performance.avgResponseTime}ms</h3>
                                <p>Avg Response Time</p>
                            </div>
                        </div>
                        <div className="agent-actions">
                            <button onClick={() => handleToggleAgent(agent.id)}>
                                {agent.status === 'online' ? 'Stop' : 'Start'}
                            </button>
                            <button onClick={() => openConfigModal(agent)}>Configure</button>
                        </div>
                    </div>
                ))}
            </div>
            <div className="logs-section">
                <div className="logs-header" onClick={() => setExpandedLogs(!expandedLogs)}>
                    <h3>Agent Logs</h3>
                    <button>{expandedLogs ? 'Collapse' : 'Expand'}</button>
                </div>
                {expandedLogs && (
                    <div className="logs-list">
                        {logs.map(log => (
                            <div key={log.id} className={`log-item ${log.level}`}>
                                <span className="log-timestamp">{new Date(log.timestamp).toLocaleString()}</span>
                                <span className={`log-level ${log.level}`}>{log.level.toUpperCase()}</span>
                                <span className="log-message">{log.message}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
            {showConfigModal && selectedAgent && (
                <div className="modal-overlay" onClick={() => setShowConfigModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3>Configure {selectedAgent.name}</h3>
                        <div className="config-options">
                            <label>
                                <input type="checkbox" defaultChecked /> Enable Auto-Start
                            </label>
                            <label>
                                <input type="checkbox" defaultChecked /> Allow Background Processing
                            </label>
                            <label>
                                Max Response Time (ms): <input type="number" defaultValue={selectedAgent.performance.avgResponseTime} />
                            </label>
                        </div>
                        <button onClick={() => setShowConfigModal(false)}>Save</button>
                    </div>
                </div>
            )}
        </div>
    );
};
