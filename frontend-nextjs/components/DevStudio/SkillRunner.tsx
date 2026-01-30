import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, Terminal, Search, Package, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

// Tauri imports
const { invoke } = typeof window !== 'undefined' ? require('@tauri-apps/api') : { invoke: null };
const { listen } = typeof window !== 'undefined' ? require('@tauri-apps/api/event') : { listen: null };

export interface Skill {
    id: string;
    name: string;
    description: string;
    path: string;
    version?: string;
    author?: string;
}

const SkillRunner = () => {
    const { toast } = useToast();
    const [skills, setSkills] = useState<Skill[]>([]);
    const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [isExecuting, setIsExecuting] = useState(false);
    const [output, setOutput] = useState<{ type: 'stdout' | 'stderr', text: string }[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll output
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [output]);

    // Listen for streaming output from Tauri
    useEffect(() => {
        let unlistenStdout: any;
        let unlistenStderr: any;

        const setupListeners = async () => {
            if (!listen) return;

            unlistenStdout = await listen('cli-stdout', (event: any) => {
                setOutput(prev => [...prev, { type: 'stdout', text: event.payload }]);
            });

            unlistenStderr = await listen('cli-stderr', (event: any) => {
                setOutput(prev => [...prev, { type: 'stderr', text: event.payload }]);
            });
        };

        setupListeners();

        return () => {
            if (unlistenStdout) unlistenStdout();
            if (unlistenStderr) unlistenStderr();
        };
    }, []);

    // Load available skills
    const loadSkills = async () => {
        if (!invoke) return;
        setIsLoading(true);
        try {
            const result = await invoke('list_local_skills');
            setSkills(result.skills || []);
        } catch (error) {
            console.error("Failed to load skills:", error);
            toast({
                title: "Discovery Failed",
                description: "Could not load local agent skills.",
                variant: "error"
            });
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadSkills();
    }, []);

    const runSkill = async () => {
        if (!selectedSkill || !invoke) return;

        setIsExecuting(true);
        setOutput([{ type: 'stdout', text: `🚀 Starting skill: ${selectedSkill.name}...` }]);

        try {
            // In a real scenario, we might pass args here
            const result = await invoke('execute_command', {
                command: 'python3',
                args: [`${selectedSkill.path}/main.py`], // Simplified execution logic
                workingDir: selectedSkill.path
            });

            if (result.success) {
                setOutput(prev => [...prev, { type: 'stdout', text: `\n✅ Skill execution completed successfully.` }]);
            } else {
                setOutput(prev => [...prev, { type: 'stderr', text: `\n❌ Skill failed with exit code: ${result.exit_code}` }]);
            }
        } catch (error: any) {
            setOutput(prev => [...prev, { type: 'stderr', text: `\n❌ Error: ${error.message || error}` }]);
        } finally {
            setIsExecuting(false);
        }
    };

    const filteredSkills = skills.filter(s =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-[700px]">
            {/* Skill Selector */}
            <Card className="col-span-1 flex flex-col overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-xl flex items-center gap-2">
                        <Package className="h-5 w-5 text-blue-500" />
                        Dynamic Skills
                    </CardTitle>
                    <CardDescription>Available agent skills in /skills/local</CardDescription>
                    <div className="relative mt-2">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search skills..."
                            className="pl-8"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-auto p-0">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center p-8 text-muted-foreground">
                            <Loader2 className="h-8 w-8 animate-spin mb-2" />
                            <p>Discovering skills...</p>
                        </div>
                    ) : filteredSkills.length === 0 ? (
                        <div className="p-8 text-center text-muted-foreground">
                            <p>No skills found.</p>
                            <p className="text-xs mt-1">Check skills/local/ directory.</p>
                        </div>
                    ) : (
                        <div className="divide-y">
                            {filteredSkills.map(skill => (
                                <button
                                    key={skill.id}
                                    className={`w-full text-left p-4 transition-colors hover:bg-muted/50 ${selectedSkill?.id === skill.id ? 'bg-muted border-l-4 border-blue-500' : ''}`}
                                    onClick={() => setSelectedSkill(skill)}
                                >
                                    <div className="flex justify-between items-start mb-1">
                                        <h3 className="font-semibold text-sm">{skill.name}</h3>
                                        {skill.version && <Badge variant="outline" className="text-[10px] h-4">{skill.version}</Badge>}
                                    </div>
                                    <p className="text-xs text-muted-foreground line-clamp-2">{skill.description}</p>
                                </button>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Execution Console */}
            <Card className="col-span-2 flex flex-col overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
                    <div>
                        <CardTitle className="text-xl flex items-center gap-2">
                            <Terminal className="h-5 w-5 text-green-500" />
                            Execution Console
                        </CardTitle>
                        <CardDescription>
                            {selectedSkill ? `Executing: ${selectedSkill.name}` : 'Select a skill to run'}
                        </CardDescription>
                    </div>
                    {selectedSkill && (
                        <Button
                            disabled={isExecuting}
                            onClick={runSkill}
                            className="bg-green-600 hover:bg-green-700 text-white gap-2 h-9"
                        >
                            {isExecuting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                            Run Skill
                        </Button>
                    )}
                </CardHeader>
                <CardContent className="flex-1 p-0 flex flex-col overflow-hidden bg-slate-950 font-mono text-sm">
                    <div
                        ref={scrollRef}
                        className="flex-1 overflow-auto p-4 space-y-1"
                    >
                        {output.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-slate-500 italic">
                                <Terminal className="h-8 w-8 mb-4 opacity-20" />
                                <p>Waiting for skill execution...</p>
                            </div>
                        ) : (
                            output.map((line, i) => (
                                <div
                                    key={i}
                                    className={line.type === 'stderr' ? 'text-red-400' : 'text-slate-300'}
                                >
                                    {line.text}
                                </div>
                            ))
                        )}
                    </div>
                    {isExecuting && (
                        <div className="p-2 bg-slate-900 flex items-center gap-2 text-xs text-blue-400 px-4">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>Agent active... executing skill logic</span>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default SkillRunner;
