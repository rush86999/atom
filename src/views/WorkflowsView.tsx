import React, { useState, useEffect } from 'react';
import { Workflow } from '../types';
import { WORKFLOWS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

export const WorkflowsView = () => {
    const { workflows, setWorkflows, addWorkflow, updateWorkflow, deleteWorkflow } = useAppStore();
    const { toast } = useToast();

    useEffect(() => {
        if (workflows.length === 0) {
            WORKFLOWS_DATA.forEach(workflow => addWorkflow(workflow));
        }
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
