import React, { useState, useCallback } from 'react';
import ReactFlow, {
    addEdge,
    Background,
    Controls,
    Connection,
    Edge,
    Node,
    useNodesState,
    useEdgesState,
    ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { nodeTypes } from './CustomNodes';
import { Button } from "@/components/ui/button";
import { Plus, Save, Zap, Monitor, Globe } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

const initialNodes: Node[] = [
    {
        id: '1',
        type: 'trigger',
        position: { x: 250, y: 0 },
        data: {
            label: 'Webhook Start',
            integration: 'API Gateway',
            schema: { type: 'object', properties: { userId: { type: 'string' } } }
        },
    },
    {
        id: '2',
        type: 'condition',
        position: { x: 250, y: 200 },
        data: { condition: 'userId exists?' },
    },
    {
        id: '3',
        type: 'ai_node',
        position: { x: 50, y: 350 },
        data: { label: 'Analyze Intent', model: 'GPT-4', prompt: 'Analyze user intent...' },
    },
    {
        id: '4',
        type: 'desktop_node',
        position: { x: 50, y: 500 },
        data: { action: 'Open Application', target: 'Excel', waitForInput: true },
    },
];

const initialEdges: Edge[] = [
    { id: 'e1-2', source: '1', target: '2' },
    { id: 'e2-3', source: '2', sourceHandle: 'true', target: '3' },
];

interface WorkflowBuilderProps {
    onSave?: (data: { nodes: Node[]; edges: Edge[] }) => void;
    initialData?: { nodes: Node[]; edges: Edge[] };
}

const WorkflowBuilder: React.FC<WorkflowBuilderProps> = ({ onSave: onSaveProp, initialData }) => {
    // Use prop data if available, otherwise fallback to default initialNodes
    const [nodes, setNodes, onNodesChange] = useNodesState(initialData?.nodes || initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialData?.edges || initialEdges);
    const { toast } = useToast();

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    const addNode = (type: string) => {
        const id = `${nodes.length + 1}`;
        const newNode: Node = {
            id,
            type,
            position: { x: Math.random() * 400, y: Math.random() * 400 },
            data: { label: `${type} node` },
        };
        setNodes((nds) => nds.concat(newNode));
    };

    const addServiceNode = (service: string) => {
        const id = `${nodes.length + 1}`;
        const newNode: Node = {
            id,
            type: 'action',
            position: { x: Math.random() * 400, y: Math.random() * 400 },
            data: { label: `${service} Action`, service: service, action: 'Perform Action' },
        };
        setNodes((nds) => nds.concat(newNode));
    };

    const onSave = () => {
        console.log('Saved Workflow:', { nodes, edges });
        if (onSaveProp) {
            onSaveProp({ nodes, edges });
        } else {
            toast({
                title: "Workflow Saved (Local)",
                description: `Saved ${nodes.length} nodes and ${edges.length} connections.`,
            });
        }
    };

    const handleChatSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!chatInput.trim()) return;

        setIsProcessing(true);
        const message = chatInput;
        setChatInput('');

        try {
            // Call NLU endpoint
            const response = await fetch('/api/agent/nlu', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error('NLU service unavailable');
            }

            const nluResult = await response.json();
            const { primaryGoal, extractedParameters } = nluResult;
            const service = extractedParameters?.service || 'general';
            const action = extractedParameters?.action || 'process';

            // Map NLU output to workflow operations
            if (primaryGoal === 'workflow' || service !== 'general') {
                // Service-specific nodes
                const serviceMap: Record<string, string> = {
                    'slack': 'Slack',
                    'gmail': 'Gmail',
                    'email': 'Gmail',
                    'github': 'GitHub',
                    'notion': 'Notion',
                    'asana': 'Asana',
                    'trello': 'Trello',
                    'calendar': 'Google Calendar',
                    'google calendar': 'Google Calendar',
                    'drive': 'Google Drive',
                    'dropbox': 'Dropbox',
                };

                const serviceName = serviceMap[service] || service.charAt(0).toUpperCase() + service.slice(1);

                if (action === 'delete' || message.toLowerCase().includes('clear') || message.toLowerCase().includes('reset')) {
                    setNodes([]);
                    setEdges([]);
                    toast({ title: "AI Copilot", description: "Cleared workflow." });
                } else {
                    addServiceNode(serviceName);
                    toast({ title: "AI Copilot", description: `Added ${serviceName} node via NLU.` });
                }
            } else if (message.toLowerCase().includes('clear') || message.toLowerCase().includes('reset')) {
                setNodes([]);
                setEdges([]);
                toast({ title: "AI Copilot", description: "Cleared workflow." });
            } else if (message.toLowerCase().includes('desktop')) {
                addNode('desktop');
                toast({ title: "AI Copilot", description: "Added Desktop agent." });
            } else if (message.toLowerCase().includes('ai') || message.toLowerCase().includes('analyze')) {
                addNode('ai_node');
                toast({ title: "AI Copilot", description: "Added AI Processing node." });
            } else if (message.toLowerCase().includes('condition') || message.toLowerCase().includes('if')) {
                addNode('condition');
                toast({ title: "AI Copilot", description: "Added Condition node." });
            } else {
                toast({ title: "AI Copilot", description: `Intent: ${primaryGoal} | Service: ${service}. Try specifying a service like Slack, Gmail, or GitHub.` });
            }

        } catch (error) {
            // Fallback to keyword matching if NLU fails
            console.warn('NLU failed, using fallback:', error);
            const cmd = message.toLowerCase();

            if (cmd.includes('add') && cmd.includes('slack')) {
                addServiceNode('Slack');
                toast({ title: "AI Copilot", description: "Added Slack node (fallback)." });
            } else if (cmd.includes('add') && cmd.includes('desktop')) {
                addNode('desktop');
                toast({ title: "AI Copilot", description: "Added Desktop agent (fallback)." });
            } else if (cmd.includes('clear') || cmd.includes('reset')) {
                setNodes([]);
                setEdges([]);
                toast({ title: "AI Copilot", description: "Cleared workflow." });
            } else {
                toast({ title: "AI Copilot", description: "NLU unavailable. Try 'Add Slack' or 'Clear'." });
            }
        } finally {
            setIsProcessing(false);
        }
    };

    const [chatInput, setChatInput] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);

    return (
        <div className="h-[600px] w-full border rounded-lg bg-white shadow-sm flex flex-col relative">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50">
                <h2 className="text-lg font-semibold">Workflow Builder</h2>
                <div className="space-x-2">
                    <Button size="sm" variant="outline" onClick={() => addNode('action')}>
                        <Plus className="w-4 h-4 mr-1" /> Add Action
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('condition')}>
                        <Plus className="w-4 h-4 mr-1" /> Add Condition
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('ai_node')}>
                        <Zap className="w-4 h-4 mr-1 fill-purple-500 text-purple-500" /> AI Node
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('desktop')}>
                        <Monitor className="w-4 h-4 mr-1 text-slate-600" /> Desktop
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addServiceNode('Slack')}>
                        <Globe className="w-4 h-4 mr-1 text-blue-500" /> + Slack
                    </Button>
                    <Button size="sm" onClick={onSave}>
                        <Save className="w-4 h-4 mr-1" /> Save
                    </Button>
                </div>
            </div>
            <div className="flex-1 min-h-0 relative">
                <ReactFlowProvider>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        nodeTypes={nodeTypes}
                        fitView
                    >
                        <Background />
                        <Controls />
                    </ReactFlow>
                </ReactFlowProvider>

                {/* AI Copilot Chat Interface */}
                <div className="absolute bottom-4 left-4 w-80 bg-white border rounded-lg shadow-lg p-3 z-10">
                    <div className="flex items-center space-x-2 mb-2">
                        <div className="bg-purple-100 p-1.5 rounded-full">
                            <Zap className="w-3 h-3 text-purple-600" />
                        </div>
                        <span className="text-xs font-bold text-slate-700">Workflow Copilot</span>
                    </div>
                    <form onSubmit={handleChatSubmit} className="flex space-x-2">
                        <input
                            className="flex-1 text-xs border rounded px-2 py-1 outline-none focus:border-purple-500 disabled:bg-gray-100"
                            placeholder="Type to edit (e.g. 'Add Slack')..."
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            disabled={isProcessing}
                        />
                        <button
                            type="submit"
                            className="bg-purple-600 text-white text-xs px-2 rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={isProcessing}
                        >
                            {isProcessing ? '...' : 'Ask'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
};

export default WorkflowBuilder;
