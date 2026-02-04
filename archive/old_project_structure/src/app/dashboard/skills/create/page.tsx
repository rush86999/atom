'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from '@/components/ui/label';
import { ArrowLeft, Loader2, Save, Wand2 } from 'lucide-react';
import { toast } from 'sonner';

export default function CreateSkillPage() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [aiPrompt, setAiPrompt] = useState('');
    const [isAiDialogOpen, setIsAiDialogOpen] = useState(false);

    // Form State
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [type, setType] = useState('api');

    // API Specific
    const [url, setUrl] = useState('');
    const [method, setMethod] = useState('GET');

    // Script Specific
    const [scriptContent, setScriptContent] = useState('');

    // Docker Specific
    const [dockerImage, setDockerImage] = useState('');
    const [dockerCommand, setDockerCommand] = useState('');

    // Container Specific
    const [containerImage, setContainerImage] = useState('');
    const [containerCommand, setContainerCommand] = useState('');
    const [cpuCount, setCpuCount] = useState('1');
    const [memoryMb, setMemoryMb] = useState('256');
    const [timeout, setTimeout] = useState('300');

    const [inputSchema, setInputSchema] = useState('{\n  "type": "object",\n  "properties": {}\n}');

    const handleAiGenerate = async () => {
        if (!aiPrompt.trim()) return;
        setIsGenerating(true);
        try {
            const res = await fetch('/api/skills/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: aiPrompt })
            });

            if (!res.ok) throw new Error('Generation failed');
            const data = await res.json();
            const skill = data.skill;

            setName(skill.name);
            setDescription(skill.description);
            if (skill.type === 'api') {
                setType('api');
                setUrl(skill.url);
                setMethod(skill.method);
            } else if (skill.type === 'script') {
                setType('script');
                setScriptContent(skill.config?.script || '');
            }

            setInputSchema(JSON.stringify(skill.inputSchema, null, 2));

            toast.success('Skill generated!');
            setIsAiDialogOpen(false);
        } catch (error) {
            toast.error('Failed to generate skill');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        try {
            let parsedSchema = {};
            try {
                parsedSchema = JSON.parse(inputSchema);
            } catch (err) {
                toast.error('Invalid JSON Schema');
                setIsLoading(false);
                return;
            }

            let config = {};
            if (type === 'api') {
                config = { url, method };
            } else if (type === 'script') {
                config = { script: scriptContent };
            } else if (type === 'container') {
                config = {
                    image: containerImage,
                    command: containerCommand,
                    cpu_count: parseInt(cpuCount),
                    memory_mb: parseInt(memoryMb),
                    timeout: parseInt(timeout)
                };
            } else if (type === 'docker') {
                config = { image: dockerImage, command: dockerCommand };
            }

            const payload = {
                name,
                description,
                type,
                inputSchema: parsedSchema,
                config
            };

            const res = await fetch('/api/skills', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.error || 'Failed to create skill');
            }

            toast.success('Skill created successfully');
            router.push('/dashboard/skills');
        } catch (error: any) {
            toast.error(error.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="container mx-auto max-w-2xl py-8">
            <Button variant="ghost" className="mb-4 pl-0 hover:bg-transparent" onClick={() => router.back()}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Back to Marketplace
            </Button>

            <Card>
                <CardHeader>
                    <div className="flex justify-between items-start">
                        <div>
                            <CardTitle>Create New Skill</CardTitle>
                            <CardDescription>Define a new capability for your agents.</CardDescription>
                        </div>
                        <Dialog open={isAiDialogOpen} onOpenChange={setIsAiDialogOpen}>
                            <DialogTrigger asChild>
                                <Button variant="outline" className="gap-2">
                                    <Wand2 className="h-4 w-4 text-purple-500" />
                                    Generate with AI
                                </Button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Generate Skill Definition</DialogTitle>
                                    <DialogDescription>
                                        Describe what this skill should do (e.g., "Get stock price from AlphaVantage").
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <Textarea
                                        placeholder="E.g. Create a skill to fetch weather data for a given city."
                                        value={aiPrompt}
                                        onChange={(e) => setAiPrompt(e.target.value)}
                                        className="min-h-[100px]"
                                    />
                                </div>
                                <DialogFooter>
                                    <Button onClick={handleAiGenerate} disabled={isGenerating}>
                                        {isGenerating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Generate
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                </CardHeader>
                <form onSubmit={handleSubmit}>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <Label htmlFor="name">Skill Name</Label>
                            <Input
                                id="name"
                                placeholder="e.g. Weather Service"
                                required
                                value={name}
                                onChange={e => setName(e.target.value)}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                placeholder="What does this skill do?"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="type">Type</Label>
                                <Select value={type} onValueChange={setType}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="api">API (REST)</SelectItem>
                                        <SelectItem value="script">Script (Node.js)</SelectItem>
                                        <SelectItem value="container">Container (Cloud Execution)</SelectItem>
                                        <SelectItem value="docker" disabled>Docker (Desktop Only)</SelectItem>
                                        <SelectItem value="function" disabled>Function (Coming Soon)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            {type === 'api' && (
                                <div className="space-y-2">
                                    <Label htmlFor="method">HTTP Method</Label>
                                    <Select value={method} onValueChange={setMethod}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="GET">GET</SelectItem>
                                            <SelectItem value="POST">POST</SelectItem>
                                            <SelectItem value="PUT">PUT</SelectItem>
                                            <SelectItem value="DELETE">DELETE</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>

                        {type === 'api' && (
                            <div className="space-y-2">
                                <Label htmlFor="url">Endpoint URL</Label>
                                <Input
                                    id="url"
                                    placeholder="https://api.example.com/v1/resource"
                                    required={type === 'api'}
                                    value={url}
                                    onChange={e => setUrl(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">Support dynamic params like {'{param}'}</p>
                            </div>
                        )}

                        {type === 'script' && (
                            <div className="space-y-2">
                                <Label htmlFor="script">Script Content (Node.js)</Label>
                                <Textarea
                                    id="script"
                                    className="font-mono text-sm min-h-[200px]"
                                    placeholder="params is available globally. return result at the end.&#10;const sum = params.a + params.b;&#10;return sum;"
                                    value={scriptContent}
                                    onChange={e => setScriptContent(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">Execution is sandboxed. Access inputs via <code>params</code>.</p>
                            </div>
                        )}

                        {type === 'docker' && (
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="image">Docker Image</Label>
                                    <Input
                                        id="image"
                                        placeholder="e.g. python:3.9-alpine"
                                        value={dockerImage}
                                        onChange={e => setDockerImage(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">Make sure the image is public or accessible.</p>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="command">Command (Optional)</Label>
                                    <Input
                                        id="command"
                                        placeholder="e.g. python script.py"
                                        value={dockerCommand}
                                        onChange={e => setDockerCommand(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">Params passed as env vars (SKILL_PARAMS).</p>
                                </div>
                            </div>
                        )}

                        {type === 'container' && (
                            <div className="space-y-4 border rounded-lg p-4 bg-orange-50 dark:bg-orange-950/20">
                                <div className="space-y-2">
                                    <Label htmlFor="container-image">Container Image</Label>
                                    <Input
                                        id="container-image"
                                        placeholder="python:3.9-slim or ghcr.io/user/my-skill:latest"
                                        value={containerImage}
                                        onChange={e => setContainerImage(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Use public images or your private registry. Must be accessible to the platform.
                                    </p>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="container-command">Command (Optional)</Label>
                                    <Input
                                        id="container-command"
                                        placeholder="python script.py"
                                        value={containerCommand}
                                        onChange={e => setContainerCommand(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Input parameters available as JSON in SKILL_PARAMS env var.
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="cpu-count">CPUs</Label>
                                        <Select value={cpuCount} onValueChange={setCpuCount}>
                                            <SelectTrigger id="cpu-count">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="1">1 CPU (Shared)</SelectItem>
                                                <SelectItem value="2">2 CPUs (Dedicated)</SelectItem>
                                                <SelectItem value="4">4 CPUs (Dedicated)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-muted-foreground">
                                            ~{parseInt(cpuCount) * 60} ACUs/min execution
                                        </p>
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="memory">Memory (MB)</Label>
                                        <Select value={memoryMb} onValueChange={setMemoryMb}>
                                            <SelectTrigger id="memory">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="256">256 MB</SelectItem>
                                                <SelectItem value="512">512 MB</SelectItem>
                                                <SelectItem value="1024">1 GB</SelectItem>
                                                <SelectItem value="2048">2 GB</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="timeout">Timeout (seconds)</Label>
                                    <Input
                                        id="timeout"
                                        type="number"
                                        min="10"
                                        max="3600"
                                        value={timeout}
                                        onChange={e => setTimeout(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Maximum execution time. Skill will be terminated if exceeded.
                                    </p>
                                </div>

                                <div className="bg-secondary/50 rounded-lg p-3 space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span>Estimated (60s):</span>
                                        <span className="font-medium">{parseInt(cpuCount) * 60} ACUs</span>
                                    </div>
                                    <div className="flex justify-between text-sm">
                                        <span>Maximum (timeout):</span>
                                        <span className="font-medium">{parseInt(cpuCount) * parseInt(timeout)} ACUs</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-2">
                                        💡 Actual cost based on execution time. You only pay for what you use.
                                    </p>
                                </div>
                            </div>
                        )}

                        <div className="space-y-2">
                            <Label htmlFor="schema">Input Schema (JSON)</Label>
                            <Textarea
                                id="schema"
                                className="font-mono text-sm min-h-[150px]"
                                value={inputSchema}
                                onChange={e => setInputSchema(e.target.value)}
                            />
                            <p className="text-xs text-muted-foreground">Define parameters using JSON Schema format.</p>
                        </div>

                    </CardContent>
                    <CardFooter className="flex justify-between">
                        <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Create Skill
                        </Button>
                    </CardFooter>
                </form>
            </Card>
        </div>
    );
}
