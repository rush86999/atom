import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
    Brain, 
    Zap, 
    CheckCircle2, 
    XCircle, 
    Clock, 
    Search, 
    ChevronRight,
    Activity,
    Target,
    Lightbulb
} from 'lucide-react'
import { cn } from '../../utils/cn'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Card } from '@/components/ui/card'

interface Trajectory {
    id: string
    agent_id: string
    task_type: string
    outcome: string
    step_efficiency: number
    timestamp: string
    summary: string
    learnings?: string
    confidence_score?: number
}

interface MemoryRecallFeedProps {
    workspaceId: string
    agentId?: string
    className?: string
}

export function MemoryRecallFeed({ workspaceId, agentId, className }: MemoryRecallFeedProps) {
    const [trajectories, setTrajectories] = useState<Trajectory[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')

    useEffect(() => {
        const fetchTrajectories = async () => {
            setLoading(true)
            try {
                const url = new URL('/api/governance/analytics/trajectories', window.location.origin)
                url.searchParams.append('workspace_id', workspaceId)
                if (agentId) url.searchParams.append('agent_id', agentId)
                
                const response = await fetch(url.toString())
                if (response.ok) {
                    const data = await response.json()
                    setTrajectories(data)
                }
            } catch (error) {
                console.error('Failed to fetch trajectories:', error)
            } finally {
                setLoading(false)
            }
        }

        fetchTrajectories()
    }, [workspaceId, agentId])

    const filteredTrajectories = trajectories.filter(t => 
        t.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.task_type.toLowerCase().includes(searchQuery.toLowerCase())
    )

    return (
        <div className={cn("space-y-6", className)}>
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                        <Brain className="h-6 w-6 text-blue-500" />
                        Episodic Memory Feed
                    </h3>
                    <p className="text-sm text-slate-500">Live stream of agent experiences and neural recalls.</p>
                </div>
                <div className="relative w-full md:w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input 
                        placeholder="Search experiences..." 
                        className="pl-9 bg-white border-slate-200"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            <div className="space-y-4">
                {loading ? (
                    <div className="py-12 text-center text-slate-400">Loading neural events...</div>
                ) : filteredTrajectories.length === 0 ? (
                    <div className="py-12 text-center bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
                        <Activity className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                        <h4 className="text-slate-900 font-medium">No neural events found</h4>
                        <p className="text-slate-500 text-sm">Agents haven't generated any episodic traces yet.</p>
                    </div>
                ) : (
                    <AnimatePresence mode="popLayout">
                        {filteredTrajectories.map((trajectory, index) => (
                            <motion.div
                                key={trajectory.id}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ delay: index * 0.05 }}
                            >
                                <Card className="group overflow-hidden border-slate-200 hover:border-blue-200 hover:shadow-lg transition-all cursor-pointer">
                                    <div className="p-6 flex flex-col gap-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={cn(
                                                    "p-2 rounded-xl transition-colors",
                                                    trajectory.outcome.toLowerCase() === 'success' 
                                                        ? "bg-green-100 text-green-600 group-hover:bg-green-200" 
                                                        : "bg-amber-100 text-amber-600 group-hover:bg-amber-200"
                                                )}>
                                                    {trajectory.outcome.toLowerCase() === 'success' 
                                                        ? <CheckCircle2 className="h-6 w-6" /> 
                                                        : <Target className="h-6 w-6" />
                                                    }
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <h4 className="font-bold text-slate-900 capitalize">
                                                            {trajectory.task_type.replace(/_/g, ' ')}
                                                        </h4>
                                                        <Badge variant="secondary" className="text-[10px] uppercase tracking-wider h-5">
                                                            {trajectory.outcome}
                                                        </Badge>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                                                        <Clock className="h-3 w-3" />
                                                        {new Date(trajectory.timestamp).toLocaleString()}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end gap-1">
                                                <div className="text-[10px] uppercase font-bold text-slate-400">Efficiency</div>
                                                <div className="flex items-center gap-2">
                                                    <Progress 
                                                        value={(1 - Math.min(trajectory.step_efficiency, 1)) * 100} 
                                                        className="w-16 h-1.5" 
                                                    />
                                                    <span className="text-xs font-bold text-slate-700">
                                                        {Math.round((1 - Math.min(trajectory.step_efficiency, 1)) * 100)}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="bg-slate-50/50 p-4 rounded-xl border border-slate-100 group-hover:bg-blue-50/30 group-hover:border-blue-100 transition-all">
                                            <p className="text-sm text-slate-700 leading-relaxed font-medium">
                                                {trajectory.summary}
                                            </p>
                                        </div>

                                        {trajectory.learnings && (
                                            <div className="flex items-start gap-2 pt-2 border-t border-slate-100">
                                                <Lightbulb className="h-4 w-4 text-amber-500 mt-0.5" />
                                                <div>
                                                    <span className="text-[10px] uppercase font-bold text-slate-400 block">System Learning</span>
                                                    <p className="text-xs text-slate-600 italic">
                                                        "{trajectory.learnings}"
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                        
                                        <div className="flex items-center justify-between pt-2">
                                            <div className="flex items-center gap-4">
                                                <div className="flex items-center gap-1.5">
                                                    <Zap className="h-3.5 w-3.5 text-blue-500" />
                                                    <span className="text-xs font-bold text-slate-500">
                                                        Confidence: {Math.round((trajectory.confidence_score || 0.85) * 100)}%
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1 text-blue-500 font-bold text-xs opacity-0 group-hover:opacity-100 transition-all">
                                                View Trace <ChevronRight className="h-4 w-4" />
                                            </div>
                                        </div>
                                    </div>
                                </Card>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                )}
            </div>
        </div>
    )
}
