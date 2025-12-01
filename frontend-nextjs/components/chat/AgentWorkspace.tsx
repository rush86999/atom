import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Checkbox } from "../ui/checkbox";
import { ScrollArea } from "../ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Brain, ListTodo, Globe, AlertTriangle } from "lucide-react";

interface AgentWorkspaceProps {
    sessionId: string | null;
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({ sessionId }) => {
    const [tasks, setTasks] = useState([
        { id: 1, text: "Analyze user request", status: "completed" },
        { id: 2, text: "Search documentation for API endpoints", status: "in-progress" },
        { id: 3, text: "Generate authentication code", status: "pending" },
        { id: 4, text: "Verify implementation", status: "pending" },
    ]);

    return (
        <div className="h-full flex flex-col border-l border-border bg-background">
            <div className="p-4 border-b border-border">
                <h2 className="font-semibold flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    Agent Workspace
                </h2>
            </div>

            <Tabs defaultValue="tasks" className="flex-1 flex flex-col">
                <div className="px-4 pt-2">
                    <TabsList className="w-full grid grid-cols-2">
                        <TabsTrigger value="tasks">Tasks & Plan</TabsTrigger>
                        <TabsTrigger value="browser">Browser View</TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="tasks" className="flex-1 p-4 overflow-hidden flex flex-col gap-4">
                    {/* Self Reflection / Status */}
                    <Card className="bg-secondary/20 border-primary/20">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                Agent Reflection
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-muted-foreground">
                                I noticed the documentation for the API is outdated. I will switch to using the browser to find the latest reference docs instead of relying on internal knowledge.
                            </p>
                        </CardContent>
                    </Card>

                    {/* Task List */}
                    <Card className="flex-1 flex flex-col overflow-hidden">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2">
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
                                            className="mt-1"
                                            disabled
                                        />
                                        <div className="flex-1">
                                            <p className={`text-sm ${task.status === "completed" ? "text-muted-foreground line-through" : "text-foreground"}`}>
                                                {task.text}
                                            </p>
                                            <div className="flex gap-2 mt-1">
                                                <Badge variant={
                                                    task.status === "completed" ? "secondary" :
                                                        task.status === "in-progress" ? "default" : "outline"
                                                } className="text-[10px] h-5">
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
