'use client';

import React, { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, ListTodo, Globe, AlertTriangle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ArtifactSidebar } from "./ArtifactSidebar";

interface AgentStep {
    step: number;
    thought?: string;
    action?: string;
    action_input?: string;
    observation?: string;
    timestamp?: string;
}

interface AgentWorkspaceProps {
    sessionId: string | null;
    initialAgentId?: string | null;
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({ sessionId, initialAgentId }) => {
    const [steps, setSteps] = useState<AgentStep[]>([]);
    const [agentStatus, setAgentStatus] = useState<string>("idle");
    const [activeAgentId, setActiveAgentId] = useState<string | null>(initialAgentId || null);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Update active agent if initial changes (e.g. navigation)
    useEffect(() => {
        if (initialAgentId) setActiveAgentId(initialAgentId);
    }, [initialAgentId]);

    // Subscribe to workspace events
    const { lastMessage, isConnected } = useWebSocket({
        initialChannels: ["workspace:default"]
    });

    // Handle incoming events
    useEffect(() => {
        if (!lastMessage) return;

        if (lastMessage.type === "agent_step_update") {
            // Handle various payload shapes (flat or nested in data)
            const newStep = lastMessage.step || lastMessage.data?.step || lastMessage.data;
            if (newStep) {
                setSteps(prev => {
                    // If step is 1, this is a NEW agent run - clear previous steps
                    if (newStep.step === 1) {
                        return [newStep];
                    }
                    // Avoid duplicates if step number exists
                    if (prev.some(s => s.step === newStep.step)) return prev;
                    return [...prev, newStep];
                });
                setAgentStatus("running");
                if (lastMessage.data?.agent_id) setActiveAgentId(lastMessage.data.agent_id);
            }
        } else if (lastMessage.type === "agent_status_change") {
            // Handle flat or nested status
            const status = lastMessage.status || lastMessage.data?.status || "unknown";
            setAgentStatus(status);

            const agentId = lastMessage.agent_id || lastMessage.data?.agent_id;
            if (agentId) setActiveAgentId(agentId);
        }

    }, [lastMessage]);

    // Auto-scroll to bottom of steps
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [steps]);

    const handleClear = () => {
        setSteps([]);
        setAgentStatus("idle");
        setActiveAgentId(null);
    };

    return (
        <div className="h-full flex flex-col border-l border-slate-800 bg-[#0F172A]">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h2 className="font-semibold flex items-center gap-2 text-slate-100">
                    <Brain className="h-4 w-4 text-indigo-400" />
                    Agent Workspace
                    {isConnected && <Badge variant="outline" className="text-green-400 border-green-400 text-[10px]">Live</Badge>}
                </h2>
                {steps.length > 0 && (
                    <Button variant="ghost" size="sm" onClick={handleClear} className="text-slate-400 hover:text-slate-200">
                        <Trash2 className="h-4 w-4" />
                    </Button>
                )}
            </div>

            <Tabs defaultValue="tasks" className="flex-1 flex flex-col">
                <div className="px-4 pt-2">
                    <TabsList className="w-full grid grid-cols-3 bg-slate-800">
                        <TabsTrigger value="tasks" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Tasks</TabsTrigger>
                        <TabsTrigger value="artifacts" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Artifacts</TabsTrigger>
                        <TabsTrigger value="browser" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Browser View</TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="tasks" className="flex-1 p-4 overflow-hidden flex flex-col gap-4">
                    {/* Self Reflection / Status */}
                    <Card className="bg-indigo-900/10 border-indigo-500/20">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-indigo-300">
                                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                Agent Status: {agentStatus}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-slate-400 italic">
                                &quot;{steps.length > 0 ? `Processing step ${steps.length}...` : "I am standing by. Start a chat to see my execution plan."}&quot;
                            </p>
                        </CardContent>
                    </Card>

                    {/* Execution Steps */}
                    <Card className="flex-1 flex flex-col overflow-hidden bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-slate-200">
                                <ListTodo className="h-4 w-4" />
                                Execution Steps ({steps.length})
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 overflow-auto" ref={scrollRef}>
                            <div className="space-y-3">
                                {steps.length === 0 ? (
                                    <p className="text-sm text-slate-500 italic">No execution steps yet. Send a message to see the agent's reasoning.</p>
                                ) : (
                                    steps.map((step, idx) => (
                                        <div key={idx} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Badge variant="outline" className="text-indigo-400 border-indigo-400">Step {step.step}</Badge>
                                                {step.action && <Badge variant="secondary" className="bg-indigo-600 text-white">{step.action}</Badge>}
                                            </div>
                                            {step.thought && (
                                                <p className="text-sm text-slate-300 mb-1"><strong>Thinking:</strong> {step.thought}</p>
                                            )}
                                            {step.observation && (
                                                <p className="text-sm text-slate-400"><strong>Result:</strong> {step.observation}</p>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="artifacts" className="flex-1 p-0 overflow-hidden">
                    <ArtifactSidebar
                        sessionId={sessionId}
                        onSelectArtifact={(id: string) => {
                            console.log("Selected artifact:", id);
                        }}
                    />
                </TabsContent>

                <TabsContent value="browser" className="flex-1 p-4 h-full">
                    <Card className="h-full flex flex-col bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2 border-b border-slate-800">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-slate-200">
                                <Globe className="h-4 w-4" />
                                Headless Browser Preview
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 bg-slate-950 flex items-center justify-center p-0">
                            <div className="text-center p-4">
                                <Globe className="h-12 w-12 text-slate-700 mx-auto mb-2 opacity-20" />
                                <p className="text-sm text-slate-500">
                                    Browser view will appear here when the agent is interacting with web pages.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default AgentWorkspace;
