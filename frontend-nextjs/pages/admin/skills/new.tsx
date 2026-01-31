'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/router' // Changed from next/navigation for Pages Router
import { Code, FileText, Save, Terminal, Cpu, CheckCircle, AlertTriangle, ArrowLeft } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card' // Assuming generic UI exists or needs adaptation
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { SecurityScanner } from '@/components/ui/SecurityScanner'
import { useSecurityScanner } from '@/hooks/useSecurityScanner'

export default function NewSkillPage() {
    const { data: session } = useSession() as any
    const router = useRouter()

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    // Form State
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [instructions, setInstructions] = useState('')
    const [capabilitiesInput, setCapabilitiesInput] = useState('')
    const [scriptContent, setScriptContent] = useState('# write your python script here\n\ndef main():\n    print("Hello from Atom Skill!")\n\nif __name__ == "__main__":\n    main()')
    const [scriptName, setScriptName] = useState('script.py')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)
        setSuccess(null)

        try {
            const capabilities = capabilitiesInput.split(',').map(c => c.trim()).filter(c => c)

            const payload = {
                name,
                description,
                instructions,
                capabilities,
                scripts: {
                    [scriptName]: scriptContent
                }
            }

            const res = await fetch('/api/admin/skills', { // This endpoint matches backend port
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session?.backendToken}`
                },
                body: JSON.stringify(payload)
            })

            const data = await res.json()

            if (!res.ok) {
                throw new Error(data.detail || 'Failed to create skill')
            }

            setSuccess(`Skill '${name}' created successfully`)

        } catch (err: any) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const { scanSkill, isScanning, results } = useSecurityScanner();

    const handleSecurityScan = () => {
        scanSkill(name || 'Untitled', instructions || '', { [scriptName]: scriptContent });
    };

    return (
        <div className="bg-black min-h-screen p-6">
            <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto">
                <div className="flex items-center gap-4 mb-6">
                    <Button variant="ghost" size="icon" onClick={() => router.back()}>
                        <ArrowLeft className="w-4 h-4 text-white" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-black text-white tracking-tight flex items-center gap-3">
                            <Cpu className="text-primary h-8 w-8" />
                            Skill Builder
                        </h1>
                        <p className="text-zinc-400 mt-1">Create portable "Skill Skill" packages for your agents.</p>
                    </div>
                </div>

                {error && (
                    <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        {error}
                    </div>
                )}

                {success && (
                    <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-500 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5" />
                        {success}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                    {/* Left Column: Metadata */}
                    <div className="lg:col-span-1 space-y-6">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-primary" />
                                    Metadata
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label className="text-zinc-400">Skill Name</Label>
                                    <Input
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="e.g., data-scraper"
                                        className="bg-black/50 border-zinc-800 text-white"
                                        required
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label className="text-zinc-400">Description</Label>
                                    <Textarea
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="What does this skill do?"
                                        className="bg-black/50 border-zinc-800 min-h-[100px] text-white"
                                        required
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label className="text-zinc-400">Capabilities (comma separated)</Label>
                                    <Input
                                        value={capabilitiesInput}
                                        onChange={(e) => setCapabilitiesInput(e.target.value)}
                                        placeholder="scrape, interactions"
                                        className="bg-black/50 border-zinc-800 text-white"
                                    />
                                    <div className="flex flex-wrap gap-2 mt-2">
                                        {capabilitiesInput.split(',').filter(c => c.trim()).map((cap, i) => (
                                            <Badge key={i} variant="secondary" className="text-xs">
                                                {cap.trim()}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Terminal className="w-4 h-4 text-primary" />
                                    Instructions
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    <Label className="text-zinc-400">Usage Guide (System Prompt)</Label>
                                    <Textarea
                                        value={instructions}
                                        onChange={(e) => setInstructions(e.target.value)}
                                        placeholder="Tell the agent how to use this skill..."
                                        className="bg-black/50 border-zinc-800 min-h-[150px] text-white"
                                        required
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        <SecurityScanner
                            isScanning={isScanning}
                            results={results}
                            onScan={handleSecurityScan}
                        />

                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? <span className="animate-spin mr-2">⏳</span> : <Save className="w-4 h-4 mr-2" />}
                            {loading ? 'Packaging...' : 'Create Skill Package'}
                        </Button>
                    </div>

                    {/* Right Column: Code Editor */}
                    <div className="lg:col-span-2">
                        <Card className="bg-zinc-900 border-zinc-800 h-full flex flex-col">
                            <CardHeader className="border-b border-zinc-800 pb-4">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-white flex items-center gap-2">
                                        <Code className="w-4 h-4 text-primary" />
                                        Script Editor
                                    </CardTitle>
                                    <div className="flex items-center gap-2">
                                        <Input
                                            value={scriptName}
                                            onChange={(e) => setScriptName(e.target.value)}
                                            className="h-8 w-40 bg-black/50 border-zinc-700 text-xs font-mono text-white"
                                        />
                                    </div>
                                </div>
                                <CardDescription className="text-zinc-400">
                                    This script will be executed in the secure cloud sandbox.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="p-0 flex-1 relative min-h-[500px]">
                                <Textarea
                                    value={scriptContent}
                                    onChange={(e) => setScriptContent(e.target.value)}
                                    className="w-full h-full min-h-[500px] resize-none border-0 rounded-none bg-[#0d0d0d] font-mono text-sm p-6 focus-visible:ring-0 leading-relaxed text-emerald-400"
                                    spellCheck={false}
                                />
                            </CardContent>
                        </Card>
                    </div>

                </form>
            </div>
        </div>
    )
}
