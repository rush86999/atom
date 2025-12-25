
import React from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Clock, CheckCircle, XCircle, AlertTriangle } from "lucide-react";

export interface AgentInfo {
    id: string;
    name: string;
    description: string;
    status: "idle" | "running" | "success" | "failed";
    last_run?: string;
    category: string;
}

interface AgentCardProps {
    agent: AgentInfo;
    onRun: (id: string) => void;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onRun }) => {

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "running":
                return <Badge variant="default" className="bg-blue-500 animate-pulse">Running</Badge>;
            case "success":
                return <Badge variant="secondary" className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Success</Badge>;
            case "failed":
                return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Failed</Badge>;
            default:
                return <Badge variant="outline">Idle</Badge>;
        }
    };

    return (
        <Card className="w-full hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                    <Badge variant="outline" className="mb-2 text-xs">{agent.category}</Badge>
                    {getStatusBadge(agent.status)}
                </div>
                <CardTitle className="text-lg">{agent.name}</CardTitle>
                <CardDescription className="line-clamp-2 h-10">{agent.description}</CardDescription>
            </CardHeader>
            <CardContent className="pb-2">
                <div className="flex items-center text-xs text-gray-500 mt-2">
                    <Clock className="w-3 h-3 mr-1" />
                    {agent.last_run ? `Last run: ${new Date(agent.last_run).toLocaleString()}` : 'Never run'}
                </div>
            </CardContent>
            <CardFooter>
                <Button
                    className="w-full"
                    variant={agent.status === "running" ? "secondary" : "default"}
                    disabled={agent.status === "running"}
                    onClick={() => onRun(agent.id)}
                >
                    <Play className="w-4 h-4 mr-2" />
                    {agent.status === "running" ? "Running..." : "Run Agent"}
                </Button>
            </CardFooter>
        </Card>
    );
};

export default AgentCard;
