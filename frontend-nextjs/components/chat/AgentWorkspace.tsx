'use client';

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, ListTodo, Globe, AlertTriangle } from "lucide-react";
import { ArtifactSidebar } from "./ArtifactSidebar";

interface AgentWorkspaceProps {
    sessionId: string | null;
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({ sessionId }) => {
    // In a real implementation, this would fetch data based on sessionId
    const [tasks] = useState([
        { id: 1, text: "Analyze user request", status: "completed" },
        { id: 2, text: "Search documentation for API endpoints", status: "in-progress" },
        { id: 3, text: "Generate authentication code", status: "pending" },
        { id: 4, text: "Verify implementation", status: "pending" },
    ]);

    return (
        <div className="h-full flex flex-col border-l border-slate-800 bg-[#0F172A]">
            <div className="p-4 border-b border-slate-800">
                <h2 className="font-semibold flex items-center gap-2 text-slate-100">
                    <Brain className="h-4 w-4 text-indigo-400" />
                    Agent Workspace
                </h2>
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
                            <CardTitle className="text-[10px] font-bold uppercase flex items-center gap-2 text-indigo-300">
                                <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
                                Agent Strategy
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-slate-400 italic">
                                &quot;{sessionId ? "I am currently processing the conversation history to better assist you." : "I am standing by. Start a chat to see my execution plan."}&quot;
                            </p>
                        </CardContent>
                    </Card>

                    {/* Task List */}
                    <Card className="flex-1 flex flex-col overflow-hidden bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-slate-200">
                                <ListTodo className="h-4 w-4" />
                                Execution Plan
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 overflow-auto">
                            <div className="space-y-3">
                                {tasks.map((task) => (
                                    <div key={task.id} className="flex items-start gap-2 group">
                                        <Checkbox
                                            checked={task.status === "completed"}
                                            className="mt-1 border-slate-600 data-[state=checked]:bg-indigo-600"
                                            disabled
                                        />
                                        <div className="flex-1">
                                            <p className={`text-sm ${task.status === "completed" ? "text-slate-500 line-through" : "text-slate-300"}`}>
                                                {task.text}
                                            </p>
                                            <div className="flex gap-2 mt-1">
                                                <Badge variant={
                                                    task.status === "completed" ? "secondary" :
                                                        task.status === "in-progress" ? "default" : "outline"
                                                } className={`text-[10px] h-5 ${task.status === 'in-progress' ? 'bg-indigo-600' : ''}`}>
                                                    {task.status}
                                                </Badge>
                                            </div>
                                        </div>
                                    </div>
                                ))}
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
