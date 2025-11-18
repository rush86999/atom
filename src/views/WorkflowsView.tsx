import React, { useState, useEffect, FC } from 'react';
import { Workflow } from '../types';
import { WORKFLOWS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';
import { useWebSocket } from '../hooks/useWebSocket';

interface WorkflowStats {
    totalExecutions: number;
    successRate: number;
    averageExecutionTime: number;
    errorCount: number;
}

// Workflow Visualization Component
const WorkflowVisualization: FC<{ workflow: Workflow }> = ({ workflow }) => {
    return (
        <div className="workflow-visualization">
            <div className="workflow-nodes">
                <div className="workflow-node trigger">
                    <span>🔔 Trigger</span>
                    <p>{workflow.triggers[0]?.type || 'None'}</p>
                </div>
                <div className="workflow-arrow">→</div>
                <div className="workflow-node action">
                    <span>⚡ Action</span>
                    <p>{workflow.actions[0]?.type || 'None'}</p>
                </div>
            </div>
        </div>
    );
};

// Workflow Performance Widget
const WorkflowPerformanceWidget: FC<{ workflow: Workflow }> = ({ workflow }) => {
    const stats: WorkflowStats = {
        totalExecutions: workflow.executionCount || 0,
        successRate: 95,
        averageExecutionTime: 2500,
        errorCount: Math.floor((workflow.executionCount || 0) * 0.05)
    };

    return (
        <div className="workflow-performance">
            <h4>Performance Metrics</h4>
            <div className="metrics-grid">
                <div className="metric">
                    <span className="metric-label">Success Rate</span>
                    <span className="metric-value">{stats.successRate}%</span>
                </div>
                <div className="metric">
                    <span className="metric-label">Avg. Time</span>
                    <span className="metric-value">{(stats.averageExecutionTime / 1000).toFixed(1)}s</span>
                </div>
                <div className="metric">
                    <span className="metric-label">Errors</span>
                    <span className="metric-value">{stats.errorCount}</span>
                </div>
            </div>
        </div>
    );
};

export const WorkflowsView = () => {
    const { workflows, setWorkflows, addWorkflow, updateWorkflow, deleteWorkflow } = useAppStore();
    const { toast } = useToast();
    const { subscribe, unsubscribe, emit } = useWebSocket({ enabled: true });
    const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
    const [showBuilder, setShowBuilder] = useState(false);
    const [filterEnabled, setFilterEnabled] = useState<boolean | null>(null);

    useEffect(() => {
        if (workflows.length === 0) {
            WORKFLOWS_DATA.forEach(workflow => addWorkflow(workflow));
        }

        const onExecuted = (data: any) => {
            if (!data?.workflowId) return;
            toast.success('Workflow Executed', `Workflow ${data.workflowId} executed in ${data.executionTime}ms`);
            // Optionally update execution count if present
            const wf = workflows.find(w => w.id === data.workflowId);
            if (wf) updateWorkflow(data.workflowId, { executionCount: (wf.executionCount || 0) + 1, lastExecuted: data.timestamp || new Date().toISOString() });
        };

        const onFailed = (data: any) => {
            toast.error('Workflow Failed', data.error || 'Workflow execution failed');
        };

        subscribe('workflow:executed', onExecuted);
        subscribe('workflow:execution:failed', onFailed);

        return () => {
            unsubscribe('workflow:executed', onExecuted);
            unsubscribe('workflow:execution:failed', onFailed);
        };
    }, [workflows.length, addWorkflow]);

    const filteredWorkflows = filterEnabled === null 
        ? workflows 
        : workflows.filter(w => w.enabled === filterEnabled);

    const handleToggleWorkflow = (workflowId: string) => {
        const workflow = workflows.find(w => w.id === workflowId);
        if (workflow) {
            updateWorkflow(workflowId, { enabled: !workflow.enabled });
            toast.success('Workflow Updated', `${workflow.name} ${!workflow.enabled ? 'enabled' : 'disabled'}`);
            emit?.('workflow:toggled', { workflowId, enabled: !workflow.enabled });
        }
    };

    const handleExecuteWorkflow = (workflowId: string) => {
        emit?.('workflow:execute', { workflowId, timestamp: new Date().toISOString() });
        toast.info('Executing', 'Workflow execution started...');
    };

    return (
        <div className="workflows-view">
            <header className="view-header">
                <h1>Workflows</h1>
                <p>Automate your tasks with custom workflows.</p>
            </header>
            
            <div className="workflows-controls">
                <button className="new-workflow-btn" onClick={() => setShowBuilder(!showBuilder)}>
                    {showBuilder ? '✕ Close Builder' : '+ New Workflow'}
                </button>
                <div className="workflow-filters">
                    <button 
                        className={`filter-btn ${filterEnabled === null ? 'active' : ''}`}
                        onClick={() => setFilterEnabled(null)}
                    >
                        All
                    </button>
                    <button 
                        className={`filter-btn ${filterEnabled === true ? 'active' : ''}`}
                        onClick={() => setFilterEnabled(true)}
                    >
                        Enabled
                    </button>
                    <button 
                        className={`filter-btn ${filterEnabled === false ? 'active' : ''}`}
                        onClick={() => setFilterEnabled(false)}
                    >
                        Disabled
                    </button>
                </div>
            </div>

            {showBuilder && (
                <div className="workflow-builder">
                    <h3>Visual Workflow Builder</h3>
                    <div className="builder-content">
                        <p>Drag components to build your workflow</p>
                        <div className="builder-canvas">
                            <p style={{ textAlign: 'center', color: '#999' }}>Workflow canvas - Coming soon</p>
                        </div>
                    </div>
                </div>
            )}

            <div className="workflows-list">
                {filteredWorkflows.map(workflow => (
                    <div key={workflow.id} className="workflow-card">
                        <div className="workflow-card-header">
                            <h3>{workflow.name}</h3>
                            <label className="toggle-switch">
                                <input 
                                    type="checkbox" 
                                    checked={workflow.enabled}
                                    onChange={() => handleToggleWorkflow(workflow.id)}
                                />
                                <span className="slider"></span>
                            </label>
                        </div>
                        <p className="workflow-description">{workflow.description}</p>
                        
                        <WorkflowVisualization workflow={workflow} />
                        
                        <WorkflowPerformanceWidget workflow={workflow} />
                        
                        <div className="workflow-card-footer">
                            <div className="workflow-stats">
                                <span>Executed {workflow.executionCount} times</span>
                                <span>Last: {new Date(workflow.lastExecuted).toLocaleDateString()}</span>
                            </div>
                            <div className="workflow-actions">
                                <button 
                                    className="workflow-execute-btn"
                                    onClick={() => handleExecuteWorkflow(workflow.id)}
                                    disabled={!workflow.enabled}
                                >
                                    ▶️ Run
                                </button>
                                <button className="workflow-edit-btn">✏️ Edit</button>
                                <button 
                                    className="workflow-delete-btn"
                                    onClick={() => deleteWorkflow(workflow.id)}
                                >
                                    🗑️
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
