
import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useToast } from "@/components/ui/use-toast";
import AgentCard, { AgentInfo } from "@/components/Agents/AgentCard";
import AgentTerminal from "@/components/Agents/AgentTerminal";
import { Badge } from "@/components/ui/badge";
import { LayoutDashboard } from "lucide-react";

const AgentsDashboard = () => {
    const [agents, setAgents] = useState<AgentInfo[]>([]);
    const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const { toast } = useToast();

    // Fetch Agents
    const fetchAgents = async () => {
        try {
            const res = await fetch('/api/agents/', { credentials: 'include' });
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
        const interval = setInterval(fetchAgents, 2000); // Poll status
        return () => clearInterval(interval);
    }, []);

    const handleRunAgent = async (id: string) => {
        setActiveAgentId(id);
        setLogs([`Initializing agent: ${id}...`, "Connecting to reliable-messaging-service..."]);

        try {
            const res = await fetch(`/api/agents/${id}/run/`, {
                credentials: 'include',
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: {} })
            });

            if (res.ok) {
                toast({ title: "Agent Started", description: `Agent ${id} is now running.` });

                // Simulate streaming logs for demo
                simulateLogs(id);
            } else {
                const err = await res.json();
                toast({ title: "Failed to start", description: err.detail, variant: "error" });
                setLogs(prev => [...prev, `Error: ${err.detail}`]);
            }
        } catch (e) {
            toast({ title: "Error", description: "Network error", variant: "error" });
        }
    };

    // Simulation for MVP Visuals
    const simulateLogs = (id: string) => {
        let step = 0;
        const mockLogs = [
            "Loading configuration from LanceDB...",
            "Analyzing latest market data...",
            "Found 3 new competitor price references.",
            "Verifying inventory counts for SKU-123...",
            "Diffing wms_count (50) vs shopify_count (50)... MATCH",
            "Diffing wms_count (8) vs shopify_count (10)... VARIANCE DETECTED",
            "Generating alert payload...",
            "Sending urgent notification to #operations...",
            "Updating Business Intelligence Graph...",
            "Task Completed Successfully."
        ];

        const interval = setInterval(() => {
            if (step >= mockLogs.length) {
                clearInterval(interval);
                return;
            }
            setLogs(prev => [...prev, mockLogs[step]]);
            step++;
        }, 800);
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
                    <h1 className="text-3xl font-bold flex items-center gap-2">
                        <LayoutDashboard className="w-8 h-8 text-blue-600" />
                        Agent Control Center
                    </h1>
                    <p className="text-gray-500">Monitor and orchestrate your autonomous workforce.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Agent Grid */}
                    <div className="lg:col-span-2 space-y-6">
                        <h2 className="text-xl font-semibold">Available Agents</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {agents.map(agent => (
                                <AgentCard
                                    key={agent.id}
                                    agent={agent}
                                    onRun={handleRunAgent}
                                />
                            ))}
                            {agents.length === 0 && <p>Loading agents...</p>}
                        </div>
                    </div>

                    {/* Terminal Panel */}
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-semibold">Live Logs</h2>
                            <Badge variant={activeAgentId ? "default" : "outline"}>
                                {activeAgentId ? "Live Connection" : "Offline"}
                            </Badge>
                        </div>
                        <AgentTerminal
                            agentName={activeAgentName}
                            logs={logs}
                            status={activeAgentStatus}
                        />

                        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border shadow-sm mt-4">
                            <h3 className="font-semibold mb-2 text-sm text-gray-700 dark:text-gray-300">Urgent Alerts (Most Recent)</h3>
                            <div className="text-xs text-red-500 bg-red-50 p-2 rounded border border-red-100">
                                [Slack Bot] Inventory variance detected for SKU-999 (-2 units).
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentsDashboard;
