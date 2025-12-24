import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Play, Activity, Clock } from 'lucide-react';

interface AgentCardProps {
    agent: {
        id: string;
        name: string;
        description: string;
        category: string;
        status: 'idle' | 'running' | 'error';
    };
    onRun: (id: string) => void;
    onSchedule: (id: string) => void;
}

export const AgentCard: React.FC<AgentCardProps> = ({ agent, onRun, onSchedule }) => {
    return (
        <Card className="hover:border-primary/50 transition-colors">
            <CardHeader>
                <div className="flex justify-between items-start">
                    <div>
                        <CardTitle className="text-lg">{agent.name}</CardTitle>
                        <CardDescription>{agent.category}</CardDescription>
                    </div>
                    <Badge variant={agent.status === 'running' ? 'default' : 'secondary'}>
                        {agent.status.toUpperCase()}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-muted-foreground">{agent.description}</p>
            </CardContent>
            <CardFooter className="gap-2">
                <Button
                    className="flex-1"
                    onClick={() => onRun(agent.id)}
                    disabled={agent.status === 'running'}
                >
                    <Play className="w-4 h-4 mr-2" />
                    Run Now
                </Button>
                <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => onSchedule(agent.id)}
                >
                    <Clock className="w-4 h-4 mr-2" />
                    Schedule
                </Button>
            </CardFooter>
        </Card>
    );
};
