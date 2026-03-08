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
import AddStepEdge from './AddStepEdge';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import { useKeyPress } from 'reactflow';
import PiecesSidebar, { Piece, PieceAction, PieceTrigger } from './PiecesSidebar';
import { LogsSidebar } from './LogsSidebar';
import SmartSuggestions, { StepSuggestion } from './SmartSuggestions';
import { Button } from "@/components/ui/button";
import { Plus, Save, Zap, Monitor, Globe, Mail, Clock, Sparkles, PanelLeftClose, PanelLeft, Loader2, Settings2, Undo, Redo, RotateCcw, Activity, List, Play, CheckCircle2, PauseCircle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import NodeConfigSidebar from './NodeConfigSidebar';
import { VoiceInput } from '@/components/Voice/VoiceInput';
import OptimizationPanel, { OptimizationSuggestion as IOptimizationSuggestion } from './OptimizationPanel';

const initialNodes: Node[] = [
    {
        id: '1',
        type: 'trigger',
        position: { x: 300, y: 0 },
        data: {
            label: '📧 Inbound Lead Email',
            integration: 'Gmail / Webhook',
            description: 'Triggers when a new B2B lead email is received',
            schema: { type: 'object', properties: { from: { type: 'string' }, subject: { type: 'string' }, body: { type: 'string' } } }
        },
    },
    {
        id: '2',
        type: 'ai_node',
        position: { x: 300, y: 160 },
        data: {
            label: '🧠 NLU Parse Lead Intent',
            model: 'Qwen-Plus',
            prompt: 'Extract: company name, budget, urgency, product interest from email body. Return JSON.',
            description: 'AI extracts structured lead data from raw email'
        },
    },
    {
        id: '3',
        type: 'action',
        position: { x: 300, y: 320 },
        data: {
            label: '📋 Update Zoho CRM',
            service: 'Zoho',
            action: 'Create / Update Lead',
            description: 'Pushes extracted lead data into Zoho CRM as a new contact',
        },
    },
    {
        id: '4',
        type: 'action',
        position: { x: 300, y: 480 },
        data: {
            label: '🎥 Generate Zoom Meeting Link',
            service: 'Zoom',
            action: 'Create Meeting',
            description: 'Auto-schedules a discovery call and generates a unique Zoom link',
        },
    },
    {
        id: '5',
        type: 'action',
        position: { x: 300, y: 640 },
        data: {
            label: '✋ Slack HITL Approval',
            service: 'Slack',
            action: 'Send Approval Request',
            description: 'Pauses workflow — sends lead summary + Zoom link to #sales-leads for human approval before outreach',
        },
    },
];

const initialEdges: Edge[] = [
    { id: 'e1-2', source: '1', target: '2', type: 'addStepEdge' },
    { id: 'e2-3', source: '2', target: '3', type: 'addStepEdge' },
    { id: 'e3-4', source: '3', target: '4', type: 'addStepEdge' },
    { id: 'e4-5', source: '4', target: '5', type: 'addStepEdge' },
];

const edgeTypes = {
    addStepEdge: AddStepEdge,
};

interface WorkflowBuilderProps {
    onSave?: (data: { nodes: Node[]; edges: Edge[] }) => void;
    initialData?: { nodes: Node[]; edges: Edge[] };
    workflowId?: string;
}

const WorkflowBuilder: React.FC<WorkflowBuilderProps> = ({ onSave: onSaveProp, initialData, workflowId }) => {
    // Use prop data if available, otherwise fallback to default initialNodes
    const [nodes, setNodes, onNodesChange] = useNodesState(initialData?.nodes || initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialData?.edges || initialEdges);
    const { toast } = useToast();

    // Undo/Redo Hook
    const { undo, redo, takeSnapshot, canUndo, canRedo, history } = useUndoRedo({ nodes, edges });

    // Performance Mode State
    const [isPerformanceMode, setIsPerformanceMode] = useState(false);
    const [analyticsData, setAnalyticsData] = useState<Record<string, any> | null>(null);

    // Optimization State
    const [isOptimizationOpen, setIsOptimizationOpen] = useState(false);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [optimizationSuggestions, setOptimizationSuggestions] = useState<IOptimizationSuggestion[]>([]);

    const handleOptimize = async () => {
        setIsOptimizationOpen(true);
        setIsOptimizing(true);

        // 1. Serialize Workflow (Minimal representation for analysis)
        // Map edges to find next_steps
        const nextStepsMap: Record<string, string[]> = {};
        edges.forEach(edge => {
            if (!nextStepsMap[edge.source]) nextStepsMap[edge.source] = [];
            nextStepsMap[edge.source].push(edge.target);
        });

        const workflowPayload = {
            workflow: {
                workflow_id: workflowId || 'preview',
                steps: nodes.map(node => ({
                    step_id: node.id,
                    step_type: node.type, // Map to backend type if needed
                    description: node.data.label || node.id,
                    parameters: node.data, // Pass full data as parameters for now (contains inputs)
                    next_steps: nextStepsMap[node.id] || []
                }))
            }
        };

        try {
            const res = await fetch('/api/workflows/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(workflowPayload.workflow) // The proxy expects body to be the workflow dict? verify proxy
            });
            // Proxy: body: JSON.stringify(req.body) -> Backend: request.workflow
            // So we should send { workflow: ... } to proxy?
            // Proxy logic: body: JSON.stringify(req.body). So if I send { workflow: ... }, backend gets { workflow: ... }
            // Backend OptimizeRequest expects { workflow: Dict }
            // So yes, fetch('/api/workflows/optimize', body: JSON.stringify({ workflow: ... }))

            if (res.ok) {
                const data = await res.json();
                setOptimizationSuggestions(data.suggestions || []);
            } else {
                toast({ title: "Optimization Failed", description: "Could not analyze workflow.", variant: "error" });
            }
        } catch (e) {
            console.error(e);
            toast({ title: "Optimization Error", description: String(e), variant: "error" });
        } finally {
            setIsOptimizing(false);
        }
    };

    // Sync history to state when undo/redo occurs
    React.useEffect(() => {
        if (history.present) {
            setNodes(history.present.nodes);
            setEdges(history.present.edges);
        }
    }, [history.present, setNodes, setEdges]);

    // Fetch Analytics Effect
    React.useEffect(() => {
        if (isPerformanceMode && workflowId) {
            const fetchAnalytics = async () => {
                try {
                    const res = await fetch(`/api/analytics/workflows/${workflowId}/heatmap`);
                    if (res.ok) {
                        const data = await res.json();
                        setAnalyticsData(data);
                        toast({ title: "Performance Mode", description: "Loaded execution heatmap." });
                    }
                } catch (e) {
                    console.error("Failed to load analytics", e);
                }
            };
            fetchAnalytics();
        } else if (!isPerformanceMode) {
            setAnalyticsData(null);
        }
    }, [isPerformanceMode, workflowId, toast]);

    // Inject Analytics Data into Nodes
    React.useEffect(() => {
        if (!analyticsData) {
            // Clear analytics data if mode is off
            setNodes((nds) => nds.map(n => {
                if (n.data && n.data._analytics) {
                    const { _analytics, ...restData } = n.data;
                    return { ...n, data: restData };
                }
                return n;
            }));
            return;
        }

        setNodes((nds) => nds.map((node) => {
            const stats = analyticsData[node.id] || analyticsData[node.data.action] || analyticsData[node.data.label];

            if (stats) {
                return {
                    ...node,
                    data: {
                        ...node.data,
                        _analytics: {
                            duration: stats.avg_duration,
                            status: stats.status === 'red' ? 'error' : 'success'
                        }
                    }
                };
            }
            return node;
        }));
    }, [analyticsData, setNodes]);

    // Inject workflowId into nodes whenever it changes
    React.useEffect(() => {
        if (workflowId && nodes.length > 0) {
            setNodes((nds) =>
                nds.map((node) => {
                    // Avoid infinite loop if ID is already set
                    if (node.data?._workflowId === workflowId) return node;

                    return {
                        ...node,
                        data: {
                            ...node.data,
                            id: node.id, // Inject ID so CustomNode can access data.id
                            _workflowId: workflowId // Inject ID for child nodes to use
                        }
                    };
                })
            );
        }
    }, [workflowId, nodes.length]); // Re-run when ID changes or new nodes added

    // Keyboard Shortcuts
    React.useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if ((event.metaKey || event.ctrlKey) && event.key === 'z') {
                if (event.shiftKey) {
                    redo();
                } else {
                    undo();
                }
                event.preventDefault();
            }
            if ((event.metaKey || event.ctrlKey) && (event.key === 'y')) {
                redo();
                event.preventDefault();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [undo, redo]);

    // Sidebar state - default to visible
    const [showSidebar, setShowSidebar] = useState(true);
    const [showLogs, setShowLogs] = useState(false); // [NEW] Logs Panel State
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [pendingEdgeInsertion, setPendingEdgeInsertion] = useState<string | null>(null);

    const onConnect = useCallback(
        (params: Connection) => {
            // Snapshot before change (using current state)
            const newEdges = addEdge({ ...params, type: 'addStepEdge' }, edges);
            takeSnapshot({ nodes, edges: newEdges });
            setEdges(newEdges);
        },
        [edges, nodes, setEdges, takeSnapshot]
    );

    const handleAddStepClick = useCallback((edgeId: string) => {
        setPendingEdgeInsertion(edgeId);
        setShowSidebar(true);
        toast({
            title: "Add Step",
            description: "Select an integration to insert into the workflow.",
        });
    }, [toast]);

    // Handler for adding pieces from the PiecesSidebar
    const handlePieceSelect = useCallback((piece: Piece, type: 'trigger' | 'action', item: PieceAction | PieceTrigger) => {
        const id = `${Date.now()}`;

        if (pendingEdgeInsertion) {
            // Insertion logic
            const edge = edges.find(e => e.id === pendingEdgeInsertion);
            if (edge) {
                const sourceNode = nodes.find(n => n.id === edge.source);
                const targetNode = nodes.find(n => n.id === edge.target);

                if (sourceNode && targetNode) {
                    // Calculate position between nodes
                    const newX = (sourceNode.position.x + targetNode.position.x) / 2;
                    const newY = (sourceNode.position.y + targetNode.position.y) / 2;

                    const newNode: Node = {
                        id,
                        type: type === 'trigger' ? 'trigger' : 'action',
                        position: { x: newX, y: newY },
                        data: {
                            label: item.name,
                            service: piece.name,
                            serviceId: piece.id,
                            action: item.id,
                            description: item.description,
                        },
                    };


                    // Snapshot before modifying
                    const newNodes = [...nodes, newNode];

                    // Replace old edge with two new ones
                    setEdges((eds) => {
                        const filtered = eds.filter(e => e.id !== pendingEdgeInsertion);
                        const newEdgeList = [
                            ...filtered,
                            {
                                id: `e${edge.source}-${id}`,
                                source: edge.source,
                                target: id,
                                type: 'addStepEdge',
                                sourceHandle: edge.sourceHandle
                            },
                            {
                                id: `e${id}-${edge.target}`,
                                source: id,
                                target: edge.target,
                                type: 'addStepEdge',
                                targetHandle: edge.targetHandle
                            }
                        ];
                        // Snapshot with calculated new state
                        takeSnapshot({ nodes: newNodes, edges: newEdgeList });
                        return newEdgeList;
                    });

                    setNodes(newNodes);

                    setPendingEdgeInsertion(null);
                    toast({
                        title: `Inserted ${piece.name}`,
                        description: `Step "${item.name}" added between steps.`,
                    });
                    return;
                }
            }
        }

        // Standard append logic (if no insertion pending)
        // Calculate position: place new nodes vertically below existing ones
        const maxY = nodes.reduce((max, node) => Math.max(max, node.position.y), 0);
        const newY = maxY + 150;

        const newNode: Node = {
            id,
            type: type === 'trigger' ? 'trigger' : 'action',
            position: { x: 300, y: newY },
            data: {
                label: item.name,
                service: piece.name,
                serviceId: piece.id,
                action: item.id,
                description: item.description,
            },
        };

        // Create new edge if needed
        let newEdge: Edge | null = null;
        if (nodes.length > 0) {
            const lastNode = nodes[nodes.length - 1];
            newEdge = {
                id: `e${lastNode.id}-${id}`,
                source: lastNode.id,
                target: id,
                type: 'addStepEdge'
            };
        }

        const newNodes = [...nodes, newNode];
        const newEdges = newEdge ? [...edges, newEdge] : edges;

        setNodes(newNodes);
        if (newEdge) setEdges(newEdges);

        takeSnapshot({ nodes: newNodes, edges: newEdges });

        toast({
            title: `Added ${piece.name}`,
            description: `${type === 'trigger' ? 'Trigger' : 'Action'}: ${item.name}`,
        });
    }, [nodes, edges, pendingEdgeInsertion, setNodes, setEdges, toast]);

    // Handle node selection for configuration
    const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
        setSelectedNodeId(node.id);
    }, []);

    const handleUpdateNode = useCallback((nodeId: string, newData: any) => {
        setNodes((nds) =>
            nds.map((node) => {
                if (node.id === nodeId) {
                    return { ...node, data: newData };
                }
                return node;
            })
        );
    }, [setNodes]);

    // Handler for smart suggestions
    const handleSuggestionClick = useCallback((suggestion: StepSuggestion) => {
        // Convert suggestion to a node
        const typeMap: Record<string, string> = {
            'action': 'action',
            'trigger': 'trigger',
            'condition': 'condition',
            'ai_node': 'ai_node',
            'loop': 'loop',
        };
        const nodeType = typeMap[suggestion.type] || 'action';
        addNode(nodeType);

        toast({
            title: `Added ${suggestion.title}`,
            description: suggestion.reason,
        });
    }, [toast]);

    const addNode = (type: string) => {
        const id = `${nodes.length + 1}`;
        let data: any = { label: `${type} node` };

        // Set default data based on node type
        switch (type) {
            case 'email':
                data = { label: 'Send Email', recipient: 'user@example.com', subject: 'Notification' };
                break;
            case 'http':
                data = { label: 'HTTP Request', method: 'GET', url: 'https://api.example.com' };
                break;
            case 'timer':
                data = { label: 'Delay', duration: '5', unit: 'minutes' };
                break;
            case 'ai_node':
                data = { label: 'AI Processing', model: 'GPT-4', prompt: 'Analyze input...' };
                break;
            case 'desktop':
                data = { label: 'Desktop Action', app: 'Excel', action: 'Open' };
                break;
            case 'condition':
                data = { label: 'Condition', condition: 'If true' };
                break;
            case 'action':
                data = { label: 'Generic Action', action: 'Do something' };
                break;
            case 'loop':
                data = { label: 'Loop', iterateOver: '{{previousStep.items}}', maxIterations: 100 };
                break;
            case 'approval':
                data = { label: 'Wait for Approval', message: 'Please approve to continue', timeout: '24 hours' };
                break;
            case 'code':
                data = {
                    label: 'Code',
                    language: 'TypeScript',
                    code: `// Write your code here\nexport const code = async (inputs) => {\n  return { result: inputs.data };\n};`,
                    npmPackages: []
                };
                break;
            case 'table':
                data = { label: 'Tables', action: 'Insert Row', tableName: '' };
                break;
            case 'subflow':
                data = { label: 'Sub Flow', flowName: '', async: false };
                break;
        }

        const newNode: Node = {
            id,
            type,
            position: { x: Math.random() * 400 + 50, y: Math.random() * 400 + 50 },
            data,
        };
        setNodes((nds) => {
            const newNodes = nds.concat(newNode);
            takeSnapshot({ nodes: newNodes, edges });
            return newNodes;
        });
    };

    const addServiceNode = (service: string) => {
        const id = `${nodes.length + 1}`;
        const newNode: Node = {
            id,
            type: 'action',
            position: { x: Math.random() * 400, y: Math.random() * 400 },
            data: { label: `${service} Action`, service: service, action: 'Perform Action' },
        };
        setNodes((nds) => {
            const newNodes = nds.concat(newNode);
            takeSnapshot({ nodes: newNodes, edges });
            return newNodes;
        });
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
            const workflowActions = nluResult.rawSubAgentResponses?.workflow?.actions;

            if (primaryGoal === 'workflow' || service !== 'general') {
                // Service-specific nodes mapping
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
                    'hubspot': 'HubSpot',
                    'salesforce': 'Salesforce',
                    'discord': 'Discord',
                    'stripe': 'Stripe',
                    'jira': 'Jira',
                    'zendesk': 'Zendesk',
                    'figma': 'Figma',
                    'twilio': 'Twilio',
                    'excel': 'Excel',
                    'teams': 'Microsoft Teams',
                    'outlook': 'Outlook',
                    'word': 'Word',
                    'powerpoint': 'PowerPoint',
                    'onenote': 'OneNote',
                    'forms': 'Google Forms',
                    'google_forms': 'Google Forms',
                    'microsoft_forms': 'Microsoft Forms',
                    'planner': 'Planner'
                };

                const isNewWorkflow = message.toLowerCase().includes('create') || (workflowActions && workflowActions.length > 1);

                // Force reset if new workflow
                let currentNodes = isNewWorkflow ? [] : [...nodes];
                let currentEdges = isNewWorkflow ? [] : [...edges];

                if (isNewWorkflow) {
                    setNodes([]);
                    setEdges([]);
                    // We'll snapshot after generation
                    toast({ title: "AI Copilot", description: "Starting new workflow..." });
                }

                // Helper to add node with auto-layout
                const addNodeAuto = (label: string, service: string, index: number, total: number) => {
                    const id = (currentNodes.length + 1).toString();
                    const isTrigger = index === 0 && total > 1; // Assume first node is trigger for multi-step
                    const type = isTrigger ? 'trigger' : 'action';

                    // Smart Layout: Top to Bottom placement
                    const x = 250;
                    const y = index * 200 + 50;

                    const newNode: Node = {
                        id,
                        type,
                        position: { x, y },
                        data: {
                            label: isTrigger ? `${label} Trigger` : `${label} Action`,
                            service: service, // Pass service for styling 
                            action: 'Perform Action'
                        },
                    };

                    currentNodes.push(newNode);

                    // Auto-connect to previous node
                    if (index > 0) {
                        const prevNode = currentNodes[index - 1];
                        if (prevNode) {
                            const newEdge: Edge = {
                                id: `e${prevNode.id}-${id}`,
                                source: prevNode.id,
                                target: id
                            };
                            currentEdges.push(newEdge);
                        }
                    }
                    return newNode;
                };

                // Handle Multi-Node Workflow Response
                if (workflowActions && Array.isArray(workflowActions) && workflowActions.length > 0) {
                    let addedCount = 0;
                    workflowActions.forEach((act: any, index: number) => {
                        const svc = act.service?.toLowerCase();
                        if (svc) {
                            const mappedService = serviceMap[svc] || svc.charAt(0).toUpperCase() + svc.slice(1);
                            addNodeAuto(mappedService, mappedService, index, workflowActions.length);
                            addedCount++;
                        }
                    });

                    if (addedCount > 0) {
                        setNodes(currentNodes);
                        setEdges(currentEdges);
                        takeSnapshot({ nodes: currentNodes, edges: currentEdges });
                        toast({ title: "AI Copilot", description: `Generated ${addedCount} steps workflow.` });
                        return;
                    }
                }

                // Fallback to single node if no actions array
                const serviceName = serviceMap[service] || service.charAt(0).toUpperCase() + service.slice(1);
                addServiceNode(serviceName); // Fallback to random placement for single nodes
                toast({ title: "AI Copilot", description: `Added ${serviceName} node via NLU.` });

            } else if (message.toLowerCase().includes('clear') || message.toLowerCase().includes('reset')) {
                setNodes([]);
                setEdges([]);
                takeSnapshot({ nodes: [], edges: [] });
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
                toast({ title: "AI Copilot", description: `Intent: ${primaryGoal} | Service: ${service}. Try specifying a service like Slack, GMail, or GitHub.` });
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
                takeSnapshot({ nodes: [], edges: [] });
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
    const [isDemoRunning, setIsDemoRunning] = useState(false);
    const [demoLog, setDemoLog] = useState<Array<{ nodeId: string; title: string; output: React.ReactNode; status: 'running' | 'success' | 'paused' }>>([]);
    const [showDemoPanel, setShowDemoPanel] = useState(false);

    const DEMO_STEPS = [
        {
            title: '📧 Inbound Lead Email received',
            duration: 1800,
            output: (
                <div className="space-y-1 text-xs">
                    <div className="bg-gray-50 border rounded p-2 font-mono text-[11px] space-y-1">
                        <div><span className="text-gray-400">From:</span> <span className="text-blue-700 font-semibold">james.chen@velocitytech.io</span></div>
                        <div><span className="text-gray-400">Subject:</span> <span className="font-medium">Interested in ATOM for our sales team (~200 reps)</span></div>
                        <div className="mt-1 text-gray-600">"Hi, we're scaling rapidly and need a workflow automation platform. Budget approved: $80k/year. Can we connect this week?"</div>
                    </div>
                    <div className="text-green-600 font-semibold text-[11px]">✓ Webhook triggered · Lead captured</div>
                </div>
            )
        },
        {
            title: '🧠 AI parsing lead intent (Qwen-Plus)',
            duration: 2200,
            output: (
                <div className="space-y-1 text-xs">
                    <div className="text-gray-400 text-[10px] mb-1">Extracting structured data...</div>
                    <pre className="bg-slate-900 text-green-400 p-2 rounded text-[10px] font-mono overflow-auto">{`{
  "company": "VelocityTech",
  "contact": "James Chen",
  "email": "james.chen@velocitytech.io",
  "budget": "$80,000/year",
  "team_size": "~200 reps",
  "urgency": "HIGH",
  "intent": "purchase",
  "confidence": 0.97
}`}</pre>
                    <div className="text-purple-600 font-semibold text-[11px]">✓ Intent parsed · Confidence 97%</div>
                </div>
            )
        },
        {
            title: '📋 Creating lead in Zoho CRM',
            duration: 1600,
            output: (
                <div className="space-y-1 text-xs">
                    <div className="bg-blue-50 border border-blue-200 rounded p-2 text-[11px] space-y-1">
                        <div className="font-semibold text-blue-800">✓ Lead Created — ID #ZCR-29841</div>
                        <div className="text-gray-600 space-y-0.5">
                            <div><span className="font-medium">Name:</span> James Chen</div>
                            <div><span className="font-medium">Company:</span> VelocityTech</div>
                            <div><span className="font-medium">Pipeline:</span> Enterprise Sales</div>
                            <div><span className="font-medium">Deal Value:</span> $80,000</div>
                            <div><span className="font-medium">Stage:</span> New Inbound → Qualified</div>
                        </div>
                    </div>
                    <div className="text-blue-600 font-semibold text-[11px]">✓ CRM updated · Pipeline advanced</div>
                </div>
            )
        },
        {
            title: '🎥 Generating Zoom discovery call',
            duration: 1400,
            output: (
                <div className="space-y-1 text-xs">
                    <div className="bg-blue-50 border border-blue-100 rounded p-2 text-[11px] space-y-1">
                        <div className="font-semibold text-blue-700">Discovery Call Scheduled</div>
                        <div className="text-gray-600"><span className="font-medium">Date:</span> Mon Mar 10, 2026 · 3:00 PM IST</div>
                        <div className="text-gray-600"><span className="font-medium">Duration:</span> 30 min</div>
                        <div className="mt-1 p-1.5 bg-white border rounded font-mono text-[10px] text-blue-600 break-all">
                            https://zoom.us/j/92847301928?pwd=xK9mP
                        </div>
                    </div>
                    <div className="text-blue-600 font-semibold text-[11px]">✓ Zoom link generated · Calendar invite sent</div>
                </div>
            )
        },
        {
            title: '✋ Slack HITL — Awaiting approval',
            duration: 0,
            output: (
                <div className="space-y-2 text-xs">
                    <div className="bg-[#4A154B] text-white rounded p-2 text-[11px] space-y-1">
                        <div className="font-bold text-[12px]">#sales-leads · ATOM Bot</div>
                        <div>🚨 <span className="font-semibold">New high-value lead</span> needs approval before outreach</div>
                        <div className="bg-white/10 rounded p-1.5 text-[10px] space-y-0.5 mt-1">
                            <div>👤 James Chen · VelocityTech</div>
                            <div>💰 Budget: $80k/year · 200 reps</div>
                            <div>⚡ Urgency: HIGH</div>
                            <div className="text-blue-300 mt-1">🔗 zoom.us/j/92847301928</div>
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <button className="flex-1 bg-green-500 hover:bg-green-600 text-white text-[11px] py-1.5 rounded font-semibold transition-colors">
                            ✓ Approve Outreach
                        </button>
                        <button className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 text-[11px] py-1.5 rounded font-semibold transition-colors">
                            ✗ Reject
                        </button>
                    </div>
                    <div className="text-amber-600 font-semibold text-[11px] animate-pulse">⏸ Workflow paused · Waiting for sales rep...</div>
                </div>
            )
        }
    ];

    const runDemoAnimation = async () => {
        if (isDemoRunning) return;
        setIsDemoRunning(true);
        setDemoLog([]);
        setShowDemoPanel(true);

        // Reset all nodes first
        setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, _demoStatus: undefined } })));
        await new Promise(r => setTimeout(r, 300));

        const nodeIds = nodes.map(n => n.id);
        const lastIdx = nodeIds.length - 1;

        for (let i = 0; i < nodeIds.length; i++) {
            const id = nodeIds[i];
            const isLast = i === lastIdx;
            const step = DEMO_STEPS[i] || DEMO_STEPS[DEMO_STEPS.length - 1];

            // Add "running" log entry
            setDemoLog(prev => [...prev, {
                nodeId: id,
                title: step.title,
                output: <div className="text-yellow-600 text-[11px] flex items-center gap-1"><span className="w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin inline-block" /> Processing...</div>,
                status: 'running'
            }]);

            // Set node running
            setNodes(nds => nds.map(n => ({
                ...n,
                data: {
                    ...n.data,
                    _demoStatus: n.id === id ? 'running'
                        : n.data._demoStatus === 'success' || n.data._demoStatus === 'paused' ? n.data._demoStatus
                            : undefined
                }
            })));

            // Animate edge
            setEdges(eds => eds.map(e => ({
                ...e,
                animated: e.source === id || e.target === id,
                style: e.source === id ? { stroke: '#8b5cf6', strokeWidth: 2.5 } : {}
            })));

            await new Promise(r => setTimeout(r, step.duration || 1500));

            // Update log with real output
            const finalStatus = isLast ? 'paused' : 'success';
            setDemoLog(prev => prev.map(entry =>
                entry.nodeId === id ? { ...entry, output: step.output, status: finalStatus } : entry
            ));

            // Update node status
            setNodes(nds => nds.map(n => ({
                ...n,
                data: {
                    ...n.data,
                    _demoStatus: n.id === id ? finalStatus : n.data._demoStatus
                }
            })));

            await new Promise(r => setTimeout(r, 300));
        }

        setEdges(eds => eds.map(e => ({ ...e, animated: false, style: {} })));
        setIsDemoRunning(false);
    };

    return (
        <div className="h-[700px] w-full border rounded-lg bg-white dark:bg-gray-900 shadow-sm flex flex-col overflow-hidden">
            {/* AI Copilot Header - Promoted Position */}
            <div className="bg-gradient-to-r from-purple-50 via-blue-50 to-purple-50 border-b p-4">
                <div className="flex items-center gap-3 mb-3">
                    <div className="bg-purple-100 p-2 rounded-full">
                        <Sparkles className="w-5 h-5 text-purple-600" />
                    </div>
                    <div>
                        <h3 className="font-bold text-gray-800 dark:text-gray-200">AI Workflow Builder</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Describe what you want to automate</p>
                    </div>
                </div>
                <form onSubmit={handleChatSubmit} className="flex gap-2 items-center">
                    <VoiceInput
                        onTranscriptChange={(text) => setChatInput(text)}
                        className="mr-1"
                    />
                    <input
                        className="flex-1 text-sm border rounded-lg px-4 py-2.5 outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-100 disabled:bg-gray-100 dark:bg-gray-800 shadow-sm"
                        placeholder="e.g., 'When I get an email, summarize it with AI and post to Slack'"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        disabled={isProcessing}
                    />
                    <Button type="submit" disabled={isProcessing} className="bg-purple-600 hover:bg-purple-700">
                        {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                        {isProcessing ? 'Generating...' : 'Generate'}
                    </Button>
                </form>
            </div>

            {/* Toolbar */}
            <div className="p-3 border-b flex justify-between items-center bg-gray-50 dark:bg-gray-800">
                <div className="flex items-center gap-2">
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setShowSidebar(!showSidebar)}
                        className="text-gray-600 dark:text-gray-400"
                    >
                        {showSidebar ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
                    </Button>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {nodes.length} steps • {edges.length} connections
                    </span>
                </div>
                <div className="flex gap-1 flex-wrap items-center">
                    <div className="flex bg-white dark:bg-gray-900 rounded-md border mr-2 items-center">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-gray-500 dark:text-gray-400 hover:text-black"
                            onClick={undo}
                            disabled={!canUndo}
                            title="Undo (Ctrl+Z)"
                        >
                            <Undo className="w-4 h-4" />
                        </Button>
                        <div className="w-[1px] h-4 bg-gray-200 dark:bg-gray-800"></div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-gray-500 dark:text-gray-400 hover:text-black"
                            onClick={redo}
                            disabled={!canRedo}
                            title="Redo (Ctrl+Shift+Z)"
                        >
                            <Redo className="w-4 h-4" />
                        </Button>
                    </div>

                    <Button
                        size="sm"
                        variant={isPerformanceMode ? "secondary" : "outline"}
                        className={isPerformanceMode ? "bg-amber-100 text-amber-900 border-amber-200 hover:bg-amber-200" : ""}
                        onClick={() => {
                            if (!workflowId && !isPerformanceMode) {
                                toast({
                                    title: "Performance Unavailable",
                                    description: "Please save or select a workflow to view execution data.",
                                    variant: "error"
                                });
                                return;
                            }
                            setIsPerformanceMode(!isPerformanceMode);
                        }}
                    >
                        <Activity className="w-3 h-3 mr-1" />
                        {isPerformanceMode ? "Performance ON" : "Performance"}
                    </Button>

                    {/* Run Demo Button */}
                    <Button
                        size="sm"
                        onClick={runDemoAnimation}
                        disabled={isDemoRunning}
                        className={`${isDemoRunning
                            ? 'bg-green-500 text-white animate-pulse cursor-not-allowed'
                            : 'bg-green-600 hover:bg-green-700 text-white'
                            } font-semibold shadow-sm`}
                    >
                        {isDemoRunning
                            ? <><span className="w-3 h-3 mr-1 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />Running...</>
                            : <><Play className="w-3 h-3 mr-1" />▶ Run Demo</>
                        }
                    </Button>

                    <Button
                        size="sm"
                        variant="outline"
                        className="bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100"
                        onClick={handleOptimize}
                    >
                        <Sparkles className="w-3 h-3 mr-1" />
                        Optimize
                    </Button>

                    <Button
                        size="sm"
                        variant={showLogs ? "secondary" : "outline"}
                        className={showLogs ? "bg-blue-100 text-blue-900 border-blue-200" : ""}
                        onClick={() => setShowLogs(!showLogs)}
                    >
                        <List className="w-3 h-3 mr-1" />
                        Logs
                    </Button>

                    <Button size="sm" variant="outline" onClick={() => addNode('condition')}>
                        <Plus className="w-3 h-3 mr-1" /> Condition
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('loop')}>
                        <svg className="w-3 h-3 mr-1 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Loop
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('code')}>
                        <svg className="w-3 h-3 mr-1 text-slate-600 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                        Code
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('ai_node')}>
                        <Zap className="w-3 h-3 mr-1 text-purple-500" /> AI
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('approval')}>
                        <svg className="w-3 h-3 mr-1 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        Approval
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addNode('timer')}>
                        <Clock className="w-3 h-3 mr-1" /> Delay
                    </Button>
                    <Button size="sm" onClick={onSave} className="ml-2">
                        <Save className="w-3 h-3 mr-1" /> Save
                    </Button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex min-h-0">
                {/* Pieces Sidebar */}
                {showSidebar && (
                    <PiecesSidebar onSelectPiece={handlePieceSelect} className="w-72 flex-shrink-0" />
                )}
                {/* Flow Canvas */}
                <div className="flex-1 min-h-0 relative">
                    <ReactFlowProvider>
                        <ReactFlow
                            nodes={nodes}
                            edges={edges.map(edge => ({
                                ...edge,
                                data: { ...edge.data, onAddStep: handleAddStepClick }
                            }))}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            onConnect={onConnect}
                            onNodeClick={onNodeClick}
                            nodeTypes={nodeTypes}
                            edgeTypes={edgeTypes}
                            fitView
                            onNodeDragStop={() => takeSnapshot({ nodes, edges })}
                            onNodesDelete={() => takeSnapshot({ nodes, edges })}
                            onEdgesDelete={() => takeSnapshot({ nodes, edges })}
                        >
                            <Background />
                            <Controls />
                        </ReactFlow>
                    </ReactFlowProvider>
                    {showLogs && workflowId && (
                        <LogsSidebar workflowId={workflowId} onClose={() => setShowLogs(false)} />
                    )}
                </div>

                {/* Demo Live Output Panel */}
                {showDemoPanel && demoLog.length > 0 && (
                    <div className="w-80 flex-shrink-0 border-l bg-white dark:bg-gray-900 flex flex-col overflow-hidden">
                        <div className="p-3 border-b bg-gradient-to-r from-purple-50 to-blue-50 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                {isDemoRunning
                                    ? <span className="w-3 h-3 border-2 border-purple-600 border-t-transparent rounded-full animate-spin inline-block" />
                                    : <CheckCircle2 className="w-4 h-4 text-green-500" />
                                }
                                <span className="text-sm font-bold text-gray-800">
                                    {isDemoRunning ? 'Workflow running...' : 'Run complete ✓'}
                                </span>
                            </div>
                            <button onClick={() => { setShowDemoPanel(false); setDemoLog([]); setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, _demoStatus: undefined } }))); }} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 space-y-3">
                            {demoLog.map((entry, idx) => (
                                <div key={idx} className={`rounded-lg border p-3 transition-all duration-300 ${entry.status === 'running' ? 'border-yellow-300 bg-yellow-50' :
                                    entry.status === 'paused' ? 'border-amber-300 bg-amber-50' :
                                        'border-green-200 bg-green-50'
                                    }`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        {entry.status === 'running'
                                            ? <span className="w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin inline-block flex-shrink-0" />
                                            : entry.status === 'paused'
                                                ? <PauseCircle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                                                : <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />
                                        }
                                        <span className="text-[11px] font-bold text-gray-700 leading-tight">{entry.title}</span>
                                    </div>
                                    <div>{entry.output}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Node Configuration Sidebar */}
                {selectedNodeId && (
                    <div className="absolute top-0 right-0 h-full z-20 pointer-events-auto">
                        <NodeConfigSidebar
                            selectedNode={nodes.find(n => n.id === selectedNodeId)}
                            allNodes={nodes}
                            onClose={() => setSelectedNodeId(null)}
                            onUpdateNode={handleUpdateNode}
                        />
                    </div>
                )}

                {/* Empty State Hint */}
                {nodes.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="text-center p-8 bg-white/80 dark:bg-gray-900/80 rounded-lg shadow-sm">
                            <Sparkles className="w-12 h-12 text-purple-300 mx-auto mb-3" />
                            <h4 className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Start Building Your Workflow</h4>
                            <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs">
                                Describe your automation above, or browse pieces on the left
                            </p>
                        </div>
                    </div>
                )}

                {/* Smart Suggestions Panel */}
                {nodes.length > 0 && (
                    <div className="absolute bottom-4 right-4 w-72 z-10 pointer-events-auto">
                        <SmartSuggestions
                            nodes={nodes}
                            edges={edges}
                            onSuggestionClick={handleSuggestionClick}
                        />
                    </div>
                )}
            </div>

            {/* Optimization Panel */}
            <OptimizationPanel
                open={isOptimizationOpen}
                onOpenChange={setIsOptimizationOpen}
                isLoading={isOptimizing}
                suggestions={optimizationSuggestions}
                onApply={(suggestion) => {
                    toast({ title: "Feature Pending", description: "Auto-fix is coming soon!", variant: "default" });
                }}
            />
        </div>
    );
};

export default WorkflowBuilder;
