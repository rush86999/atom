'use client';

import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, ListTodo, Globe, AlertTriangle, Terminal, Play, RotateCcw } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import { Button } from "@/components/ui/button";

interface AgentWorkspaceProps {
    sessionId: string | null;
}

interface AgentStep {
    step: number;
    thought: string;
    action: string;
    action_input: string;
    observation: string;
    timestamp: string;
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({ sessionId }) => {
    const [steps, setSteps] = useState<AgentStep[]>([]);
    const [agentStatus, setAgentStatus] = useState<string>("idle");
    const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

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
        <div className="h-full flex flex-col border-l border-border bg-background">
            <div className="p-4 border-b border-border flex justify-between items-center">
                <h2 className="font-semibold flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    Agent Workspace
                </h2>
                <div className="flex items-center gap-2">
                    {!isConnected && (
                        <Badge variant="destructive" className="text-[10px] h-5 animate-pulse">
                            DISCONNECTED
                        </Badge>
                    )}
                    <Badge variant={agentStatus === "running" ? "default" : "outline"} className="text-xs">
                        {agentStatus.toUpperCase()}
                    </Badge>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleClear} title="Clear Workspace">
                        <RotateCcw className="h-3 w-3" />
                    </Button>
                </div>
            </div>

            <Tabs defaultValue="tasks" className="flex-1 flex flex-col">
                <div className="px-4 pt-2">
                    <TabsList className="w-full grid grid-cols-2">
                        <TabsTrigger value="tasks">Live Execution</TabsTrigger>
                        <TabsTrigger value="browser">Browser View</TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="tasks" className="flex-1 p-4 overflow-hidden flex flex-col gap-4">
                    {/* Status / Active Agent */}
                    {activeAgentId && (
                        <Card className="bg-muted/30 border-muted">
                            <CardContent className="p-3 flex items-center gap-2 text-xs font-mono">
                                <Terminal className="h-3 w-3" />
                                <span>Agent ID: {activeAgentId}</span>
                            </CardContent>
                        </Card>
                    )}

                    {/* Empty State */}
                    {steps.length === 0 && (
                        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8 text-center opacity-50">
                            <Brain className="h-12 w-12 mb-4" />
                            <p className="text-sm">Ready to execute agents.</p>
                            <p className="text-xs">Try asking: "Run inventory check"</p>
                        </div>
                    )}

                    {/* Live Steps List */}
                    {steps.length > 0 && (
                        <Card className="flex-1 flex flex-col overflow-hidden border-none shadow-none bg-transparent">
                            <div className="overflow-auto pr-2" ref={scrollRef}>
                                <div className="space-y-4">
                                    {steps.map((step, idx) => (
                                        <div key={idx} className="flex flex-col gap-2 p-3 rounded-lg border bg-card text-card-foreground shadow-sm animate-in fade-in slide-in-from-bottom-2">
                                            <div className="flex items-center justify-between">
                                                <Badge variant="outline" className="text-[10px]">Step {step.step}</Badge>
                                                <span className="text-[10px] text-muted-foreground">{new Date().toLocaleTimeString()}</span>
                                            </div>

                                            {step.thought && (
                                                <div className="text-sm italic text-muted-foreground border-l-2 pl-2 border-primary/20">
                                                    "{step.thought}"
                                                </div>
                                            )}

                                            {step.action && (
                                                <div className="bg-muted/50 rounded p-2 text-xs font-mono mt-1">
                                                    <div className="text-blue-600 font-bold flex items-center gap-1">
                                                        <Play className="h-3 w-3" />
                                                        {step.action}
                                                    </div>
                                                    <div className="truncate mt-1 opacity-80">
                                                        {step.action_input}
                                                    </div>
                                                </div>
                                            )}

                                            {step.observation && (
                                                <div className="text-xs text-green-700 bg-green-50/50 p-2 rounded mt-1">
                                                    → {step.observation.substring(0, 150)}{step.observation.length > 150 ? "..." : ""}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="browser" className="flex-1 p-4 h-full">
                    <Card className="h-full flex flex-col">
                        <CardHeader className="pb-2 border-b">
                            <CardTitle className="text-sm font-medium flex items-center gap-2">
                                <Globe className="h-4 w-4" />
                                Headless Browser Preview
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 bg-muted/50 flex items-center justify-center p-0">
                            <div className="text-center p-4">
                                <Globe className="h-12 w-12 text-muted-foreground mx-auto mb-2 opacity-20" />
                                <p className="text-sm text-muted-foreground">
                                    No active browser session.
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
