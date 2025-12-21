import React, { useEffect, useRef, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Terminal } from 'lucide-react';

interface LogEntry {
    timestamp: string;
    message: string;
    level: 'info' | 'warning' | 'error' | 'success';
}

interface AgentTerminalProps {
    agentId: string | null;
    isRunning: boolean;
}

export const AgentTerminal: React.FC<AgentTerminalProps> = ({ agentId, isRunning }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    // Simulate receiving logs via WebSocket (Mock for MVP)
    useEffect(() => {
        if (!isRunning || !agentId) return;

        const interval = setInterval(() => {
            const mockLogs = [
                `[${agentId}] Navigating to target URL...`,
                `[${agentId}] Found selector #price-table...`,
                `[${agentId}] Extracting data...`,
                `[${agentId}] Storing snapshot in LanceDB...`,
                `[${agentId}] No variance detected.`
            ];
            const randomLog = mockLogs[Math.floor(Math.random() * mockLogs.length)];

            setLogs(prev => [...prev, {
                timestamp: new Date().toLocaleTimeString(),
                message: randomLog,
                level: 'info'
            }]);

        }, 2000);

        return () => clearInterval(interval);
    }, [isRunning, agentId]);

    if (!agentId) {
        return (
            <Card className="h-full bg-black text-green-500 font-mono border-gray-800">
                <CardContent className="flex items-center justify-center h-full">
                    <p className="opacity-50">Select an agent to view logs...</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="h-full bg-black text-green-500 font-mono border-gray-800 flex flex-col">
            <CardHeader className="py-2 border-b border-gray-800">
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4" />
                    <CardTitle className="text-sm">Agent Terminal: {agentId}</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="flex-1 p-0 overflow-hidden">
                <div ref={scrollRef} className="h-96 overflow-y-auto p-4 space-y-1">
                    {logs.map((log, i) => (
                        <div key={i} className="flex gap-2 text-xs">
                            <span className="opacity-50">[{log.timestamp}]</span>
                            <span className={
                                log.level === 'error' ? 'text-red-500' :
                                    log.level === 'warning' ? 'text-yellow-500' : 'text-green-500'
                            }>
                                {log.message}
                            </span>
                        </div>
                    ))}
                    {isRunning && (
                        <div className="animate-pulse">_</div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};
