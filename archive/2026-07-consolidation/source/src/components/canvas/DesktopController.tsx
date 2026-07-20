'use client';

import React, { useState, useEffect } from 'react';
import { Monitor, Satellite, RefreshCw, Play, Square, Settings, Terminal, AlertCircle } from 'lucide-react';

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

interface DesktopControllerProps {
    canvasId: string;
}

export function DesktopController({ canvasId }: DesktopControllerProps) {
    const [sessions, setSessions] = useState<DesktopSession[]>([]);
    const [selectedSession, setSelectedSession] = useState<DesktopSession | null>(null);
    const [commands, setCommands] = useState<DesktopCommand[]>([]);
    const [commandInput, setCommandInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');

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
                // Command will appear in polling results
            } else {
                console.error('Failed to send command');
            }
        } catch (error) {
            console.error('Error sending command:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const testConnection = async () => {
        setConnectionStatus('connecting');
        // Simulate connection test
        setTimeout(() => {
            setConnectionStatus('connected');
            // Mock sessions for demo
            setSessions([
                {
                    id: 'demo-session-1',
                    platform: 'macos',
                    hostname: 'MacBook-Pro',
                    status: 'active',
                    last_active: new Date().toISOString(),
                },
            ]);
        }, 1000);
    };

    return (
        <div className="h-full flex flex-col bg-gray-950 text-white">
            {/* Header */}
            <div className="border-b border-gray-800 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Monitor className="w-6 h-6 text-indigo-400" />
                    <div>
                        <h2 className="text-lg font-semibold">Desktop Controller</h2>
                        <p className="text-xs text-gray-400">Manage Atom Satellite connections</p>
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
                    <button
                        onClick={testConnection}
                        className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
                        title="Test Connection"
                    >
                        <RefreshCw className="w-5 h-5 text-gray-400" />
                    </button>
                </div>
            </div>

            {/* Sessions List */}
            <div className="flex-1 overflow-auto p-4">
                {!selectedSession ? (
                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                        <Satellite className="w-16 h-16 text-gray-600" />
                        <div className="text-center space-y-2">
                            <h3 className="text-lg font-medium text-gray-300">No Desktop Selected</h3>
                            <p className="text-sm text-gray-500 max-w-md">
                                Connect to an Atom Satellite instance to control remote machines, execute commands,
                                and monitor desktop activities.
                            </p>
                            <button
                                onClick={testConnection}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition-colors"
                            >
                                <Satellite className="w-4 h-4 mr-2 inline" />
                                Scan for Satellites
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Selected Session Info */}
                        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    <Monitor className="w-5 h-5 text-indigo-400" />
                                    <span className="font-medium">{selectedSession.hostname}</span>
                                    <span className="text-xs text-gray-500">({selectedSession.platform})</span>
                                </div>
                                <button
                                    onClick={() => setSelectedSession(null)}
                                    className="text-xs text-gray-400 hover:text-white"
                                >
                                    Disconnect
                                </button>
                            </div>
                            <div className="text-xs text-gray-500">
                                Session ID: {selectedSession.id}
                            </div>
                        </div>

                        {/* Command Input */}
                        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                            <label className="text-sm font-medium text-gray-300 mb-2 block">
                                Execute Command
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={commandInput}
                                    onChange={(e) => setCommandInput(e.target.value)}
                                    placeholder="Enter shell command..."
                                    className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    onKeyPress={(e) => e.key === 'Enter' && sendCommand()}
                                />
                                <button
                                    onClick={sendCommand}
                                    disabled={isLoading || !commandInput.trim()}
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg flex items-center gap-2 transition-colors"
                                >
                                    {isLoading ? (
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Play className="w-4 h-4" />
                                    )}
                                    Execute
                                </button>
                            </div>
                        </div>

                        {/* Command History */}
                        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                            <h3 className="text-sm font-medium text-gray-300 mb-3">Command History</h3>
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                                {commands.length === 0 ? (
                                    <div className="text-center py-8 text-gray-500 text-sm">
                                        No commands executed yet
                                    </div>
                                ) : (
                                    commands.map((cmd) => (
                                        <div
                                            key={cmd.id}
                                            className={`bg-gray-800 border rounded-lg p-3 ${
                                                cmd.status === 'completed'
                                                    ? 'border-green-500/30'
                                                    : cmd.status === 'failed'
                                                    ? 'border-red-500/30'
                                                    : 'border-gray-700'
                                            }`}
                                        >
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Terminal className="w-4 h-4 text-gray-400" />
                                                        <code className="text-sm text-white">{cmd.command}</code>
                                                    </div>
                                                    {cmd.result && (
                                                        <pre className="text-xs text-gray-400 mt-2 overflow-x-auto">
                                                            {JSON.stringify(cmd.result, null, 2)}
                                                        </pre>
                                                    )}
                                                    {cmd.error && (
                                                        <div className="text-xs text-red-400 mt-2 flex items-center gap-1">
                                                            <AlertCircle className="w-3 h-3" />
                                                            {cmd.error}
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="text-xs text-gray-500">
                                                    {new Date(cmd.created_at).toLocaleTimeString()}
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
