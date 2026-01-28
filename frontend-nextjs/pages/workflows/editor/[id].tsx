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

    useEffect(() => {
        if (!id) return;
        fetchWorkflow(id as string);
    }, [id]);

    const fetchWorkflow = async (workflowId: string) => {
        setIsLoading(true);
        try {
            const res = await fetch(`/api/workflow-templates/${workflowId}`);
            if (!res.ok) throw new Error('Failed to load workflow');

            const template = await res.json();
            setTemplateName(template.name);

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

            const res = await fetch(`/api/workflow-templates/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
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

    return (
        <div className="h-[calc(100vh-64px)] w-full bg-gray-50">
            <WorkflowBuilder
                initialData={initialData}
                onSave={handleSave}
                workflowId={id as string}
            />
        </div>
    );
}
