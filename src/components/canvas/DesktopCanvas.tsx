'use client';

import { useState, useEffect } from 'react';
import { Monitor, Satellite, RefreshCw, Play, Square, Settings, AlertCircle, Maximize2, Minimize2, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { GuidancePanel, AgentAction } from './GuidancePanel';
import { useCanvasGuidance } from '@/hooks/useCanvasGuidance';
import { useAccessibilityMirror } from '@/lib/canvas/accessibility';

interface DesktopSession {
    id: string;
    platform: string;
    hostname: string;
    status: 'active' | 'offline';
    last_active: string;
}

interface DesktopCommand {
    id: string;
    command: string;
    payload: any;
    status: 'pending' | 'sent' | 'completed' | 'failed';
    result?: any;
    error?: string;
    created_at: string;
}

interface DesktopCanvasProps {
    canvasId: string;
}

export function DesktopCanvas({ canvasId }: DesktopCanvasProps) {
    const {
        currentAction,
        actionHistory,
        wsConnected,
        handleApprove,
        handleEdit,
        handleSkip,
        handleCancel,
        handleGuidance
    } = useCanvasGuidance(canvasId);

    const [sessions, setSessions] = useState<DesktopSession[]>([]);
    const [selectedSession, setSelectedSession] = useState<DesktopSession | null>(null);
    const [commands, setCommands] = useState<DesktopCommand[]>([]);
    const [commandInput, setCommandInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Accessibility mirror for screen readers and AI agents
    const accessibilityMirror = useAccessibilityMirror({
        canvasId,
        canvasType: 'desktop',
        getContent: () => {
            const lines: string[] = [];
            sessions.forEach(session => {
                lines.push(`[${session.id}] ${session.hostname} - ${session.platform}`);
            });
            if (commands.length > 0) {
                commands.forEach(cmd => {
                    lines.push(`Command: ${cmd.command} - Status: ${cmd.status}`);
                });
            } else {
                lines.push('No commands executed');
            }
            if (sessions.length === 0) lines.push('No desktop sessions');
            return lines;
        },
    });

    // Poll for commands from desktop
    useEffect(() => {
        if (!selectedSession) return;

        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/desktop/commands/poll', {
                    headers: {
                        'X-Session-Token': selectedSession.id,
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.commands && data.commands.length > 0) {
                        setCommands(prev => [...prev, ...data.commands.map((cmd: any) => ({
                            ...cmd,
                            status: 'sent',
                        }))]);
                    }
                }
            } catch (error) {
                console.error('Failed to poll commands:', error);
            }
        }, 2000); // Poll every 2 seconds

        return () => clearInterval(pollInterval);
    }, [selectedSession]);

    const sendCommand = async () => {
        if (!commandInput.trim() || !selectedSession) return;

        setIsLoading(true);
        try {
            const response = await fetch('/api/desktop/actions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-Token': selectedSession.id,
                },
                body: JSON.stringify({
                    action: 'execute_command',
                    command: commandInput,
                    canvas_id: canvasId,
                }),
            });

            if (response.ok) {
                const result = await response.json();
                setCommandInput('');
                toast.success('Command sent to desktop');
            } else {
                toast.error('Failed to send command');
            }
        } catch (error) {
            console.error('Error sending command:', error);
            toast.error('Error sending command');
        } finally {
            setIsLoading(false);
        }
    };

    const testConnection = async () => {
        setConnectionStatus('connecting');
        try {
            // Simulate connection test - in real app, would call actual connection API
            setTimeout(() => {
                setConnectionStatus('connected');
                setSessions([
                    {
                        id: 'demo-session-1',
                        platform: 'macos',
                        hostname: 'MacBook-Pro',
                        status: 'active',
                        last_active: new Date().toISOString(),
                    },
                ]);
                setSelectedSession({
                    id: 'demo-session-1',
                    platform: 'macos',
                    hostname: 'MacBook-Pro',
                    status: 'active',
                    last_active: new Date().toISOString(),
                });
                toast.success('Connected to desktop');
            }, 1000);
        } catch (error) {
            setConnectionStatus('disconnected');
            toast.error('Connection failed');
        }
    };

    return (
        <div className={`h-full flex flex-col bg-gray-950 text-white ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
            {/* Header */}
            <div className="border-b border-gray-800 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Monitor className="w-6 h-6 text-indigo-400" />
                    <div>
                        <h2 className="text-lg font-semibold">Desktop Canvas</h2>
                        <p className="text-xs text-gray-400">
                            {selectedSession ? `${selectedSession.hostname} (${selectedSession.platform})` : 'No desktop connected'}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs ${
                        connectionStatus === 'connected'
                            ? 'bg-green-500/20 text-green-400'
                            : connectionStatus === 'connecting'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-gray-500/20 text-gray-400'
                    }`}>
                        <div className={`w-2 h-2 rounded-full ${
                            connectionStatus === 'connected'
                                ? 'bg-green-400 animate-pulse'
                                : connectionStatus === 'connecting'
                                ? 'bg-yellow-400 animate-pulse'
                                : 'bg-gray-400'
                        }`} />
                        {connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={testConnection}
                        disabled={connectionStatus === 'connecting'}
                        title="Test Connection"
                    >
                        <RefreshCw className={`w-5 h-5 ${connectionStatus === 'connecting' ? 'animate-spin' : ''}`} />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setIsFullscreen(!isFullscreen)}
                        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
                    >
                        {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                    </Button>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden">
                {/* Desktop View */}
                <div className="flex-1 flex flex-col">
                    {/* Session List */}
                    <div className="p-4 border-b border-gray-800">
                        <div className="flex items-center gap-2 mb-3">
                            <Satellite className="w-5 h-5 text-gray-400" />
                            <h3 className="text-sm font-medium">Desktop Sessions</h3>
                        </div>
                        <div className="space-y-2">
                            {sessions.length === 0 ? (
                                <div className="text-center py-8 text-gray-500">
                                    <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p className="text-sm">No desktop sessions connected</p>
                                    <Button
                                        onClick={testConnection}
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                    >
                                        Connect Desktop
                                    </Button>
                                </div>
                            ) : (
                                sessions.map(session => (
                                    <div
                                        key={session.id}
                                        className={`p-3 rounded-lg cursor-pointer transition-colors ${
                                            selectedSession?.id === session.id
                                                ? 'bg-indigo-500/20 border border-indigo-500/50'
                                                : 'bg-gray-900 border border-gray-800 hover:border-gray-700'
                                        }`}
                                        onClick={() => setSelectedSession(session)}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Monitor className="w-4 h-4" />
                                                <span className="font-medium">{session.hostname}</span>
                                            </div>
                                            <Badge variant={session.status === 'active' ? 'default' : 'secondary'}>
                                                {session.status}
                                            </Badge>
                                        </div>
                                        <div className="text-xs text-gray-400 mt-1">
                                            {session.platform} • Last active: {new Date(session.last_active).toLocaleTimeString()}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Command Output */}
                    <div className="flex-1 p-4 overflow-auto">
                        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                            <Terminal className="w-4 h-4" />
                            Command History
                        </h3>
                        <div className="space-y-2">
                            {commands.length === 0 ? (
                                <div className="text-center py-8 text-gray-500 text-sm">
                                    No commands executed yet
                                </div>
                            ) : (
                                commands.map(cmd => (
                                    <div key={cmd.id} className="bg-gray-900 rounded-lg p-3 border border-gray-800">
                                        <div className="flex items-center justify-between mb-2">
                                            <code className="text-sm text-indigo-400">{cmd.command}</code>
                                            <Badge variant={
                                                cmd.status === 'completed' ? 'default' :
                                                cmd.status === 'failed' ? 'destructive' :
                                                cmd.status === 'sent' ? 'secondary' : 'outline'
                                            }>
                                                {cmd.status}
                                            </Badge>
                                        </div>
                                        {cmd.error && (
                                            <div className="text-red-400 text-sm mt-2">{cmd.error}</div>
                                        )}
                                        {cmd.result && (
                                            <pre className="text-gray-300 text-xs mt-2 overflow-auto">
                                                {JSON.stringify(cmd.result, null, 2)}
                                            </pre>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Command Input */}
                    <div className="p-4 border-t border-gray-800">
                        <div className="flex gap-2">
                            <Input
                                value={commandInput}
                                onChange={(e) => setCommandInput(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && sendCommand()}
                                placeholder={selectedSession ? `Enter command for ${selectedSession.hostname}...` : 'Connect to a desktop first'}
                                disabled={!selectedSession || isLoading}
                                className="flex-1 bg-gray-900 border-gray-700 text-white placeholder:text-gray-500"
                            />
                            <Button
                                onClick={sendCommand}
                                disabled={!selectedSession || !commandInput.trim() || isLoading}
                            >
                                {isLoading ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Guidance Panel */}
                {wsConnected && (
                    <div className="w-80 border-l border-gray-800">
                        <GuidancePanel
                            currentAction={currentAction}
                            actionHistory={actionHistory}
                            onApprove={handleApprove}
                            onEdit={handleEdit}
                            onSkip={handleSkip}
                            onCancel={handleCancel}
                            onGuidance={handleGuidance}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
