
import React from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Clock, CheckCircle, XCircle, AlertTriangle, MessageSquare, Edit, Brain } from "lucide-react";

export interface AgentInfo {
    id: string;
    name: string;
    description: string;
    status: "idle" | "running" | "success" | "failed";
    last_run?: string;
    category: string;
    maturity_level?: 'student' | 'intern' | 'supervised' | 'autonomous';
}

interface AgentCardProps {
    agent: AgentInfo;
    onRun: (id: string) => void;
    onStop: (id: string) => void;
    onChat: (id: string) => void;
    onEdit: (id: string) => void;
    onViewReasoning: (id: string) => void;
}

// P3.1 — Mirror of AgentGraduationService.CRITERIA min_episodes thresholds.
// Used to render a lightweight progress hint on the card. For real-time
// progress numbers, the dashboard calls GET /api/agents/:id/graduation-progress.
const TIER_THRESHOLDS: Record<NonNullable<AgentInfo["maturity_level"]>, number> = {
    student: 0,    // baseline; needs 10 to reach intern
    intern: 10,
    supervised: 25,
    autonomous: 50,
};

const TIER_COLORS: Record<NonNullable<AgentInfo["maturity_level"]>, string> = {
    student: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    intern: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
    supervised: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
    autonomous: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
};

function getMaturityBadge(level: NonNullable<AgentInfo["maturity_level"]>) {
    return (
        <Badge variant="outline" className={`text-[10px] uppercase tracking-wide ${TIER_COLORS[level]}`} title={`Maturity: ${level}`}>
            {level}
        </Badge>
    );
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onRun, onStop, onChat, onEdit, onViewReasoning }) => {

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
                {/* P3.1: maturity tier badge + graduation progress hint. The
                    agent list payload doesn't carry live episode counts, so we
                    show the tier name + the next threshold as a static target.
                    The dashboard view surfaces real-time progress via the
                    /graduation-progress endpoint. */}
                {agent.maturity_level && (
                    <div className="flex items-center gap-2 mt-2 mb-1">
                        {getMaturityBadge(agent.maturity_level)}
                        <span className="text-[11px] text-muted-foreground">
                            {agent.maturity_level === "autonomous"
                                ? "Max tier reached"
                                : `${TIER_THRESHOLDS[agent.maturity_level]} episodes to next tier`}
                        </span>
                    </div>
                )}
                <div className="flex items-center text-xs text-gray-500 dark:text-gray-400 mt-2">
                    <Clock className="w-3 h-3 mr-1" />
                    {agent.last_run ? `Last run: ${new Date(agent.last_run).toLocaleString()}` : 'Never run'}
                </div>
            </CardContent>
            <CardFooter className="flex gap-2">
                <Button variant="outline" size="icon" onClick={() => onChat(agent.id)} title="Chat with Agent">
                    <MessageSquare className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={() => onEdit(agent.id)} title="Edit Agent">
                    <Edit className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={() => onViewReasoning(agent.id)} title="View Reasoning Trace">
                    <Brain className="w-4 h-4" />
                </Button>
                {agent.status === "running" ? (
                    <Button
                        className="flex-1"
                        variant="destructive"
                        onClick={() => onStop(agent.id)}
                    >
                        <XCircle className="w-4 h-4 mr-2" />
                        Stop
                    </Button>
                ) : (
                    <Button
                        className="flex-1"
                        variant="default"
                        onClick={() => onRun(agent.id)}
                    >
                        <Play className="w-4 h-4 mr-2" />
                        Run
                    </Button>
                )}
            </CardFooter>
        </Card>
    );
};

export default AgentCard;
