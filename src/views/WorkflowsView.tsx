import React, { useState, useEffect } from 'react';
import { Workflow } from '../types';
import { WORKFLOWS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';
import { useWebSocket } from '../hooks/useWebSocket';

export const WorkflowsView = () => {
    const { workflows, setWorkflows, addWorkflow, updateWorkflow, deleteWorkflow } = useAppStore();
    const { toast } = useToast();
    const { subscribe, unsubscribe } = useWebSocket({ enabled: true });

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

    return (
        <div className="workflows-view">
            <header className="view-header">
                <h1>Workflows</h1>
                <p>Automate your tasks with custom workflows.</p>
            </header>
            <button className="new-workflow-btn">+ New Workflow</button>
            <div className="workflows-list">
                {workflows.map(workflow => (
                    <div key={workflow.id} className="workflow-card">
                        <div className="workflow-card-header">
                            <h3>{workflow.name}</h3>
                            <label className="toggle-switch">
                                <input type="checkbox" checked={workflow.enabled} readOnly />
                                <span className="slider"></span>
                            </label>
                        </div>
                        <p className="workflow-description">{workflow.description}</p>
                        <div className="workflow-icons">
                            <span>Trigger: {workflow.triggers[0].type}</span>
                            <span>Action: {workflow.actions[0].type}</span>
                        </div>
                        <div className="workflow-card-footer">
                            <div className="workflow-stats">
                                <span>Executed {workflow.executionCount} times</span>
                                <span>Last: {new Date(workflow.lastExecuted).toLocaleDateString()}</span>
                            </div>
                            <button className="workflow-edit-btn">Edit</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
