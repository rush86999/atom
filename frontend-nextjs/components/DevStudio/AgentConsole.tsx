
import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, Square, RefreshCw, Terminal, Monitor } from 'lucide-react';
import { useToast } from "@/components/ui/use-toast";

const AgentConsole: React.FC = () => {
    const { toast } = useToast();
    const [goal, setGoal] = useState("");
    const [mode, setMode] = useState("thinker");
    const [isRunning, setIsRunning] = useState(false);
    const [taskId, setTaskId] = useState<string | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const [status, setStatus] = useState<string>("idle");
    const logsEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    // Poll for status
    useEffect(() => {
        let interval: NodeJS.Timeout;

        if (isRunning && taskId) {
            interval = setInterval(async () => {
                try {
                    const response = await fetch(`http://localhost:5059/api/agent/status/${taskId}`);
                    if (response.ok) {
                        const data = await response.json();
                        setStatus(data.status);
                        setLogs(data.logs || []);

                        if (["completed", "failed", "stopped"].includes(data.status)) {
                            setIsRunning(false);
                            if (data.status === "completed") {
                                toast({
                                    title: "Task Completed",
                                    description: "Agent finished the task successfully.",
                                    variant: "success",
                                });
                            } else if (data.status === "failed") {
                                toast({
                                    title: "Task Failed",
                                    description: "Agent encountered an error.",
                                    variant: "error",
                                });
                            }
                        }
                    }
                } catch (error) {
                    console.error("Polling error:", error);
                }
            }, 1000);
        }

        return () => clearInterval(interval);
    }, [isRunning, taskId, toast]);

    const handleRun = async () => {
        if (!goal.trim()) {
            toast({
                title: "Goal Required",
                description: "Please enter a goal for the agent.",
                variant: "error",
            });
            return;
        }

        setIsRunning(true);
        setLogs(["Starting agent..."]);
        setStatus("starting");

        try {
            const response = await fetch("http://localhost:5059/api/agent/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ goal, mode }),
            });

            if (response.ok) {
                const data = await response.json();
                setTaskId(data.id);
                toast({
                    title: "Agent Started",
                    description: `Task ID: ${data.id}`,
                });
            } else {
                throw new Error("Failed to start agent");
            }
        } catch (error) {
            console.error("Start error:", error);
            setIsRunning(false);
            setStatus("error");
            toast({
                title: "Error",
                description: "Failed to start the agent service.",
                variant: "error",
            });
        }
    };

    const handleStop = async () => {
        if (!taskId) return;

        try {
            await fetch("http://localhost:5059/api/agent/stop", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: taskId }),
            });
            toast({
                title: "Stop Signal Sent",
                description: "Agent should stop shortly.",
            });
        } catch (error) {
            console.error("Stop error:", error);
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[600px]">
            {/* Control Panel */}
            <Card className="col-span-1">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Monitor className="h-5 w-5" />
                        Control Panel
                    </CardTitle>
                    <CardDescription>Configure and control the Computer Use Agent</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Goal</label>
                        <Input
                            placeholder="e.g., Find the cheapest flight to Tokyo..."
                            value={goal}
                            onChange={(e) => setGoal(e.target.value)}
                            disabled={isRunning}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">Mode</label>
                        <Select value={mode} onValueChange={setMode} disabled={isRunning}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="thinker">Thinker (Deep Planning)</SelectItem>
                                <SelectItem value="actor">Actor (Quick Action)</SelectItem>
                                <SelectItem value="tasker">Tasker (Sequential)</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="pt-4 flex gap-2">
                        {!isRunning ? (
                            <Button className="w-full gap-2" onClick={handleRun}>
                                <Play className="h-4 w-4" /> Run Task
                            </Button>
                        ) : (
                            <Button variant="destructive" className="w-full gap-2" onClick={handleStop}>
                                <Square className="h-4 w-4" /> Stop Task
                            </Button>
                        )}
                    </div>

                    <div className="pt-4 border-t mt-4">
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-muted-foreground">Status:</span>
                            <Badge variant={isRunning ? "default" : "secondary"}>
                                {status.toUpperCase()}
                            </Badge>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Output Console */}
            <Card className="col-span-1 lg:col-span-2 flex flex-col">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Terminal className="h-5 w-5" />
                        Live Execution Logs
                    </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 min-h-0 p-0">
                    <ScrollArea className="h-full max-h-[500px] w-full p-4 font-mono text-sm bg-black text-green-400 rounded-b-lg">
                        {logs.length === 0 ? (
                            <div className="text-gray-500 italic">No logs available. Ready to start.</div>
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className="mb-1 break-words">
                                    <span className="opacity-50 mr-2">[{new Date().toLocaleTimeString()}]</span>
                                    {log}
                                </div>
                            ))
                        )}
                        <div ref={logsEndRef} />
                    </ScrollArea>
                </CardContent>
            </Card>
        </div>
    );
};

export default AgentConsole;
