'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Cpu, Power, Terminal, AlertCircle } from 'lucide-react'
import { useSession } from 'next-auth/react'

// Define Tauri types locally to avoid build errors if tauri libs aren't fully set up in Next.js
declare global {
    interface Window {
        __TAURI__?: any;
    }
}

export function SatelliteControls() {
    const { data: session } = useSession() as any
    const [isTauri, setIsTauri] = useState(false)
    const [status, setStatus] = useState<'stopped' | 'running' | 'error'>('stopped')
    const [message, setMessage] = useState('')
    const [scriptPath, setScriptPath] = useState('scripts/satellite/atom_satellite.py')

    useEffect(() => {
        setIsTauri(!!window.__TAURI__)
    }, [])

    const toggleSatellite = async () => {
        if (!window.__TAURI__) return;

        const invoke = window.__TAURI__.core.invoke;

        if (status === 'running') {
            try {
                await invoke('stop_satellite')
                setStatus('stopped')
                setMessage('Satellite disconnected.')
            } catch (e: any) {
                setMessage('Error stopping: ' + e)
            }
        } else {
            try {
                setStatus('running') // Optimistic
                setMessage('Starting Satellite...')

                // Get API Key from session
                const apiKey = session?.backendToken

                if (!apiKey) {
                    throw new Error("No API Key found. Please log in again.");
                }

                await invoke('start_satellite', {
                    apiKey,
                    scriptPath
                })

                setMessage('Satellite connected! Listening for cloud commands.')
            } catch (e: any) {
                setStatus('error')
                setMessage('Failed to start: ' + e)
            }
        }
    }

    if (!isTauri) return null;

    return (
        <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-white flex items-center gap-2">
                        <Cpu className="w-5 h-5 text-primary" />
                        Local Node (Satellite)
                    </CardTitle>
                    <Badge variant={status === 'running' ? 'default' : 'secondary'}
                        className={status === 'running' ? 'bg-emerald-500/20 text-emerald-400' : ''}>
                        {status.toUpperCase()}
                    </Badge>
                </div>
                <CardDescription>
                    Allow Atom Cloud to control this machine.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {status === 'error' && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        {message}
                    </div>
                )}

                <div className="space-y-2">
                    <Label className="text-xs text-zinc-500">Script Path (Dev)</Label>
                    <div className="flex gap-2">
                        <Input
                            value={scriptPath}
                            onChange={(e) => setScriptPath(e.target.value)}
                            className="h-8 text-xs font-mono bg-black/50 border-zinc-700"
                            disabled={status === 'running'}
                        />
                    </div>
                </div>

                <div className="p-3 bg-black/40 rounded-lg border border-white/5">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-zinc-400">Terminal Access</span>
                        <Badge variant="outline" className="text-[10px] h-5 border-zinc-700 text-zinc-500">
                            --allow-exec
                        </Badge>
                    </div>
                    <p className="text-[10px] text-zinc-600">
                        When active, agents can run commands like `ls`, `git`, or `npm` on this machine.
                    </p>
                </div>

                <Button
                    variant={status === 'running' ? "destructive" : "default"}
                    className="w-full"
                    onClick={toggleSatellite}
                >
                    <Power className="w-4 h-4 mr-2" />
                    {status === 'running' ? 'Disconnect Satellite' : 'Connect Satellite'}
                </Button>
            </CardContent>
        </Card>
    )
}
