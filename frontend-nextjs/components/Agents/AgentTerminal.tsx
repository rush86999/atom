
import React, { useEffect, useRef } from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Terminal } from "lucide-react";

interface AgentTerminalProps {
    agentName: string;
    logs: string[];
    status: string;
}

const AgentTerminal: React.FC<AgentTerminalProps> = ({ agentName, logs, status }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    return (
        <div className="w-full h-96 bg-black rounded-lg border border-gray-800 flex flex-col font-mono text-sm shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-center px-4 py-2 bg-gray-900 border-b border-gray-800">
                <div className="flex items-center text-gray-400">
                    <Terminal className="w-4 h-4 mr-2" />
                    <span>{agentName}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
            </div>

            {/* Terminal Body */}
            <ScrollArea className="flex-1 p-4">
                <div className="flex flex-col gap-2">
                    {logs.length === 0 && (
                        <div className="text-gray-600 italic">Waiting for connection...</div>
                    )}
                    {logs.map((log, index) => {
                        // Attempt to parse structured logs if they look like JSON or have specific markers
                        const isAction = log.includes("Action:");
                        const isObservation = log.includes("Observation:");
                        const isThought = log.includes("Thought:");
                        const isFinal = log.includes("Final Answer:");

                        let contentColor = "text-green-400";
                        if (isAction) contentColor = "text-blue-400";
                        if (isObservation) contentColor = "text-yellow-400";
                        if (isThought) contentColor = "text-gray-400 italic";
                        if (isFinal) contentColor = "text-green-500 font-bold";

                        return (
                            <div key={index} className={`${contentColor} break-words text-xs`}>
                                <span className="text-gray-600 mr-2">[{new Date().toLocaleTimeString()}]</span>
                                <span className="mr-2 opacity-50">$</span>
                                {log}
                            </div>
                        );
                    })}
                    <div ref={scrollRef} />
                </div>
            </ScrollArea>
        </div>
    );
};

export default AgentTerminal;
