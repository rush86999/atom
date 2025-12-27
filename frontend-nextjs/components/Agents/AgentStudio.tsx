import React, { useState, useEffect } from "react";
import {
    Card,
    CardHeader,
    CardContent,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
    Plus,
    Edit,
    Play,
    Settings,
    Bot,
    Activity,
    Calendar,
    Code,
    Terminal,
    ThumbsDown,
    MessageSquare,
} from "lucide-react";
import axios from "axios";
import { useWebSocket } from "../../hooks/useWebSocket";

// --- Types ---
interface Agent {
    id: string;
    name: string;
    category: string;
    description?: string;
    status: string;
    configuration?: any;
    schedule_config?: any;
}

interface RunResponse {
    status: string;
    result?: any;
    agent_id?: string;
}

interface TraceStep {
    step?: number;
    type?: string;
    thought?: string;
    action?: any;
    output?: string;
    final_answer?: string;
    action_id?: string;
    reason?: string;
    status?: 'pending' | 'approved' | 'rejected';
}

const AgentStudio: React.FC = () => {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const { toast } = useToast();

    // Form State
    const [formData, setFormData] = useState({
        name: "",
        category: "Operations",
        description: "",
        systemPrompt: "You are a helpful specialty agent.",
        tools: "*",
        scheduleActive: false,
        cronExpression: "0 9 * * *", // Daily at 9am
        scheduledTask: "Perform daily analysis."
    });

    // Test Run State
    const [isRunning, setIsRunning] = useState(false);
    const [runInput, setRunInput] = useState("");
    const [runResult, setRunResult] = useState<string | null>(null);
    const [runTrace, setRunTrace] = useState<TraceStep[]>([]);

    // Feedback State
    const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
    const [feedbackStep, setFeedbackStep] = useState<TraceStep | null>(null);

    // --- WebSocket for Real-time Updates ---
    const { isConnected, lastMessage, subscribe } = useWebSocket();

    useEffect(() => {
        if (isConnected) {
            // Subscribe to default workspace channel for now
            // In a real app, this would be user.workspace_id
            subscribe("workspace:default");
        }
    }, [isConnected, subscribe]);

    useEffect(() => {
        if (lastMessage && (lastMessage as any).type === "agent_step_update") {
            const { agent_id, step } = lastMessage as any;

            // If the message is for the currently running agent, we append it
            if (isRunning && agent_id === selectedAgent?.id) {
                setRunTrace(prev => {
                    // Avoid duplicate steps if they were already added or if they come from sync response
                    if (prev.some(s => s.step === step.step && s.output === step.output)) return prev;

                    // If the step already exists but was pending output, update it
                    const existingIndex = prev.findIndex(s => s.step === step.step);
                    if (existingIndex > -1) {
                        const newTrace = [...prev];
                        newTrace[existingIndex] = { ...newTrace[existingIndex], ...step };
                        return newTrace;
                    }

                    return [...prev, step];
                });
            }
        }

        if (lastMessage && (lastMessage as any).type === "hitl_paused") {
            const { agent_id, action_id, tool, reason } = lastMessage as any;
            if (isRunning && agent_id === selectedAgent?.id) {
                setRunTrace(prev => [
                    ...prev,
                    {
                        type: "hitl_paused",
                        action_id,
                        action: { tool },
                        reason,
                        status: "pending"
                    }
                ]);
            }
        }

        if (lastMessage && (lastMessage as any).type === "hitl_decision") {
            const { action_id, decision } = lastMessage as any;
            setRunTrace(prev => prev.map(s =>
                s.action_id === action_id ? { ...s, status: decision === 'approved' ? 'approved' : 'rejected' } : s
            ));
        }

        if (lastMessage && (lastMessage as any).type === "agent_status_change") {
            const { agent_id, status, result } = lastMessage as any;
            if (isRunning && (agent_id === selectedAgent?.id || agent_id === "atom_main") && status === "success") {
                setRunResult(result.output || result.final_output || "Completed.");
                setIsRunning(false);
            }
        }
    }, [lastMessage, selectedAgent, isRunning]);
    const [feedbackText, setFeedbackText] = useState("");

    // --- Fetch Agents ---
    const fetchAgents = async () => {
        try {
            setIsLoading(true);
            const res = await axios.get("/api/agents/");
            setAgents(res.data as Agent[]);
        } catch (err) {
            console.error("Failed to fetch agents:", err);
            toast({ title: "Error", description: "Could not load agents", variant: "error" });
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchAgents();
    }, []);

    // --- Handlers ---
    const handleOpenCreate = () => {
        setSelectedAgent(null);
        setFormData({
            name: "",
            category: "Operations",
            description: "",
            systemPrompt: "You are a helpful specialty agent.",
            tools: "*",
            scheduleActive: false,
            cronExpression: "0 9 * * *",
            scheduledTask: "Perform daily analysis."
        });
        setIsModalOpen(true);
    };

    const handleOpenEdit = (agent: Agent) => {
        setSelectedAgent(agent);
        // Note: In real app, might need to fetch full detail if list is partial.
        // Assuming list returns enough for now or we rely on what we have.
        // If agent.configuration is missing, defaults will show. 
        // Ideally we GET /agents/{id} here.

        // Simplification for MVP:
        const config = agent.configuration || {};
        const sched = agent.schedule_config || {};

        setFormData({
            name: agent.name,
            category: agent.category || "Operations",
            description: agent.description || "",
            systemPrompt: config.system_prompt || "You are a helpful specialty agent.",
            tools: config.tools || "*",
            scheduleActive: sched.active || false,
            cronExpression: sched.cron_expression || "0 9 * * *",
            scheduledTask: config.scheduled_task || "Perform daily analysis."
        });
        setIsModalOpen(true);
    };

    const handleSave = async () => {
        try {
            const payload = {
                name: formData.name,
                category: formData.category,
                description: formData.description,
                configuration: {
                    system_prompt: formData.systemPrompt,
                    tools: formData.tools,
                    scheduled_task: formData.scheduledTask
                },
                schedule_config: {
                    active: formData.scheduleActive,
                    cron_expression: formData.cronExpression
                }
            };

            if (selectedAgent) {
                await axios.put(`/api/agents/${selectedAgent.id}`, payload);
                toast({ title: "Updated", description: "Agent updated successfully.", variant: "success" });
            } else {
                await axios.post("/api/agents/custom", payload);
                toast({ title: "Created", description: "Agent created successfully.", variant: "success" });
            }

            setIsModalOpen(false);
            fetchAgents();
        } catch (err: any) {
            console.error("Save failed:", err);
            toast({ title: "Error", description: err.response?.data?.detail || "Failed to save agent", variant: "error" });
        }
    };

    const handleTestRun = async (agentId: string) => {
        if (!runInput) return;
        try {
            setIsRunning(true);
            setRunResult(null);
            setRunTrace([]);

            // Request synchronous execution to get the trace
            const res = await axios.post<RunResponse>(`/api/agents/${agentId}/run`, {
                parameters: {
                    request: runInput,
                    sync: true
                }
            });

            if (res.data.status === "completed") {
                const output = res.data.result;

                // If it's a generic agent result with steps
                if (output && typeof output === 'object' && Array.isArray(output.steps)) {
                    setRunTrace(output.steps);
                    setRunResult(output.final_output || output.output || "Completed.");
                } else if (typeof output === 'object') {
                    setRunResult(JSON.stringify(output, null, 2));
                    setRunTrace([]);
                } else {
                    setRunResult(String(output));
                    setRunTrace([]);
                }

                toast({ title: "Task Completed", variant: "success" });
            } else {
                toast({ title: "Task Started", description: "Agent is running in background.", variant: "success" });
                setRunResult("Task dispatched (Async).");
            }

        } catch (err) {
            console.error(err);
            toast({ title: "Run Failed", variant: "error" });
            setRunResult("Error occurred.");
        } finally {
            setIsRunning(false);
        }
    };

    const handleOpenFeedback = (step: TraceStep) => {
        setFeedbackStep(step);
        setIsFeedbackOpen(true);
        setFeedbackText("");
    };

    const handleSubmitFeedback = async () => {
        if (!selectedAgent || !feedbackStep) return;
        try {
            await axios.post(`/api/agents/${selectedAgent.id}/feedback`, {
                original_output: `Action: ${JSON.stringify(feedbackStep.action)}\nOutput: ${feedbackStep.output}`,
                user_correction: feedbackText,
                input_context: `Step: ${feedbackStep.step}\nThought: ${feedbackStep.thought}`
            });
            toast({ title: "Feedback Submitted", description: "Agent will learn from this correction.", variant: "success" });
            setIsFeedbackOpen(false);
        } catch (err) {
            toast({ title: "Error", description: "Failed to submit feedback", variant: "error" });
        }
    };
    const handleHITLDecision = async (actionId: string, decision: 'approved' | 'rejected') => {
        try {
            await axios.post(`/api/agents/approvals/${actionId}`, { decision });
            toast({ title: `Action ${decision}`, variant: "success" });
        } catch (err) {
            toast({ title: "Error", description: "Failed to submit decision", variant: "error" });
        }
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Agent Studio</h2>
                    <p className="text-muted-foreground">Design, Schedule, and Manage Specialty Agents</p>
                </div>
                <Button onClick={handleOpenCreate}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create New Agent
                </Button>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {agents.map((agent) => (
                    <Card key={agent.id} className="flex flex-col">
                        <CardHeader>
                            <div className="flex justify-between items-start">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <Bot className="w-5 h-5 text-primary" />
                                        <CardTitle className="text-lg">{agent.name}</CardTitle>
                                    </div>
                                    <CardDescription>{agent.category}</CardDescription>
                                </div>
                                <Badge variant={agent.status === "active" ? "default" : "secondary"}>
                                    {agent.status}
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="flex-1 space-y-4">
                            <p className="text-sm text-gray-500 line-clamp-2">
                                {agent.description || "No description provided."}
                            </p>

                            <div className="flex gap-2 text-xs text-gray-400">
                                {/* Visual indicator if scheduled */}
                                {/* Note: List endpoint might not return schedule_config. 
                     If we need to know, we update endpoint or just assume inactive unless detail loaded.
                     For now, skip indicator or assume list returns it.
                 */}
                                {/* <div className="flex items-center gap-1">
                   <Calendar className="w-3 h-3" /> Scheduled
                 </div> */}
                            </div>

                            <div className="flex justify-end gap-2 mt-auto pt-4">
                                <Button variant="outline" size="sm" onClick={() => handleOpenEdit(agent)}>
                                    <Edit className="w-4 h-4 mr-2" />
                                    Configure
                                </Button>
                                {/* Quick Run Modal could be added here */}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Create/Edit Modal */}
            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>{selectedAgent ? "Edit Agent" : "Create Custom Agent"}</DialogTitle>
                    </DialogHeader>

                    <div className="grid gap-6 py-4">

                        {/* Identity */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} />
                            </div>
                            <div className="space-y-2">
                                <Label>Category</Label>
                                <Select value={formData.category} onValueChange={v => setFormData({ ...formData, category: v })}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="Operations">Operations</SelectItem>
                                        <SelectItem value="Finance">Finance</SelectItem>
                                        <SelectItem value="Marketing">Marketing</SelectItem>
                                        <SelectItem value="Sales">Sales</SelectItem>
                                        <SelectItem value="HR">HR</SelectItem>
                                        <SelectItem value="Engineering">Engineering</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>Description</Label>
                            <Input value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} />
                        </div>

                        {/* Brain */}
                        <div className="space-y-4 border p-4 rounded-md">
                            <div className="flex items-center gap-2">
                                <Code className="w-4 h-4" />
                                <h3 className="font-semibold">Behavior</h3>
                            </div>

                            <div className="space-y-2">
                                <Label>System Prompt / Instructions</Label>
                                <Textarea
                                    className="h-32 font-mono text-sm"
                                    value={formData.systemPrompt}
                                    onChange={e => setFormData({ ...formData, systemPrompt: e.target.value })}
                                />
                            </div>
                        </div>

                        {/* Schedule */}
                        <div className="space-y-4 border p-4 rounded-md">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Calendar className="w-4 h-4" />
                                    <h3 className="font-semibold">Schedule</h3>
                                </div>
                                <Switch
                                    checked={formData.scheduleActive}
                                    onCheckedChange={c => setFormData({ ...formData, scheduleActive: c })}
                                />
                            </div>

                            {formData.scheduleActive && (
                                <div className="grid gap-4">
                                    <div className="space-y-2">
                                        <Label>Cron Expression</Label>
                                        <Input
                                            placeholder="0 9 * * *"
                                            value={formData.cronExpression}
                                            onChange={e => setFormData({ ...formData, cronExpression: e.target.value })}
                                        />
                                        <p className="text-xs text-muted-foreground">Format: Minute Hour Day Month DayOfWeek</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Scheduled Task Instructions</Label>
                                        <Input
                                            placeholder="e.g. Generate daily summary"
                                            value={formData.scheduledTask}
                                            onChange={e => setFormData({ ...formData, scheduledTask: e.target.value })}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Test Run Pane - Only available in Edit mode */}
                        {selectedAgent && (
                            <div className="space-y-4 border p-4 rounded-md bg-muted/40">
                                <div className="flex items-center gap-2">
                                    <Terminal className="w-4 h-4" />
                                    <h3 className="font-semibold">Test</h3>
                                </div>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Enter a task to run now..."
                                        value={runInput}
                                        onChange={e => setRunInput(e.target.value)}
                                    />
                                    <Button onClick={() => handleTestRun(selectedAgent.id)} disabled={isRunning}>
                                        <Play className="w-4 h-4" />
                                    </Button>
                                </div>
                                {runTrace.length > 0 ? (
                                    <div className="space-y-4">
                                        {runTrace.map((step, idx) => (
                                            <React.Fragment key={step.step || `hitl-${idx}`}>
                                                {step.type === "hitl_paused" ? (
                                                    <div className="p-3 border-2 border-yellow-200 rounded bg-yellow-50 space-y-3">
                                                        <div className="flex items-center gap-2 text-yellow-800 font-semibold">
                                                            <Settings className="w-4 h-4 animate-spin" />
                                                            Human Approval Required
                                                        </div>
                                                        <p className="text-sm text-yellow-700">
                                                            <strong>Action:</strong> {step.action?.tool}<br />
                                                            <strong>Reason:</strong> {step.reason}
                                                        </p>
                                                        {step.status === "pending" ? (
                                                            <div className="flex gap-2">
                                                                <Button size="sm" onClick={() => handleHITLDecision(step.action_id!, 'approved')}>
                                                                    Approve
                                                                </Button>
                                                                <Button size="sm" variant="destructive" onClick={() => handleHITLDecision(step.action_id!, 'rejected')}>
                                                                    Reject
                                                                </Button>
                                                            </div>
                                                        ) : (
                                                            <Badge variant={step.status === 'approved' ? 'default' : 'destructive'}>
                                                                {step.status?.toUpperCase()}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                ) : (
                                                    <div className="p-3 border rounded bg-white text-sm space-y-2">
                                                        <div className="flex justify-between items-start">
                                                            <span className="font-bold text-xs bg-gray-200 px-2 py-0.5 rounded">Step {step.step}</span>
                                                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleOpenFeedback(step)}>
                                                                <ThumbsDown className="w-3 h-3 text-gray-400 hover:text-red-500" />
                                                            </Button>
                                                        </div>
                                                        <div className="text-gray-700"><strong>Thought:</strong> {step.thought}</div>
                                                        {step.action && (
                                                            <div className="font-mono text-xs bg-gray-50 p-2 rounded">
                                                                <span className="text-blue-600">Action:</span> {JSON.stringify(step.action)}
                                                            </div>
                                                        )}
                                                        {step.output && (
                                                            <div className="font-mono text-xs text-gray-500">
                                                                <span className="text-green-600">Observation:</span> {step.output}
                                                            </div>
                                                        )}
                                                        {step.final_answer && (
                                                            <div className="bg-green-50 p-2 rounded border border-green-100 mt-2">
                                                                <strong>Final Answer:</strong> {step.final_answer}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </React.Fragment>
                                        ))}
                                    </div>
                                ) : (
                                    runResult && (
                                        <div className="text-xs font-mono p-2 bg-black text-green-400 rounded whitespace-pre-wrap">
                                            {runResult}
                                        </div>
                                    )
                                )}
                            </div>
                        )}

                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
                        <Button onClick={handleSave}>Save Agent</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Feedback Dialog */}
            <Dialog open={isFeedbackOpen} onOpenChange={setIsFeedbackOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Provide Feedback</DialogTitle>
                        <CardDescription>Critique the agent's reasoning to help it learn.</CardDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        {feedbackStep && (
                            <div className="text-xs text-muted-foreground p-2 bg-muted rounded">
                                <strong>Step {feedbackStep.step}:</strong> {feedbackStep.thought}
                            </div>
                        )}
                        <div className="space-y-2">
                            <Label>Correct Logic / Behavior</Label>
                            <Textarea
                                value={feedbackText}
                                onChange={e => setFeedbackText(e.target.value)}
                                placeholder="Explain what the agent should have done..."
                                className="h-32"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsFeedbackOpen(false)}>Cancel</Button>
                        <Button onClick={handleSubmitFeedback}>Submit Correction</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AgentStudio;
