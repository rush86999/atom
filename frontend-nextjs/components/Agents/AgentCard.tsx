
import React from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Clock, CheckCircle, XCircle, AlertTriangle, MessageSquare, Edit, Brain } from "lucide-react";

export interface AgentInfo {
    id: string;
    name: string;
    description: string;
    status: string; // execution state: idle | running | success | failed | paused
    last_run?: string;
    category: string;
    maturity_level?: 'student' | 'intern' | 'supervised' | 'autonomous';
}

interface AgentCardProps {
    agent: AgentInfo;
    progress?: GraduationProgress | null;
    onRun: (id: string) => void;
    onStop: (id: string) => void;
    onChat: (id: string) => void;
    onEdit: (id: string) => void;
    onViewReasoning: (id: string) => void;
}

// P3.1 — Mirror of AgentGraduationService.CRITERIA min_episodes thresholds.
// Used to render a lightweight progress hint on the card. When the dashboard
// supplies live `progress` (GET /api/agents/:id/graduation-progress) the real
// episode count is rendered instead of the static target.
const TIER_THRESHOLDS: Record<NonNullable<AgentInfo["maturity_level"]>, number> = {
    student: 10,    // episodes needed to reach intern
    intern: 25,     // episodes needed to reach supervised
    supervised: 50, // episodes needed to reach autonomous
    autonomous: 0,  // max tier — the badge renders "Max tier reached" instead
};

export interface GraduationProgress {
    episode_count: number;
    episodes_to_next?: number | null;
    next_threshold_episodes?: number | null;
    next_tier?: string | null;
}

const TIER_COLORS: Record<NonNullable<AgentInfo["maturity_level"]>, string> = {
    student: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    intern: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
    supervised: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
    autonomous: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
};

function getMaturityBadge(level: NonNullable<AgentInfo["maturity_level"]>) {
    return (
        <Badge variant="outline" className={`text-[10px] uppercase tracking-wide ${TIER_COLORS[level]}`} title={`Maturity: ${level}`} data-testid="agent-maturity-badge">
            {level}
        </Badge>
    );
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, progress, onRun, onStop, onChat, onEdit, onViewReasoning }) => {

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "running":
                return <Badge variant="default" className="bg-blue-500 animate-pulse">Running</Badge>;
            case "success":
                return <Badge variant="secondary" className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Success</Badge>;
            case "failed":
                return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Failed</Badge>;
            case "paused":
                return <Badge variant="outline" className="bg-amber-100 text-amber-800"><AlertTriangle className="w-3 h-3 mr-1" /> Paused</Badge>;
            case "stopped":
                return <Badge variant="outline" className="bg-gray-200 text-gray-700"><XCircle className="w-3 h-3 mr-1" /> Stopped</Badge>;
            default:
                return <Badge variant="outline">Idle</Badge>;
        }
    };

    return (
        <Card className="w-full hover:shadow-md transition-shadow" data-testid={`agent-card-${agent.name}`}>
            <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                    <Badge variant="outline" className="mb-2 text-xs">{agent.category}</Badge>
                    <div data-testid="agent-status-badge">{getStatusBadge(agent.status)}</div>
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
                                : (() => {
                                    const threshold = progress?.next_threshold_episodes ?? TIER_THRESHOLDS[agent.maturity_level!];
                                    const count = progress?.episode_count;
                                    if (typeof count === "number" && typeof threshold === "number" && threshold > 0) {
                                        return `✓ ${count}/${threshold} episodes · ${Math.max(0, threshold - count)} to next tier`;
                                    }
                                    return `${threshold} episodes to next tier`;
                                })()}
                        </span>
                    </div>
                )}
                {progress && agent.maturity_level !== "autonomous" && (() => {
                    const threshold = progress.next_threshold_episodes ?? TIER_THRESHOLDS[agent.maturity_level!];
                    const count = progress.episode_count ?? 0;
                    if (!threshold || threshold <= 0) return null;
                    const pct = Math.min(100, Math.round((count / threshold) * 100));
                    return (
                        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden mt-1" aria-label={`${count} of ${threshold} verified episodes`}>
                            <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                    );
                })()}
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
