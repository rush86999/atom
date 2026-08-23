import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '@/components/layout/Layout';
import WorkflowBuilder from '@/components/Automations/WorkflowBuilder';
import { useToast } from '@/components/ui/use-toast';
import { Loader2 } from 'lucide-react';
import { Node, Edge } from 'reactflow';

export default function WorkflowEditorPage() {
    const router = useRouter();
    const { id } = router.query;
    const { toast } = useToast();
    const [isLoading, setIsLoading] = useState(true);
    const [initialData, setInitialData] = useState<{ nodes: Node[], edges: Edge[] } | undefined>(undefined);
    const [templateName, setTemplateName] = useState('');

    // First-run checklist: required inputs + integration readiness for the
    // imported workflow. Advisory only — never blocks editing.
    const [requiredInputs, setRequiredInputs] = useState<string[]>([]);
    const [missingDeps, setMissingDeps] = useState<string[]>([]);
    const [connectUrls, setConnectUrls] = useState<string[]>([]);
    const [checklistDismissed, setChecklistDismissed] = useState(false);

    useEffect(() => {
        if (!id) return;
        fetchWorkflow(id as string);
    }, [id]);

    const fetchWorkflow = async (workflowId: string) => {
        setIsLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const res = await fetch(`/api/workflow-templates/${workflowId}`, {
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                }
            });
            if (!res.ok) throw new Error('Failed to load workflow');

            const template = await res.json();
            setTemplateName(template.name);
            setRequiredInputs(
                (template.inputs || [])
                    .filter((i: any) => i.required)
                    .map((i: any) => i.label || i.name)
            );

            // Integration readiness (fail-soft; personal starters declare deps).
            fetch(`/api/workflow-templates/${workflowId}/readiness`, {
                headers: { ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
            })
                .then(r => (r.ok ? r.json() : null))
                .then(d => {
                    if (d && typeof d.ready === 'boolean' && !d.ready) {
                        setMissingDeps(d.missing || []);
                        setConnectUrls(d.connect_urls || []);
                    }
                })
                .catch(() => {});

            // Convert Backend Template -> React Flow Nodes/Edges
            const newNodes: Node[] = [];
            const newEdges: Edge[] = [];

            if (template.steps && template.steps.length > 0) {
                template.steps.forEach((step: any, idx: number) => {
                    // Simple layout strategy: Staggered diagonal
                    newNodes.push({
                        id: step.step_id,
                        type: mapStepTypeToNode(step.step_type),
                        position: { x: 250, y: 100 + (idx * 150) },
                        data: {
                            label: step.name,
                            description: step.description,
                            ...step
                        }
                    });

                    // Edges
                    if (step.depends_on) {
                        step.depends_on.forEach((depId: string) => {
                            newEdges.push({
                                id: `e-${depId}-${step.step_id}`,
                                source: depId,
                                target: step.step_id,
                                type: 'addStepEdge'
                            });
                        });
                    }
                });
            } else {
                // Default start node if empty
                newNodes.push({
                    id: 'start',
                    type: 'trigger',
                    position: { x: 250, y: 50 },
                    data: { label: 'Start Trigger' }
                });
            }

            setInitialData({ nodes: newNodes, edges: newEdges });

        } catch (error) {
            console.error(error);
            toast({ title: 'Error', description: 'Failed to load workflow template', variant: 'error' });
        } finally {
            setIsLoading(false);
        }
    };

    const mapStepTypeToNode = (stepType: string): string => {
        // Map backend types to frontend node types
        switch (stepType) {
            case 'agent_execution': return 'agent';
            case 'llm_process': return 'ai_node';
            case 'condition': return 'condition';
            case 'trigger': return 'trigger';
            default: return 'action';
        }
    };

    const handleSave = async (data: { nodes: Node[], edges: Edge[] }) => {
        try {
            // Convert React Flow -> Backend JSON
            const steps = data.nodes.map(node => ({
                step_id: node.id,
                name: node.data.label,
                description: node.data.description,
                step_type: mapNodeToStepType(node.type),
                parameters: node.data.parameters || [],
                depends_on: data.edges
                    .filter(e => e.target === node.id)
                    .map(e => e.source)
            }));

            const payload = {
                name: templateName,
                description: "Updated via Visual Editor",
                steps: steps
            };

            const token = localStorage.getItem('auth_token');
            const res = await fetch(`/api/workflow-templates/${id}`, {
                method: 'PUT',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error('Failed to save to backend');

            toast({ title: 'Saved', description: 'Workflow template updated successfully.' });

        } catch (error) {
            console.error(error);
            toast({ title: 'Error', description: 'Failed to save workflow', variant: 'error' });
        }
    };

    const mapNodeToStepType = (nodeType: string | undefined): string => {
        switch (nodeType) {
            case 'agent': return 'agent_execution';
            case 'ai_node': return 'llm_process';
            case 'condition': return 'condition';
            case 'trigger': return 'trigger';
            default: return 'action';
        }
    };

    if (isLoading) return (
        <div className="flex h-screen items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
        </div>
    );

    const showChecklist =
        !checklistDismissed &&
        (requiredInputs.length > 0 || missingDeps.length > 0);

    return (
        <div className="h-[calc(100vh-64px)] w-full bg-gray-50 dark:bg-gray-800">
            {showChecklist && (
                <div
                  data-testid="first-run-checklist"
                  className="flex flex-col gap-2 border-b border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900/50 dark:bg-amber-950/30 sm:flex-row sm:items-center sm:justify-between"
                >
                    <div className="text-amber-900 dark:text-amber-200">
                        <span className="font-medium">Before first run:</span>{' '}
                        {requiredInputs.length > 0 && (
                            <span>
                                set {requiredInputs.length} required input
                                {requiredInputs.length > 1 ? 's' : ''}
                                {' '}({requiredInputs.join(', ')})
                            </span>
                        )}
                        {requiredInputs.length > 0 && missingDeps.length > 0 && ' · '}
                        {missingDeps.length > 0 && (
                            <span>connect {missingDeps.join(', ')}</span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {connectUrls.map(url => (
                            <a
                              key={url}
                              href={url}
                              className="rounded-md bg-amber-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-900 dark:bg-amber-700 dark:hover:bg-amber-600"
                            >
                                Connect {decodeURIComponent(url.split('connect=')[1] || '')}
                            </a>
                        ))}
                        <button
                          onClick={() => setChecklistDismissed(true)}
                          className="text-xs font-medium text-amber-700 underline hover:text-amber-900 dark:text-amber-300"
                        >
                            Dismiss
                        </button>
                    </div>
                </div>
            )}
            <WorkflowBuilder
                initialData={initialData}
                onSave={handleSave}
                workflowId={id as string}
            />
        </div>
    );
}
