import React, { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
    Terminal as TerminalIcon, 
    Globe, 
    Shield, 
    Zap, 
    Activity,
    Mail,
    Database,
    MessageSquare,
    CheckCircle2,
    Cpu,
    Puzzle,
    CreditCard,
    Github,
    Table,
    CheckSquare,
    HardDrive,
    ShoppingBag,
    Share2,
    Settings
} from 'lucide-react'
import { cn } from '../../utils/cn'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'

interface AgentTerminalProps {
    agentId?: string
    agentName: string
    logs: string[]
    status: string
    activeTools?: string[]
}

const TOOL_ICONS: Record<string, { icon: any, color: string }> = {
    outlook: { icon: Mail, color: 'text-blue-400' },
    gmail: { icon: Mail, color: 'text-red-400' },
    mail: { icon: Mail, color: 'text-slate-400' },
    zoho: { icon: Database, color: 'text-amber-400' },
    salesforce: { icon: Database, color: 'text-blue-500' },
    crm: { icon: Database, color: 'text-indigo-400' },
    database: { icon: Database, color: 'text-slate-400' },
    whatsapp: { icon: MessageSquare, color: 'text-emerald-400' },
    slack: { icon: MessageSquare, color: 'text-purple-400' },
    teams: { icon: MessageSquare, color: 'text-blue-600' },
    discord: { icon: MessageSquare, color: 'text-indigo-500' },
    message: { icon: MessageSquare, color: 'text-slate-400' },
    excel: { icon: Table, color: 'text-green-400' },
    sheets: { icon: Table, color: 'text-emerald-500' },
    table: { icon: Table, color: 'text-slate-400' },
    github: { icon: Github, color: 'text-white' },
    stripe: { icon: CreditCard, color: 'text-indigo-400' },
    shopify: { icon: ShoppingBag, color: 'text-emerald-400' },
    jira: { icon: CheckSquare, color: 'text-blue-400' },
    linear: { icon: CheckSquare, color: 'text-slate-200' },
    gdrive: { icon: HardDrive, color: 'text-blue-400' },
    dropbox: { icon: HardDrive, color: 'text-blue-500' },
    system: { icon: Shield, color: 'text-purple-400' },
    generic: { icon: Puzzle, color: 'text-slate-400' }
};

export const AgentTerminal: React.FC<AgentTerminalProps> = ({ agentId, agentName, logs, status, activeTools = [] }) => {
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [logs])

    const getToolInfo = (toolName: string) => {
        const normalized = toolName.toLowerCase();
        return TOOL_ICONS[normalized] || TOOL_ICONS.generic;
    };

    return (
        <div className="relative w-full h-[500px] bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col font-mono text-xs">
            {/* Glossy Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-slate-900 via-slate-900 to-slate-950 border-b border-slate-800/50 backdrop-blur-xl z-20">
                <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                        <div className="h-2.5 w-2.5 rounded-full bg-red-400/80 shadow-[0_0_8px_rgba(248,113,113,0.4)]" />
                        <div className="h-2.5 w-2.5 rounded-full bg-amber-400/80 shadow-[0_0_8px_rgba(251,191,36,0.4)]" />
                        <div className="h-2.5 w-2.5 rounded-full bg-emerald-400/80 shadow-[0_0_8px_rgba(52,211,153,0.4)]" />
                    </div>
                    <div className="h-4 w-px bg-slate-800 mx-1" />
                    <div className="flex items-center gap-2 text-slate-400">
                        <TerminalIcon className="h-3.5 w-3.5" />
                        <span className="font-bold tracking-tight text-[10px] uppercase text-slate-300">{agentName} // EXECUTION_LOG</span>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <AnimatePresence>
                        {status === 'running' && (
                            <motion.div 
                                initial={{ opacity: 0, scale: 0.8 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0 }}
                                className="flex items-center gap-2"
                            >
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                                </span>
                                <span className="text-[10px] font-bold text-blue-400 uppercase tracking-widest">Active Reasoning</span>
                            </motion.div>
                        )}
                    </AnimatePresence>
                    <Badge variant="outline" className="border-slate-800 text-slate-500 bg-slate-900/50 px-2 h-5 text-[9px] uppercase font-black tracking-tighter">
                        v2.4.0-COGNITIVE
                    </Badge>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden">
                {/* Main Log Area */}
                <div className="flex-1 relative flex flex-col bg-[#020617]">
                    <ScrollArea className="flex-1 p-6">
                        <div className="space-y-1.5">
                            {logs.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full pt-20 text-slate-700 opacity-50">
                                    <Cpu className="h-8 w-8 mb-4 animate-pulse" />
                                    <p className="italic">Kernal loaded. Waiting for agent initiation...</p>
                                </div>
                            ) : (
                                logs.map((log, idx) => {
                                    const toolMatch = log.match(/\[([A-Z0-9_-]+)\]/i);
                                    const toolName = toolMatch ? toolMatch[1].toLowerCase() : null;
                                    const isTool = !!toolMatch;
                                    const isSystem = toolName === 'system';
                                    const isError = log.match(/error/i)
                                    const isSuccess = log.match(/success/i)

                                    return (
                                        <motion.div 
                                            key={idx}
                                            initial={{ opacity: 0, x: -5 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            className={cn(
                                                "group flex items-start gap-3 py-0.5 border-l-2 border-transparent hover:border-slate-800 transition-all",
                                                isTool && "bg-blue-500/5 border-l-blue-500/50 -mx-6 px-6",
                                                isSystem && "bg-purple-500/5 border-l-purple-500/50 -mx-6 px-6",
                                                isError && "text-red-400 bg-red-500/5 border-l-red-500/50 -mx-6 px-6"
                                            )}
                                        >
                                            <span className="text-slate-600 shrink-0 select-none min-w-[65px] text-[9px] font-bold">
                                                {new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                            </span>
                                            <span className="text-slate-800 font-bold select-none shrink-0">$</span>
                                            <div className={cn(
                                                "flex-1 leading-relaxed break-words",
                                                isSuccess ? "text-emerald-400" : 
                                                isSystem ? "text-purple-300 font-black tracking-tight" :
                                                isTool ? "text-blue-300 font-bold" : 
                                                isError ? "text-red-400" : "text-slate-400"
                                            )}>
                                                {log}
                                            </div>
                                        </motion.div>
                                    )
                                })
                            )}
                            <div ref={scrollRef} className="h-4" />
                        </div>
                    </ScrollArea>

                    {/* Active Intercepts Tooltray (Sleek side tab) */}
                    <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
                         {Array.from(new Set(activeTools)).map(tool => {
                             const { icon: ToolIcon, color } = getToolInfo(tool);
                             return (
                                <motion.div 
                                    key={tool}
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    className="p-2 rounded-xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-lg flex items-center justify-center group hover:bg-slate-800 transition-colors"
                                 >
                                    <ToolIcon className={cn("h-4 w-4", color)} />
                                    <div className="absolute right-full mr-2 px-2 py-1 rounded bg-slate-800 text-white text-[9px] font-bold uppercase tracking-widest opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none transition-opacity">
                                        Interception Active: {tool}
                                    </div>
                                 </motion.div>
                             )
                         })}
                    </div>
                </div>

                {/* Secure Sandbox Environment (Visual Sidecar) */}
                <div className="w-[30%] bg-slate-900/30 border-l border-slate-800/50 hidden md:flex flex-col relative overflow-hidden group">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_rgba(0,0,0,0.4)_100%)] z-10 pointer-events-none" />
                    
                    <div className="p-3 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Globe className="h-3 w-3 text-slate-500" />
                            <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">Ephemeral Browser</span>
                        </div>
                        <div className="flex gap-1.5 opacity-50">
                            <div className="h-1.5 w-1.5 rounded-full bg-slate-700" />
                            <div className="h-1.5 w-1.5 rounded-full bg-slate-700" />
                        </div>
                    </div>

                    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-4">
                        <Activity className="h-10 w-10 text-slate-800 animate-pulse" />
                        <div className="space-y-1">
                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Sandbox Isolated</p>
                            <p className="text-[9px] text-slate-600 italic leading-relaxed">Agent is orchestrating legacy apps via ephemeral session...</p>
                        </div>
                    </div>

                    {/* Visual Overlay for Security */}
                    <div className="absolute bottom-4 left-4 right-4 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 backdrop-blur-sm z-20">
                        <div className="flex items-center gap-2 mb-1">
                            <Shield className="h-3 w-3 text-emerald-500" />
                            <span className="text-[8px] font-black uppercase text-emerald-500/80">Self-Hosted Vault</span>
                        </div>
                        <p className="text-[8px] text-slate-500 leading-tight">Logs and credentials never leave your infrastructure.</p>
                    </div>
                </div>
            </div>

            {/* Footer / Connection Status */}
            <div className="px-4 py-2 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-1.5 text-[9px] text-slate-500">
                        <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                        <span>SSH SECURE</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[9px] text-slate-500">
                        <Zap className="h-3 w-3 text-amber-500" />
                        <span>LATENCY: 42ms</span>
                    </div>
                </div>
                <div className="flex items-center gap-2 text-[9px] font-bold text-slate-600">
                    <span className="animate-pulse h-1.5 w-1.5 rounded-full bg-slate-800" />
                    LISTENING_ON_PORT_54321
                </div>
            </div>
        </div>
    )
}

export default AgentTerminal
