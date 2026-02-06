
import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useToast } from "@/components/ui/use-toast";
import AgentCard, { AgentInfo } from "@/components/Agents/AgentCard";
import AgentTerminal from "@/components/Agents/AgentTerminal";
import { Badge } from "@/components/ui/badge";
import { LayoutDashboard } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";

const AgentsDashboard = () => {
    const [agents, setAgents] = useState<AgentInfo[]>([]);
    const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const { toast } = useToast();

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

                        setLogs(prev => [...prev, `${prefix}${stepText}`]);
                        if (step.final_answer) {
                            setLogs(prev => [...prev, `Final Answer: ${step.final_answer}`]);
                        }
                    }
                }
            } else if (lastMessage.type === "agent_status_change") {
                const { agent_id, status, error } = lastMessage.data || lastMessage as any;
                if (agent_id === activeAgentId) {
                    setLogs(prev => [...prev, `Status Changed: ${status}${error ? ` - Error: ${error}` : ''}`]);
                    if (status === "success" || status === "failed") {
                        // Optionally clear active agent after delay or keep for logs
                    }
                }
                // Refresh list to update badges
                fetchAgents();
            }
        }
    }, [lastMessage, activeAgentId]);

    // Fetch Agents
    const fetchAgents = async () => {
        try {
            const res = await fetch('/api/agents', { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                setAgents(data);
            }
        } catch (e) {
            console.error("Failed to fetch agents", e);
        }
    };

    useEffect(() => {
        fetchAgents();
        const interval = setInterval(fetchAgents, 5000); // Poll status less frequently now with WS
        return () => clearInterval(interval);
    }, []);

    const handleRunAgent = async (id: string) => {
        setActiveAgentId(id);
        setLogs([`Initializing agent: ${id}...`, "Connecting to real-time stream..."]);

        try {
            const res = await fetch(`/api/agents/${id}/run`, {
                credentials: 'include',
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: {} })
            });

            if (res.ok) {
                toast({ title: "Agent Started", description: `Agent ${id} is now running.` });
            } else {
                const err = await res.json();
                toast({ title: "Failed to start", description: err.detail, variant: "error" });
                setLogs(prev => [...prev, `Error: ${err.detail || 'Unknown error'}`]);
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        }
    };

    const handleStopAgent = async (id: string) => {
        try {
            const res = await fetch(`/api/agents/${id}/stop`, {
                credentials: 'include',
                method: 'POST'
            });

            if (res.ok) {
                toast({ title: "Agent Stopped", description: `Agent ${id} termination requested.` });
                setLogs(prev => [...prev, "Termination requested by user..."]);
                fetchAgents();
            } else {
                const err = await res.json();
                toast({ title: "Failed to stop", description: err.detail, variant: "error" });
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        }
    };

    const activeAgentName = agents.find(a => a.id === activeAgentId)?.name || "Terminal";
    const activeAgentStatus = agents.find(a => a.id === activeAgentId)?.status || "idle";

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
                    <p className="text-gray-500">Monitor and orchestrate your autonomous workforce.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Agent Grid */}
                    <div className="lg:col-span-2 space-y-6">
                        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Available Agents</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {agents.map(agent => (
                                <AgentCard
                                    key={agent.id}
                                    agent={agent}
                                    onRun={handleRunAgent}
                                    onStop={handleStopAgent}
                                />
                            ))}
                            {agents.length === 0 && <p className="text-gray-500">Loading agents...</p>}
                        </div>
                    </div>

                    {/* Terminal Panel */}
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

                        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border shadow-sm mt-4">
                            <h3 className="font-semibold mb-2 text-sm text-gray-700 dark:text-gray-100">System Capability</h3>
                            <div className="text-xs text-blue-600 bg-blue-50 dark:bg-blue-900/20 p-2 rounded border border-blue-100 dark:border-blue-800">
                                WebSocket stream active. Real-time updates from GenericAgent ReAct loop.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentsDashboard;
