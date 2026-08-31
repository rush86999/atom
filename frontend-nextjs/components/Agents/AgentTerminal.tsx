import React, { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import {
    Terminal as TerminalIcon,
    Inbox
} from 'lucide-react'
import { cn } from '../../utils/cn'
import { ScrollArea } from '@/components/ui/scroll-area'

// Log lines arrive over WebSocket as plain text. The timestamp is captured
// when the line is appended (in the parent), so later re-renders of this
// component can never rewrite history for older lines.
export interface LogEntry {
    text: string
    ts: number
}

interface AgentTerminalProps {
    agentId?: string
    agentName: string
    logs: LogEntry[]
    status: string
}

// Only the statuses the backend actually emits; anything unknown shows as Idle.
const STATUS_STYLES: Record<string, { label: string; className: string; animate?: boolean }> = {
    running: { label: 'Running', className: 'text-blue-300 border-blue-500/40 bg-blue-500/10', animate: true },
    success: { label: 'Completed', className: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10' },
    failed: { label: 'Failed', className: 'text-red-300 border-red-500/40 bg-red-500/10' },
    stopped: { label: 'Stopped', className: 'text-amber-300 border-amber-500/40 bg-amber-500/10' },
    idle: { label: 'Idle', className: 'text-slate-400 border-slate-700 bg-slate-800/50' },
}

// Color log lines by the prefixes the dashboard appends to each ReAct step.
const lineClass = (text: string) => {
    if (/^Final Answer:/i.test(text)) return 'text-emerald-300 font-semibold'
    if (/error/i.test(text)) return 'text-red-400'
    if (/success/i.test(text)) return 'text-emerald-400'
    if (/^Thought:/i.test(text)) return 'text-violet-300'
    if (/^Action:/i.test(text)) return 'text-blue-300'
    if (/^Observation:/i.test(text)) return 'text-sky-300'
    if (/^Status Changed:/i.test(text)) return 'text-amber-300'
    return 'text-slate-300'
}

const formatTime = (ts: number) =>
    new Date(ts).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

export const AgentTerminal: React.FC<AgentTerminalProps> = ({ agentId, agentName, logs, status }) => {
    const scrollAreaRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (logs.length === 0) {
            return
        }

        const viewport = scrollAreaRef.current?.querySelector<HTMLDivElement>('[data-radix-scroll-area-viewport]')
        if (viewport) {
            viewport.scrollTop = viewport.scrollHeight
        }
    }, [logs.length])

    const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.idle
    const lastEntry = logs.length > 0 ? logs[logs.length - 1] : null

    return (
        <div className="relative w-full h-[500px] bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col font-mono text-xs">
            {/* Header: agent identity + real execution status */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800 z-10">
                <div className="flex items-center gap-2 min-w-0">
                    <TerminalIcon className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="font-bold tracking-tight text-[11px] text-slate-200 truncate" title={agentName}>
                        {agentName}
                    </span>
                </div>
                <span
                    className={cn(
                        "flex items-center gap-1.5 border rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider shrink-0",
                        statusStyle.className
                    )}
                >
                    {statusStyle.animate && (
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-400" />
                        </span>
                    )}
                    {statusStyle.label}
                </span>
            </div>

            {/* Log lines */}
            <div className="flex-1 relative flex flex-col overflow-hidden">
                <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
                    {logs.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-slate-500">
                            <Inbox className="h-8 w-8 mb-3" />
                            <p className="font-semibold text-slate-400">No activity yet</p>
                            <p className="italic mt-1 text-slate-600">
                                Live steps from every agent stream here as they work — canvas chats,
                                training and runs included. Waiting for the next event.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            {logs.map((entry, idx) => (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="flex items-start gap-3 py-0.5"
                                >
                                    <span className="text-slate-600 shrink-0 select-none text-[10px] pt-0.5">
                                        {formatTime(entry.ts)}
                                    </span>
                                    <div className={cn("flex-1 leading-relaxed break-words", lineClass(entry.text))}>
                                        {entry.text}
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </div>

            {/* Footer: real stream facts only */}
            <div className="px-4 py-2 bg-slate-900 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[10px] text-slate-500" data-testid="terminal-event-count">
                    {logs.length} {logs.length === 1 ? 'event' : 'events'}
                </span>
                <span className="text-[10px] text-slate-500">
                    {lastEntry ? `Last event ${formatTime(lastEntry.ts)}` : 'Waiting for first event'}
                </span>
            </div>
        </div>
    )
}

export default AgentTerminal
