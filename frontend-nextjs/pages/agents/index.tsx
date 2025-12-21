```javascript
import React, { useEffect, useState } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { AgentCard } from '@/components/agents/AgentCard';
import { AgentTerminal } from '@/components/agents/AgentTerminal';
import { AgentHistoryTable } from '@/components/agents/AgentHistoryTable';
import { useToast } from '@/components/ui/use-toast';

interface Agent {
    id: string;
    name: string;
    description: string;
    category: string;
    status: 'idle' | 'running' | 'error';
}

export default function AgentsDashboard() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
    const [runningAgentIds, setRunningAgentIds] = useState<Set<string>>(new Set());
    const { toast } = useToast();

    useEffect(() => {
        fetchAgents();
    }, []);

    const fetchAgents = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/agents/');
            if (res.ok) {
                const data = await res.json();
                setAgents(data);
            }
        } catch (error) {
            console.error("Failed to fetch agents", error);
        }
    };

    const handleRunAgent = async (id: string) => {
        try {
            setRunningAgentIds(prev => new Set(prev).add(id));
            setSelectedAgentId(id); // Auto-focus terminal

            const res = await fetch(`http://localhost:8000/api/agents/${id}/run`, {
method: 'POST',
    headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({ parameters: {} })
            });

if (res.ok) {
    toast({
        title: "Agent Started",
        description: `Agent ${id} is executing in the background.`,
    });

    // Revert running state after standard timeout (mock)
    setTimeout(() => {
        setRunningAgentIds(prev => {
            const next = new Set(prev);
            next.delete(id);
            return next;
        });
        toast({ title: "Agent Completed", description: `Agent ${id} finished successfully.` });
    }, 10000);

} else {
    throw new Error("API Failed");
}
        } catch (error) {
    toast({
        title: "Execution Failed",
        description: "Could not start agent.",
        variant: "destructive"
    });
    setRunningAgentIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
    });
}
    };

const handleScheduleAgent = async (id: string) => {
    const cron = prompt("Enter Cron Expression (e.g. '*/5 * * * *' for every 5 mins):", "*/30 * * * *");
    if (!cron) return;

    try {
        const res = await fetch(`http://localhost:8000/api/agents/${id}/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cron_expression: cron })
        });

        if (res.ok) {
            toast({ title: "Scheduled", description: `Agent ${id} scheduled: ${cron}` });
        } else {
            throw new Error("Schedule API Failed");
        }
    } catch (error) {
        toast({ title: "Scheduling Failed", description: String(error), variant: "destructive" });
    }
};

return (
    <MainLayout>
        <div className="flex h-[calc(100vh-100px)] gap-6 p-6">

            {/* Left Side: Agent Grid & History */}
            <div className="w-2/3 space-y-6 overflow-y-auto pr-2">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Agent Control Center</h1>
                    <p className="text-muted-foreground">Manage and trigger your specialized Computer Use agents.</p>
                </div>

                {/* Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {agents.map(agent => (
                        <AgentCard
                            key={agent.id}
                            agent={{
                                ...agent,
                                status: runningAgentIds.has(agent.id) ? 'running' : 'idle'
                            }}
                            onRun={handleRunAgent}
                            onSchedule={handleScheduleAgent}
                        />
                    ))}
                </div>

                {/* History Table */}
                <div className="pt-4">
                    <AgentHistoryTable />
                </div>
            </div>

            {/* Right Side: Terminal */}
            <div className="w-1/3">
                <AgentTerminal
                    agentId={selectedAgentId}
                    isRunning={selectedAgentId ? runningAgentIds.has(selectedAgentId) : false}
                />
            </div>

        </div>
    </MainLayout>
);
}
```
