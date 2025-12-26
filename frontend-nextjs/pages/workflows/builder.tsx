import React, { useState, useCallback, useEffect } from 'react';
import ReactFlow, {
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Node,
    Edge,
    NodeTypes,
    Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import Link from 'next/link';
import Layout from '@/components/layout/Layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';
import { Bot, Zap, Save, Play, Plus, FolderOpen, Loader2 } from 'lucide-react';

// Custom Node Component for Agents
const AgentNode = ({ data }: { data: any }) => {
    return (
        <div className="px-4 py-3 shadow-md rounded-lg bg-gradient-to-br from-purple-600 to-indigo-700 border-2 border-purple-500 text-white min-w-[180px]">
            <div className="flex items-center gap-2">
                <Bot className="w-5 h-5" />
                <span className="font-semibold">{data.label}</span>
            </div>
            <p className="text-xs text-purple-200 mt-1">{data.description || 'Computer Use Agent'}</p>
        </div>
    );
};

// Custom Node Component for Actions
const ActionNode = ({ data }: { data: any }) => {
    return (
        <div className="px-4 py-3 shadow-md rounded-lg bg-gradient-to-br from-gray-700 to-gray-800 border border-gray-600 text-white min-w-[160px]">
            <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                <span className="font-medium">{data.label}</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">{data.description || 'Workflow Action'}</p>
        </div>
    );
};

const nodeTypes: NodeTypes = {
    agent: AgentNode,
    action: ActionNode,
};

// Initial nodes for demo
const initialNodes: Node[] = [
    {
        id: 'start',
        type: 'input',
        position: { x: 250, y: 50 },
        data: { label: 'Start' },
        style: { background: '#10b981', color: 'white', border: 'none', borderRadius: '8px' },
    },
];

const initialEdges: Edge[] = [];

// Available agents for sidebar
const availableAgents = [
    { id: 'competitive_intel', name: 'Competitive Intel', description: 'Monitor competitor pricing' },
    { id: 'payroll_guardian', name: 'Payroll Guardian', description: 'Reconcile payroll data' },
    { id: 'inventory_omni', name: 'Inventory Check', description: 'Shopify vs WMS comparison' },
];

interface Template {
    template_id: string;
    name: string;
    description: string;
}

export default function WorkflowBuilder() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [workflowName, setWorkflowName] = useState('My Agent Pipeline');
    const [templates, setTemplates] = useState<Template[]>([]);
    const [currentTemplateId, setCurrentTemplateId] = useState<string | null>(null);
    const [isRunning, setIsRunning] = useState(false);
    const { toast } = useToast();

    // Fetch templates on mount
    useEffect(() => {
        fetchTemplates();
    }, []);

    const fetchTemplates = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/workflow-templates');
            if (res.ok) {
                const data = await res.json();
                setTemplates(data);
            }
        } catch (error) {
            console.error("Failed to fetch templates", error);
        }
    };

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    const addAgentNode = useCallback((agentId: string, agentName: string, description: string) => {
        const newNode: Node = {
            id: `${agentId}-${Date.now()}`,
            type: 'agent',
            position: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
            data: { label: agentName, description, agentId },
        };
        setNodes((nds) => [...nds, newNode]);
    }, [setNodes]);

    const handleSave = async () => {
        const templateData = {
            name: workflowName,
            description: `Visual workflow: ${workflowName}`,
            category: 'automation',
            complexity: 'intermediate',
            tags: ['visual', 'agent-pipeline'],
            steps: nodes
                .filter(n => n.type === 'agent')
                .map((node) => ({
                    step_id: node.id,
                    name: node.data.label,
                    description: node.data.description,
                    step_type: 'agent_execution',
                    parameters: [{ name: 'agent_id', type: 'string', default_value: node.data.agentId }],
                    depends_on: edges.filter(e => e.target === node.id).map(e => e.source)
                }))
        };

        try {
            const res = await fetch('http://localhost:8000/api/workflow-templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(templateData)
            });

            if (res.ok) {
                const result = await res.json();
                setCurrentTemplateId(result.template_id);
                toast({ title: 'Saved!', description: `Template "${workflowName}" saved.` });
                fetchTemplates(); // Refresh list
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            toast({ title: 'Error', description: 'Failed to save template.', variant: 'error' });
        }
    };

    const handleRun = async () => {
        if (!currentTemplateId) {
            toast({ title: 'Save First', description: 'Please save the workflow before running.', variant: 'error' });
            return;
        }

        setIsRunning(true);
        toast({ title: 'Executing...', description: `Running template: ${workflowName}` });

        try {
            const res = await fetch(`http://localhost:8000/api/workflow-templates/${currentTemplateId}/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            if (res.ok) {
                const result = await res.json();
                toast({ title: 'Completed!', description: `Status: ${result.workflow_status}` });
            } else {
                throw new Error('Execution failed');
            }
        } catch (error) {
            toast({ title: 'Execution Failed', description: String(error), variant: 'error' });
        } finally {
            setIsRunning(false);
        }
    };

    const loadTemplate = async (templateId: string) => {
        try {
            const res = await fetch(`http://localhost:8000/api/workflow-templates/${templateId}`);
            if (!res.ok) throw new Error('Failed to load');

            const template = await res.json();
            setWorkflowName(template.name);
            setCurrentTemplateId(template.template_id);

            // Convert steps to nodes
            const newNodes: Node[] = [
                {
                    id: 'start', type: 'input', position: { x: 250, y: 50 }, data: { label: 'Start' },
                    style: { background: '#10b981', color: 'white', border: 'none', borderRadius: '8px' }
                }
            ];
            const newEdges: Edge[] = [];

            (template.steps || []).forEach((step: any, idx: number) => {
                const agentId = step.parameters?.find((p: any) => p.name === 'agent_id')?.default_value || step.step_id;
                newNodes.push({
                    id: step.step_id,
                    type: 'agent',
                    position: { x: 100 + idx * 250, y: 150 },
                    data: { label: step.name, description: step.description, agentId }
                });

                // Create edges from depends_on
                (step.depends_on || []).forEach((dep: string) => {
                    newEdges.push({ id: `e-${dep}-${step.step_id}`, source: dep, target: step.step_id });
                });

                // If no dependencies, connect to start
                if (!step.depends_on?.length && idx === 0) {
                    newEdges.push({ id: `e-start-${step.step_id}`, source: 'start', target: step.step_id });
                }
            });

            setNodes(newNodes);
            setEdges(newEdges);
            toast({ title: 'Loaded', description: `Template "${template.name}" loaded.` });

        } catch (error) {
            toast({ title: 'Error', description: 'Failed to load template.', variant: 'error' });
        }
    };

    return (
        <Layout>
            <div className="h-[calc(100vh-80px)] flex">
                {/* Sidebar */}
                <div className="w-64 bg-gray-900 border-r border-gray-800 p-4 space-y-4 overflow-y-auto">
                    <div>
                        <h2 className="text-lg font-bold text-white mb-2">Workflow Builder</h2>
                        <input
                            type="text"
                            value={workflowName}
                            onChange={(e) => setWorkflowName(e.target.value)}
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                            placeholder="Workflow Name"
                        />
                    </div>

                    {/* Template Loader */}
                    <div>
                        <h3 className="text-sm font-semibold text-gray-400 mb-2 flex items-center gap-1">
                            <FolderOpen className="w-4 h-4" /> Load Template
                        </h3>
                        <select
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                            onChange={(e) => e.target.value && loadTemplate(e.target.value)}
                            defaultValue=""
                        >
                            <option value="" disabled>Select template...</option>
                            {templates.map((t) => (
                                <option key={t.template_id} value={t.template_id}>{t.name}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <h3 className="text-sm font-semibold text-gray-400 mb-2">Available Agents</h3>
                        <div className="space-y-2">
                            {availableAgents.map((agent) => (
                                <Card
                                    key={agent.id}
                                    className="cursor-pointer hover:border-purple-500 transition-colors bg-gray-800 border-gray-700"
                                    onClick={() => addAgentNode(agent.id, agent.name, agent.description)}
                                >
                                    <CardContent className="p-3">
                                        <div className="flex items-center gap-2">
                                            <Plus className="w-4 h-4 text-purple-400" />
                                            <span className="text-sm text-white">{agent.name}</span>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-1">{agent.description}</p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Canvas */}
                <div className="flex-1">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        nodeTypes={nodeTypes}
                        fitView
                        className="bg-gray-950"
                    >
                        <Panel position="top-right" className="flex gap-2">
                            <Button onClick={handleSave} className="bg-green-600 hover:bg-green-700">
                                <Save className="w-4 h-4 mr-2" />
                                Save
                            </Button>
                            <Button onClick={handleRun} disabled={isRunning} variant="outline">
                                {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                                {isRunning ? 'Running...' : 'Run'}
                            </Button>
                        </Panel>
                        <Controls className="bg-gray-800 border-gray-700" />
                        <MiniMap className="bg-gray-900" />
                        <Background color="#333" gap={16} />
                    </ReactFlow>
                </div>
            </div>
        </Layout>
    );
}
