import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GraduationCap, Briefcase, ShieldCheck, Zap, Info } from 'lucide-react'
import { cn } from '../../utils/cn'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export type MaturityLevel = 'student' | 'intern' | 'supervised' | 'autonomous'

interface Tier {
    id: MaturityLevel
    name: string
    description: string
    icon: React.ElementType
    color: string
    bgColor: string
}

const TIERS: Tier[] = [
    {
        id: 'student',
        name: 'Student',
        description: '100% Manual. Requires human approval for every atomic action.',
        icon: GraduationCap,
        color: 'text-slate-500',
        bgColor: 'bg-slate-100'
    },
    {
        id: 'intern',
        name: 'Intern',
        description: 'Propose & Verify. Agent proposes a full plan; you approve the start.',
        icon: Briefcase,
        color: 'text-blue-500',
        bgColor: 'bg-blue-100'
    },
    {
        id: 'supervised',
        name: 'Supervised',
        description: 'Threshold Guarded. Automated unless high-risk or low-confidence.',
        icon: ShieldCheck,
        color: 'text-purple-500',
        bgColor: 'bg-purple-100'
    },
    {
        id: 'autonomous',
        name: 'Autonomous',
        description: 'Zero Friction. Fully authorized for production execution paths.',
        icon: Zap,
        color: 'text-orange-500',
        bgColor: 'bg-orange-100'
    }
]

interface MaturityProgressionProps {
    currentLevel: MaturityLevel
    className?: string
}

export function MaturityProgression({ currentLevel, className }: MaturityProgressionProps) {
    const currentIndex = TIERS.findIndex(t => t.id === currentLevel)

    return (
        <div className={cn("p-6 rounded-2xl bg-white border border-slate-100 shadow-sm", className)}>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h3 className="text-lg font-bold text-slate-900">Career Maturity Path</h3>
                    <p className="text-xs text-slate-500">Governance escalation from Sandbox to Production.</p>
                </div>
                <div className="flex -space-x-2">
                    {TIERS.map((tier, idx) => (
                        <div 
                            key={tier.id}
                            className={cn(
                                "h-8 w-8 rounded-full border-2 border-white flex items-center justify-center transition-all",
                                idx <= currentIndex ? tier.bgColor : "bg-slate-50",
                                idx === currentIndex && "ring-2 ring-offset-2 ring-blue-500 scale-110 z-10"
                            )}
                        >
                            <tier.icon className={cn("h-4 w-4", idx <= currentIndex ? tier.color : "text-slate-300")} />
                        </div>
                    ))}
                </div>
            </div>

            <div className="relative">
                {/* Progress Bar Background */}
                <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-100 -translate-y-1/2 rounded-full" />
                
                {/* Active Progress Bar */}
                <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${(currentIndex / (TIERS.length - 1)) * 100}%` }}
                    className="absolute top-1/2 left-0 h-1 bg-blue-500 -translate-y-1/2 rounded-full shadow-[0_0_10px_rgba(59,130,246,0.5)]"
                />

                <div className="relative flex justify-between items-center">
                    <TooltipProvider>
                        {TIERS.map((tier, idx) => {
                            const isActive = idx <= currentIndex
                            const isCurrent = idx === currentIndex
                            const Icon = tier.icon

                            return (
                                <Tooltip key={tier.id}>
                                    <TooltipTrigger asChild>
                                        <div className="flex flex-col items-center">
                                            <motion.div
                                                initial={false}
                                                animate={{
                                                    scale: isCurrent ? 1.2 : 1,
                                                    backgroundColor: isActive ? 'var(--tw-bg-opacity)' : '#F8FAFC'
                                                }}
                                                className={cn(
                                                    "h-12 w-12 rounded-2xl flex items-center justify-center cursor-help transition-all duration-500 shadow-sm",
                                                    isActive ? tier.bgColor : "bg-slate-100 border border-slate-200",
                                                    isCurrent && "border-2 border-blue-500 shadow-xl shadow-blue-500/10"
                                                )}
                                            >
                                                <Icon className={cn("h-6 w-6 transition-colors duration-500", isActive ? tier.color : "text-slate-400")} />
                                            </motion.div>
                                            <div className="mt-4 text-center">
                                                <p className={cn(
                                                    "text-[10px] uppercase font-bold tracking-widest",
                                                    isActive ? "text-slate-900" : "text-slate-400"
                                                )}>
                                                    {tier.name}
                                                </p>
                                                {isCurrent && (
                                                    <motion.div 
                                                        layoutId="active-indicator"
                                                        className="h-1.5 w-1.5 bg-blue-500 rounded-full mx-auto mt-1"
                                                    />
                                                )}
                                            </div>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-[200px] p-3 text-xs bg-slate-900 text-white border-0 shadow-2xl rounded-xl">
                                        <div className="flex items-start gap-2">
                                            <Info className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
                                            <div>
                                                <p className="font-bold mb-1">{tier.name} Mode</p>
                                                <p className="opacity-80 leading-relaxed font-medium">{tier.description}</p>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            )
                        })}
                    </TooltipProvider>
                </div>
            </div>

            {/* Maturity Context Card (Premium) */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={currentLevel}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="mt-8 p-4 rounded-xl border border-blue-50/50 bg-blue-50/20 backdrop-blur-sm flex items-center gap-4"
                >
                    <div className={cn("p-3 rounded-lg flex items-center justify-center", TIERS[currentIndex].bgColor)}>
                        {React.createElement(TIERS[currentIndex].icon, { className: cn("h-5 w-5", TIERS[currentIndex].color) })}
                    </div>
                    <div>
                        <h4 className="text-sm font-bold text-slate-800">Currently at {TIERS[currentIndex].name} Tier</h4>
                        <p className="text-xs text-slate-500 leading-relaxed">
                            {TIERS[currentIndex].description}
                        </p>
                    </div>
                </motion.div>
            </AnimatePresence>
        </div>
    )
}
