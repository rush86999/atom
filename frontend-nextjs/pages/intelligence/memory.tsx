import React, { useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { Brain, Shield, ArrowLeft, Target, Activity } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { MemoryRecallFeed } from '@/components/Agents/MemoryRecallFeed'
import { cn } from '../../utils/cn'

export default function MemoryDashboardPage() {
    // In submodule, we might not have subdomain-based multi-tenancy in the same way, 
    // using 'default' as workspaceId for now.
    const workspaceId = 'default'

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 font-sans">
            <Head>
                <title>Atom AI | Neural Memory</title>
            </Head>

            <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
                <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-blue-600 text-white rounded-2xl shadow-lg shadow-blue-200 dark:shadow-blue-900/20">
                            <Brain className="h-8 w-8" />
                        </div>
                        <div>
                            <nav className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
                                <Link href="/agents" className="hover:text-blue-600 transition-colors">Agents</Link>
                                <span>/</span>
                                <span className="text-slate-900 dark:text-white">Neural Memory</span>
                            </nav>
                            <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">Episodic Intelligence</h1>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button variant="outline" asChild className="border-slate-200 dark:border-slate-700 h-11 px-6 rounded-xl font-bold bg-white dark:bg-gray-800">
                            <Link href="/agents">
                                <Shield className="h-4 w-4 mr-2 text-slate-400" />
                                Control Center
                            </Link>
                        </Button>
                        <Button className="bg-blue-600 hover:bg-blue-700 text-white h-11 px-6 rounded-xl font-bold shadow-lg shadow-blue-200 dark:shadow-none border-0">
                            Archive Session
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    <div className="lg:col-span-8">
                        <MemoryRecallFeed workspaceId={workspaceId} />
                    </div>
                    
                    <div className="lg:col-span-4 space-y-6">
                        <div className="p-6 rounded-2xl bg-slate-900 text-white space-y-4 shadow-xl">
                            <div className="flex items-center gap-2">
                                <div className="p-1.5 bg-blue-500 rounded-lg">
                                    <Shield className="h-4 w-4" />
                                </div>
                                <h3 className="font-bold">Neural Security</h3>
                            </div>
                            <p className="text-xs text-slate-400 leading-relaxed">
                                Atom's memory is siloed and encrypted. Agents recall patterns and multi-step logic without ever exposing underlying raw data to third-party model training.
                            </p>
                            <ul className="space-y-3 pt-2">
                                {[
                                    "Zero-leak Vector Isolation",
                                    "Feedback-driven Confidence",
                                    "Episodic Pattern Recognition"
                                ].map((feature, i) => (
                                    <li key={i} className="flex items-center gap-2 text-xs font-medium text-slate-300">
                                        <div className="h-1 w-1 rounded-full bg-blue-500" />
                                        {feature}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="p-6 rounded-2xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-gray-800 shadow-sm space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="font-bold text-slate-900 dark:text-white">Confidence Distribution</h3>
                                <Activity className="h-4 w-4 text-slate-400" />
                            </div>
                            <div className="space-y-4 pt-2">
                                {[
                                    { label: "High Confidence", value: 72, color: "bg-green-500" },
                                    { label: "Needs Supervision", value: 18, color: "bg-blue-500" },
                                    { label: "Critical Failure", value: 10, color: "bg-amber-500" }
                                ].map((stat, i) => (
                                    <div key={i} className="space-y-1.5">
                                        <div className="flex justify-between text-[10px] uppercase font-bold text-slate-400">
                                            <span>{stat.label}</span>
                                            <span>{stat.value}%</span>
                                        </div>
                                        <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                            <div 
                                                className={cn("h-full rounded-full transition-all duration-1000", stat.color)} 
                                                style={{ width: `${stat.value}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="p-6 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-gray-800/50 text-center space-y-3">
                            <Target className="h-8 w-8 text-slate-300 mx-auto" />
                            <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200">World Model Sync</h4>
                            <p className="text-[10px] text-slate-500 leading-relaxed">
                                Episodic traces are periodically reconciled with the Global Knowledge Graph to improve cross-agent reasoning.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
