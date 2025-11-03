
import React, { useState, useEffect } from 'react';
import { Workflow } from '../types';
import { WORKFLOWS_DATA } from '../data';
import { ServiceIcon } from '../components/ServiceIcon';

const timeAgo = (date: string) => {
    const seconds = Math.floor((new Date().getTime() - new Date(date).getTime()) / 1000);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
};

const WorkflowCard: React.FC<{ workflow: Workflow; onEdit: () => void; }> = ({ workflow, onEdit }) => {
    const [isEnabled, setIsEnabled] = useState(workflow.enabled);
    return (
        <div className="workflow-card">
            <div className="workflow-card-header"><h3>{workflow.name}</h3><label className="toggle-switch"><input type="checkbox" checked={isEnabled} onChange={() => setIsEnabled(!isEnabled)} /><span className="slider"></span></label></div>
            <p className="workflow-description">{workflow.description}</p>
            <div className="workflow-icons"><ServiceIcon service={workflow.triggers[0].type.split('_')[0]} /><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M2 10a.75.75 0 01.75-.75h12.59l-2.1-1.95a.75.75 0 111.02-1.1l3.5 3.25a.75.75 0 010 1.1l-3.5 3.25a.75.75 0 11-1.02-1.1l2.1-1.95H2.75A.75.75 0 012 10z" clipRule="evenodd" /></svg><ServiceIcon service={workflow.actions[0].config.platform || workflow.actions[0].config.service || 'default'} /></div>
            <div className="workflow-card-footer"><div className="workflow-stats"><p><strong>{workflow.executionCount}</strong> executions</p><p>Last run: {timeAgo(workflow.lastExecuted)}</p></div><button onClick={onEdit} className="workflow-edit-btn">Edit</button></div>
        </div>
    );
};

const WorkflowEditor: React.FC<{ workflow: Workflow | null; onClose: () => void; }> = ({ workflow, onClose }) => {
    if (!workflow) return null;
    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content workflow-editor" onClick={e => e.stopPropagation()}>
                <div className="modal-header"><h2>{workflow.name}</h2><button className="close-button" onClick={onClose}>&times;</button></div>
                <div className="modal-body"><div className="editor-flow">
                    <div className="editor-column"><h4>Trigger</h4><div className="flow-card"><div className="flow-card-header"><ServiceIcon service={workflow.triggers[0].type.split('_')[0]} /><span>{workflow.triggers[0].type.replace(/_/g, ' ')}</span></div><div className="flow-card-config">{Object.entries(workflow.triggers[0].config).map(([key, value]) => (<p key={key}><strong>{key}:</strong> {String(value)}</p>))}</div></div></div>
                    <div className="flow-connector"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M2 10a.75.75 0 01.75-.75h12.59l-2.1-1.95a.75.75 0 111.02-1.1l3.5 3.25a.75.75 0 010 1.1l-3.5 3.25a.75.75 0 11-1.02-1.1l2.1-1.95H2.75A.75.75 0 012 10z" clipRule="evenodd" /></svg></div>
                    <div className="editor-column"><h4>Action</h4><div className="flow-card"><div className="flow-card-header"><ServiceIcon service={workflow.actions[0].config.platform || workflow.actions[0].config.service || 'default'} /><span>{workflow.actions[0].type.replace(/_/g, ' ')}</span></div><div className="flow-card-config">{Object.entries(workflow.actions[0].config).map(([key, value]) => (<p key={key}><strong>{key}:</strong> {String(value)}</p>))}</div></div></div>
                </div></div>
            </div>
        </div>
    );
};

export const WorkflowsView = () => {
    const [workflows, setWorkflows] = useState<Workflow[]>([]);
    const [editingWorkflow, setEditingWorkflow] = useState<Workflow | null>(null);
    useEffect(() => { setWorkflows(WORKFLOWS_DATA); }, []);
    return (
        <div className="workflows-view">
            <header className="view-header"><h1>Workflow Automation</h1><p>Create automations to connect your services.</p><button className="new-workflow-btn">+ New Workflow</button></header>
            <div className="workflows-list">{workflows.map(wf => (<WorkflowCard key={wf.id} workflow={wf} onEdit={() => setEditingWorkflow(wf)} />))}</div>
            <WorkflowEditor workflow={editingWorkflow} onClose={() => setEditingWorkflow(null)} />
        </div>
    );
};
