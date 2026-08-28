import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useToast } from "@/components/ui/use-toast";
import AgentCard, { AgentInfo, GraduationProgress } from "@/components/Agents/AgentCard";
import AgentTerminal, { LogEntry } from "@/components/Agents/AgentTerminal";
import { MaturityProgression } from "@/components/Agents/MaturityProgression";
import MaturityApprovalPanel from "@/components/Agents/MaturityApprovalPanel";
import { EmployeeOnboardingGuide } from "@/components/Agents/EmployeeOnboardingGuide";
import AgentLaunchGuide from "@/components/Agents/AgentLaunchGuide";
import { GuidedAgentCreator } from "@/components/Agents/GuidedAgentCreator";
import { AutomationSuggestionsPanel } from "@/components/Agents/AutomationSuggestionsPanel";
import { AgentMaturityGuideDialog } from "@/components/Agents/AgentMaturityGuide";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LayoutDashboard, Sparkles, GraduationCap } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
    DialogDescription,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Brain } from "lucide-react";
import ReasoningChainViewer from "@/components/ReasoningChainViewer";
import { useProviderStatus } from "@/hooks/useProviderStatus";
import { ProviderRequiredBanner } from "@/components/shared/ProviderRequiredBanner";
import { handleSessionExpired } from "@/lib/auth-headers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// The backend list payload carries the maturity TIER in `status`
// (student/intern/supervised/autonomous/paused/...). The card expects
// `maturity_level` for the tier badge and an execution status for the
// status badge — derive both here so both render correctly.
const TIER_STATUSES = ['student', 'intern', 'supervised', 'autonomous'];

const normalizeAgent = (a: any) => {
    const tier = TIER_STATUSES.includes(a.status) ? a.status : undefined;
    const executionStatus = TIER_STATUSES.includes(a.status) ? 'idle' : (a.status || 'idle');
    return { ...a, maturity_level: a.maturity_level ?? tier, status: executionStatus };
};

// Backend error bodies arrive in two shapes: BaseAPIRouter wraps as
// { success: false, error: { code, message } } and FastAPI validation
// failures as { detail }. Surface whichever is present instead of
// showing the raw "undefined".
const extractErrorMessage = (json: any, fallback: string): string => {
    if (!json) return fallback;
    return json?.error?.message || json?.detail || json?.message || fallback;
};

// Cap the live-log buffer so a chatty agent can't grow page state unbounded.
const MAX_LOG_LINES = 200;

const AgentsDashboard = () => {
    const router = useRouter();
    const providerStatus = useProviderStatus();
    const [agents, setAgents] = useState<AgentInfo[]>([]);
    const [progressByAgent, setProgressByAgent] = useState<Record<string, GraduationProgress | null>>({});
    const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const { toast } = useToast();

    // The timestamp is fixed at append time so re-renders never rewrite the
    // history of older lines.
    const appendLog = useCallback((text: string) => {
        if (!text) return;
        setLogs(prev => [...prev, { text, ts: Date.now() }].slice(-MAX_LOG_LINES));
    }, []);

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");

    // Run Dialog State
    const [isRunDialogOpen, setIsRunDialogOpen] = useState(false);
    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
    const [runInstructions, setRunInstructions] = useState("");
    const [isRunning, setIsRunning] = useState(false);
    
    // Reasoning Modal State
    const [isReasoningModalOpen, setIsReasoningModalOpen] = useState(false);
    const [selectedReasoningId, setSelectedReasoningId] = useState<string | null>(null);

    // Guided agent creation (employee self-serve) + maturity guide state
    const [isGuidedCreatorOpen, setIsGuidedCreatorOpen] = useState(false);
    const [guidedPresetGoal, setGuidedPresetGoal] = useState<string | null>(null);
    const [isMaturityGuideOpen, setIsMaturityGuideOpen] = useState(false);

    // WebSocket Integration
    const { isConnected, lastMessage, subscribe } = useWebSocket();

    useEffect(() => {
        if (isConnected) {
            subscribe("workspace:default");
        }
    }, [isConnected, subscribe]);

    useEffect(() => {
        if (lastMessage) {
            if (lastMessage.type === "agent_step_update") {
                const { agent_id, step } = lastMessage.data || (lastMessage as any).step || lastMessage;
                if (agent_id === activeAgentId) {
                    const stepText = step.thought || step.output || JSON.stringify(step.action);
                    if (stepText) {
                        let prefix = "";
                        if (step.thought) prefix = "Thought: ";
                        else if (step.action) prefix = "Action: ";
                        else if (step.output) prefix = "Observation: ";

                        appendLog(`${prefix}${stepText}`);
                        if (step.final_answer) {
                            appendLog(`Final Answer: ${step.final_answer}`);
                        }
                    }
                }
            } else if (lastMessage.type === "agent_status_change") {
                const { agent_id, status, error } = lastMessage.data || lastMessage as any;
                if (agent_id === activeAgentId) {
                    appendLog(`Status Changed: ${status}${error ? ` - Error: ${error}` : ''}`);
                    if (status === "success" || status === "failed") {
                        // Optionally clear active agent after delay or keep for logs
                    }
                }
                // Refresh list to update badges
                fetchAgents();
            }
        }
    }, [lastMessage, activeAgentId, appendLog]);

    // Fetch Agents
    const fetchAgents = async () => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
            setError("Unauthorized: Redirecting to login...");
            router.push('/login');
            return;
        }

        try {
            setError(null);
            // Direct backend connection to bypass proxy issues
            const res = await fetch(`${API_BASE}/api/agents/`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (res.ok) {
                const json = await res.json();
                // The backend wraps responses as { success, data, ... }.
                // Accept either the wrapped shape or a bare array for safety.
                const data = Array.isArray(json) ? json : (json.data ?? []);
                setAgents(data.map(normalizeAgent));
            } else if (res.status === 401 || res.status === 403) {
                // Token no longer valid (expired/revoked) — clear it and go
                // to login, same behavior as the axios 401 interceptor.
                setError("Session expired. Redirecting to login...");
                handleSessionExpired();
            } else {
                // Surface the backend's structured error (W45): the list
                // endpoint now returns {error: {message}} on failure so the
                // real cause (e.g. DB schema drift) is visible instead of a
                // generic "Internal Server Error".
                let detail = res.statusText || "Unknown error";
                try {
                    const json = await res.json();
                    const payload = json?.detail || json;
                    detail = payload?.error?.message || payload?.message || detail;
                } catch {
                    // non-JSON error body — keep statusText
                }
                setError(`Failed to load agents: ${detail}`);
            }
        } catch (err: any) {
            console.error("Agents fetch error:", err);
            setError(`Failed to load agents: ${err.message || String(err)}. Check console for details.`);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchAgents();
        const interval = setInterval(fetchAgents, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, []);

    // R82: fetch real graduation progress (episode counts) per agent so the
    // card renders live progress instead of the static threshold text. Best
    // effort — failures keep the card's static fallback.
    const fetchGraduationProgress = useCallback(async () => {
        const token = localStorage.getItem('auth_token');
        if (!token) return;
        const map: Record<string, GraduationProgress | null> = {};
        await Promise.allSettled(
            agents.map(async (a) => {
                try {
                    const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(a.id)}/graduation-progress`, {
                        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    });
                    if (res.status === 401 || res.status === 403) {
                        handleSessionExpired();
                        return;
                    }
                    if (res.ok) {
                        const json = await res.json();
                        map[a.id] = (json?.data ?? json) as GraduationProgress;
                    }
                } catch {
                    map[a.id] = null;
                }
            })
        );
        setProgressByAgent(map);
    }, [agents]);

    useEffect(() => {
        if (agents.length > 0) {
            fetchGraduationProgress();
        }
    }, [agents, fetchGraduationProgress]);

    const handleRunAgent = (id: string) => {
        setSelectedAgentId(id);
        setRunInstructions("");
        setIsRunDialogOpen(true);
    };

    const executeAgentRun = async () => {
        if (!selectedAgentId) return;

        setIsRunning(true);
        setActiveAgentId(selectedAgentId);
        setLogs([]);
        appendLog(`Initializing agent: ${selectedAgentId}...`);
        appendLog("Connecting to real-time stream...");
        appendLog(`Instructions: ${runInstructions || "Default behavior"}`);

        try {
            const res = await fetch(`${API_BASE}/api/agents/${selectedAgentId}/run/`, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                method: 'POST',
                body: JSON.stringify({
                    parameters: {
                        task_input: runInstructions // Pass user instructions to backend
                    }
                })
            });

            if (res.ok) {
                toast({
                    title: "Agent Started Successfully",
                    description: `Agent ${selectedAgentId} is now running with your instructions.`,
                    duration: 5000
                });
                setIsRunDialogOpen(false); // Close dialog on success
            } else {
                if (res.status === 401 || res.status === 403) {
                    handleSessionExpired();
                    return;
                }
                const err = await res.json();
                const message = extractErrorMessage(err, 'Unknown error');
                toast({ title: "Failed to start", description: message, variant: "error" });
                appendLog(`Error: ${message}`);
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        } finally {
            setIsRunning(false);
        }
    };

    // Guard against double-click on stop (BUG-065).
    const [stoppingId, setStoppingId] = useState<string | null>(null);

    const handleStopAgent = async (id: string) => {
        if (stoppingId) return; // prevent double-fire while in-flight
        setStoppingId(id);
        try {
            const res = await fetch(`${API_BASE}/api/agents/${id}/stop`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                method: 'POST'
            });

            if (res.ok) {
                toast({ title: "Agent Stopped", description: `Agent ${id} termination requested.` });
                appendLog("Termination requested by user...");
                fetchAgents();
            } else {
                if (res.status === 401 || res.status === 403) {
                    handleSessionExpired();
                    return;
                }
                const err = await res.json();
                toast({ title: "Failed to stop", description: extractErrorMessage(err, 'Unknown error'), variant: "error" });
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        } finally {
            setStoppingId(null);
        }
    };

    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [editAgentName, setEditAgentName] = useState("");
    const [editAgentDescription, setEditAgentDescription] = useState("");

    const handleChat = (id: string) => {
        router.push(`/chat?agent_id=${id}`);
    };

    const handleEdit = (id: string) => {
        const agent = agents.find(a => a.id === id);
        if (agent) {
            setSelectedAgentId(id);
            setEditAgentName(agent.name);
            setEditAgentDescription(agent.description);
            setIsEditDialogOpen(true);
        }
    };

    const handleViewReasoning = (id: string) => {
        setSelectedReasoningId(id);
        setIsReasoningModalOpen(true);
    };

    const handleStepFeedback = async (stepId: string, score: number, comment?: string) => {
        try {
            // POST to the correct reasoning-step feedback endpoint
            // (was /api/v1/agents/steps/feedback — 404; correct is /api/reasoning/feedback).
            // Map the frontend's (stepId, score, comment) to the backend's
            // ReasoningStepFeedback schema (agent_id, run_id, step_index,
            // step_content, feedback_type, comment).
            const feedbackType = score >= 0.5 ? "thumbs_up" : "thumbs_down";
            const parts = stepId.split(":");
            const agentId = parts[0] || "atom_main";
            const runId = parts[1] || stepId;
            const stepIndex = parseInt(parts[2] || "0", 10);
            const res = await fetch(`${API_BASE}/api/reasoning/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                body: JSON.stringify({
                    agent_id: agentId,
                    run_id: runId,
                    step_index: stepIndex,
                    step_content: { thought: "" },
                    feedback_type: feedbackType,
                    comment: comment
                })
            });

            if (res.status === 401 || res.status === 403) {
                handleSessionExpired();
                return;
            }
            if (res.ok) {
                toast({ title: "Feedback Recorded", description: "The agent will learn from this correction." });
            }
        } catch (e) {
            toast({ title: "Error", description: "Failed to submit feedback", variant: "error" });
        }
    };

    const saveAgentChanges = async () => {
        if (!selectedAgentId) return;

        try {
            const res = await fetch(`${API_BASE}/api/agents/${selectedAgentId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                body: JSON.stringify({
                    name: editAgentName,
                    description: editAgentDescription
                })
            });

            if (res.ok) {
                toast({ title: "Agent Updated", description: "Agent details saved successfully." });
                setIsEditDialogOpen(false);
                fetchAgents();
            } else {
                if (res.status === 401 || res.status === 403) {
                    handleSessionExpired();
                    return;
                }
                const err = await res.json();
                toast({ title: "Failed to update", description: extractErrorMessage(err, 'Unknown error'), variant: "error" });
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        }
    };

    const activeAgentName = agents.find(a => a.id === activeAgentId)?.name || "Terminal";
    const activeAgentStatus = agents.find(a => a.id === activeAgentId)?.status || "idle";
    const activeAgentMaturity = agents.find(a => a.id === activeAgentId)?.maturity_level || "student";

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8 font-sans">
            <Head>
                <title>Atom AI | Agent Control Center</title>
            </Head>

            <div className="max-w-6xl mx-auto space-y-8">

                {/* Header */}
                <div className="flex flex-col space-y-2">
                    <h1 className="text-3xl font-bold flex items-center gap-2 text-gray-900 dark:text-white">
                        <LayoutDashboard className="w-8 h-8 text-blue-600" />
                        Agent Control Center
                    </h1>
                    <p className="text-gray-500 dark:text-gray-400">Monitor and orchestrate your autonomous workforce.</p>
                    <div className="flex flex-wrap items-center gap-3">
                        <Button
                            size="sm"
                            data-testid="describe-job-button"
                            onClick={() => { setGuidedPresetGoal(null); setIsGuidedCreatorOpen(true); }}
                        >
                            <Sparkles className="mr-1.5 h-4 w-4" />
                            Describe a job — we&apos;ll build the agent
                        </Button>
                        <span className="text-xs text-gray-400">
                            No setup forms. The agent starts as a Student and learns on the job.
                        </span>
                    </div>
                </div>

                <EmployeeOnboardingGuide />

                {/* Guided journey: connect Zoho/Outlook -> create sales agent ->
                    ingest scoped data -> training. Hides itself once the core
                    setup (both connections + a Sales-category agent) is done. */}
                <AgentLaunchGuide agents={agents} onAgentsChanged={fetchAgents} />

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Agent Grid */}
                    <div className="lg:col-span-2 space-y-6">
                        <div className="flex items-center justify-between gap-4">
                            <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Available Agents</h2>
                            <Input
                                type="text"
                                placeholder="Search agents..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                data-testid="agent-search-input"
                                className="max-w-xs"
                            />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="agents-grid">
                            {isLoading && agents.length === 0 && (
                                <div className="col-span-1 md:col-span-2 py-12 text-center text-gray-500 dark:text-gray-400">
                                    <p>Loading agents...</p>
                                </div>
                            )}

                            {error && (
                                <div className="col-span-1 md:col-span-2 p-4 bg-red-50 text-red-600 rounded border border-red-200">
                                    {error}
                                </div>
                            )}

                            {!isLoading && !error && agents.length === 0 && (
                                <div className="col-span-1 md:col-span-2 py-12 text-center text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 rounded border border-dashed border-gray-300 dark:border-gray-600">
                                    <p>No agents found. Create your first agent or spawn from a template.</p>
                                    {/* P1.5: actionable CTA so the empty state is not a dead end. */}
                                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                                        <Link href="/marketplace">
                                            <Button size="sm">Browse templates</Button>
                                        </Link>
                                        <Link href="/automations">
                                            <Button size="sm" variant="outline">Describe a workflow</Button>
                                        </Link>
                                        <Link href="/chat">
                                            <Button size="sm" variant="outline">Chat with an agent</Button>
                                        </Link>
                                    </div>
                                </div>
                            )}

                            {Array.isArray(agents) && agents
                                .filter(a => {
                                    const q = searchQuery.trim().toLowerCase();
                                    if (!q) return true;
                                    return (a.name || '').toLowerCase().includes(q)
                                        || (a.category || '').toLowerCase().includes(q);
                                })
                                .map(agent => (
                                <AgentCard
                                    key={agent.id}
                                    agent={agent}
                                    progress={progressByAgent[agent.id]}
                                    onRun={handleRunAgent}
                                    onStop={handleStopAgent}
                                    onChat={handleChat}
                                    onEdit={handleEdit}
                                    onViewReasoning={handleViewReasoning}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Live activity column: the terminal is the point of this
                        column, so it goes first. Maturity, approvals, and
                        automation suggestions are supporting panels — tabs
                        keep them reachable without pushing the logs below
                        the fold. */}
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Live Logs</h2>
                            <Badge variant={isConnected ? "default" : "outline"} className={isConnected ? "bg-green-500" : ""}>
                                {isConnected ? "Live Connection" : "Offline"}
                            </Badge>
                        </div>
                        <AgentTerminal
                            agentName={activeAgentName}
                            logs={logs}
                            status={activeAgentStatus}
                        />
                        <Tabs defaultValue="career">
                            <TabsList className="w-full grid grid-cols-3">
                                <TabsTrigger value="career">Career path</TabsTrigger>
                                <TabsTrigger value="approvals">Approvals</TabsTrigger>
                                <TabsTrigger value="automate">Automate</TabsTrigger>
                            </TabsList>
                            <TabsContent value="career" className="mt-3 space-y-3">
                                <MaturityProgression
                                    currentLevel={activeAgentMaturity}
                                />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="w-full"
                                    data-testid="active-agent-maturity-guide-button"
                                    disabled={!activeAgentId}
                                    onClick={() => setIsMaturityGuideOpen(true)}
                                >
                                    <GraduationCap className="mr-1.5 h-4 w-4" />
                                    When will {activeAgentName === "Terminal" ? "this agent" : activeAgentName} be useful?
                                </Button>
                            </TabsContent>
                            <TabsContent value="approvals" className="mt-3 bg-white dark:bg-gray-800 p-4 rounded-lg border shadow-sm">
                                <MaturityApprovalPanel onChanged={fetchAgents} />
                            </TabsContent>
                            <TabsContent value="automate" className="mt-3 bg-white dark:bg-gray-800 p-4 rounded-lg border shadow-sm">
                                <AutomationSuggestionsPanel
                                    onCreateAgent={(goal) => {
                                        setGuidedPresetGoal(goal);
                                        setIsGuidedCreatorOpen(true);
                                    }}
                                />
                            </TabsContent>
                        </Tabs>
                    </div>
                </div>
            </div>


            {/* Employee self-serve guided agent creation */}
            <GuidedAgentCreator
                open={isGuidedCreatorOpen}
                onOpenChange={setIsGuidedCreatorOpen}
                onAgentCreated={fetchAgents}
                initialGoal={guidedPresetGoal}
            />

            {/* Per-agent readiness report */}
            <AgentMaturityGuideDialog
                agentId={activeAgentId}
                open={isMaturityGuideOpen}
                onOpenChange={setIsMaturityGuideOpen}
            />

            {/* Run Agent Dialog */}
            <Dialog open={isRunDialogOpen} onOpenChange={setIsRunDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Run Agent</DialogTitle>
                        <DialogDescription>
                            Provide specific instructions for this agent execution. Leave empty for default behavior.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        {/* Pre-flight: the run needs an LLM provider — say so
                            before the user starts a doomed execution. */}
                        {providerStatus.configured === false && <ProviderRequiredBanner />}
                        <Textarea
                            placeholder="e.g. Reconcile inventory for SKU-123 and SKU-999..."
                            value={runInstructions}
                            onChange={(e) => setRunInstructions(e.target.value)}
                            className="min-h-[100px]"
                        />
                        {/* data-testid="run-dialog-guidance" */}
                        <div data-testid="run-dialog-guidance" className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700 rounded p-3 space-y-1">
                            <p><strong>Tips for good instructions:</strong></p>
                            <ul className="list-disc pl-4 space-y-0.5">
                                <li>Name the systems and records to act on (&ldquo;Zoho invoice INV-1001&rdquo;, not &ldquo;the invoice&rdquo;).</li>
                                <li>State the goal and any limits (&ldquo;draft, don&rsquo;t send&rdquo;).</li>
                                <li>Include a success check (&ldquo;confirm stock levels match the sales order&rdquo;).</li>
                            </ul>
                            <p className="pt-1">
                                Student/Intern employees will ask for approval before acting —
                                watch <Link href="/approvals" className="text-blue-600 underline">Approvals</Link>.
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsRunDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={executeAgentRun} disabled={isRunning}>
                            {isRunning ? "Starting..." : "Run Agent"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Edit Agent Dialog */}
            <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Agent</DialogTitle>
                        <DialogDescription>
                            Update agent details.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="name">Name</Label>
                            <Input
                                id="name"
                                value={editAgentName}
                                onChange={(e) => setEditAgentName(e.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="description">Job description</Label>
                            <Textarea
                                id="description"
                                value={editAgentDescription}
                                onChange={(e) => setEditAgentDescription(e.target.value)}
                                className="min-h-[100px]"
                            />
                            {/* data-testid="edit-dialog-guidance" */}
                            <p data-testid="edit-dialog-guidance" className="text-xs text-gray-500 dark:text-gray-400">
                                This is the employee&rsquo;s job description: it steers behavior
                                <em> and</em> which synced integration data (invoices, leads, tickets)
                                the employee recalls. Write it like a role spec — responsibilities,
                                systems it owns, boundaries.
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={saveAgentChanges}>
                            Save Changes
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
            {/* Reasoning Viewer Dialog */}
            <Dialog open={isReasoningModalOpen} onOpenChange={setIsReasoningModalOpen}>
                <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Brain className="w-5 h-5 text-purple-600" />
                            Agent Reasoning Audit: {agents.find(a => a.id === selectedReasoningId)?.name}
                        </DialogTitle>
                        <DialogDescription>
                            Review the agent's internal thought process and provide corrections to improve its accuracy.
                        </DialogDescription>
                    </DialogHeader>
                    {selectedReasoningId && (
                        <div className="py-2">
                            <ReasoningChainViewer 
                                chainId={selectedReasoningId} 
                                onStepFeedback={handleStepFeedback}
                            />
                        </div>
                    )}
                    <DialogFooter>
                        <Button onClick={() => setIsReasoningModalOpen(false)}>Close</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    );
};

export default AgentsDashboard;
