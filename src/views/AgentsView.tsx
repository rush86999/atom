
import React, { useState, useEffect } from 'react';
import { Agent } from '../types';
import { AGENTS_DATA } from '../data';

const AgentCard: React.FC<{ agent: Agent }> = ({ agent }) => (
    <div className="agent-card">
        <div className="agent-card-header">
            <h2>{agent.name}</h2>
            <div className={`agent-status ${agent.status}`}><div className="agent-status-dot"></div>{agent.status}</div>
        </div>
        <div className="agent-info"><p><strong>Role:</strong> {agent.role.replace(/_/g, ' ')}</p></div>
        <div className="agent-capabilities">{agent.capabilities.map(cap => <span key={cap} className="capability-tag">{cap.replace(/_/g, ' ')}</span>)}</div>
        <div className="agent-performance">
            <div className="perf-metric"><h3>{agent.performance.tasksCompleted}</h3><p>Tasks Done</p></div>
            <div className="perf-metric"><h3>{agent.performance.successRate}%</h3><p>Success Rate</p></div>
            <div className="perf-metric"><h3>{agent.performance.avgResponseTime}ms</h3><p>Avg. Response</p></div>
        </div>
    </div>
);

export const AgentsView = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  useEffect(() => { setAgents(AGENTS_DATA); }, []);
  return (
    <div className="agents-view">
        <header className="view-header"><h1>Agent Management</h1><p>Monitor and coordinate your team of specialized AI agents.</p></header>
        <div className="agents-grid">{agents.map(agent => <AgentCard key={agent.id} agent={agent} />)}</div>
    </div>
  );
};
