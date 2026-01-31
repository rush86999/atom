'use client';

import React, { useState } from 'react';
import { Shield, FolderSearch, Loader2, AlertTriangle, ShieldCheck, Terminal } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export function DesktopSecurityAudit() {
    const [isScanning, setIsScanning] = useState(false);
    const [results, setResults] = useState<any>(null);
    const [selectedPath, setSelectedPath] = useState<string | null>(null);

    const handleSelectFolder = async () => {
        if (typeof window === 'undefined' || !window.__TAURI__) return;
        try {
            // Adapt to Upstream Tauri bridge pattern
            const invoke = (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke;
            const result = await invoke('open_folder_dialog');
            if (result && result.success) {
                setSelectedPath(result.path);
            }
        } catch (e) {
            toast.error("Failed to open folder dialog");
        }
    };

    const handleRunScan = async () => {
        if (!selectedPath || typeof window === 'undefined' || !window.__TAURI__) return;
        setIsScanning(true);
        setResults(null);

        try {
            const invoke = (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke;

            // Run the local CLI scanner via Tauri execute_command
            const scanOutput = await invoke('execute_command', {
                command: 'python3',
                args: ['-m', 'atom_security', selectedPath, '--format', 'json'],
            });

            if (scanOutput && scanOutput.success) {
                const findings = JSON.parse(scanOutput.stdout || "[]");
                setResults({
                    isSafe: findings.length === 0,
                    findings: findings,
                    raw: scanOutput.stdout
                });
                toast.success("Local security audit complete.");
            } else if (scanOutput) {
                // If it failed due to finding issues, parse them anyway
                try {
                    const findings = JSON.parse(scanOutput.stdout || "[]");
                    setResults({
                        isSafe: false,
                        findings: findings,
                        raw: scanOutput.stdout
                    });
                } catch {
                    toast.error("Security scan failed to complete.");
                }
            }
        } catch (error: any) {
            toast.error(`Scan execution error: ${error.message}`);
        } finally {
            setIsScanning(false);
        }
    };

    if (typeof window === 'undefined' || !window.__TAURI__) return null;

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-emerald-500" />
                    <CardTitle className="text-white font-black uppercase tracking-tighter">Local Security Audit</CardTitle>
                </div>
                <CardDescription className="text-zinc-500 text-xs">
                    Audit your local codebase via Atom Security CLI.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex gap-2">
                    <div className="flex-1 p-2 bg-black/40 border border-zinc-800 rounded-md text-[10px] font-mono truncate text-zinc-400">
                        {selectedPath || "No folder selected"}
                    </div>
                    <Button variant="outline" size="sm" onClick={handleSelectFolder} className="h-8 border-zinc-700 hover:bg-zinc-800 text-xs">
                        <FolderSearch className="h-3 w-3 mr-2" />
                        Browse
                    </Button>
                </div>

                <Button
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-9 text-xs"
                    disabled={!selectedPath || isScanning}
                    onClick={handleRunScan}
                >
                    {isScanning ? <Loader2 className="h-3 w-3 animate-spin mr-2" /> : <Terminal className="h-3 w-3 mr-2" />}
                    {isScanning ? 'AUDITING...' : 'RUN SECURITY SCAN'}
                </Button>

                {results && (
                    <div className="mt-4 p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-3">
                        <div className="flex items-center gap-2">
                            {results.isSafe ? (
                                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                            ) : (
                                <AlertTriangle className="h-4 w-4 text-red-500" />
                            )}
                            <span className={`text-xs font-black uppercase ${results.isSafe ? 'text-emerald-500' : 'text-red-500'}`}>
                                {results.isSafe ? "ALL CLEAR" : `${results.findings.length} RISKS DETECTED`}
                            </span>
                        </div>

                        {!results.isSafe && (
                            <div className="max-h-[120px] overflow-y-auto space-y-2 text-[10px] custom-scrollbar">
                                {results.findings.map((f: any, i: number) => (
                                    <div key={i} className="p-2 border border-zinc-800 rounded bg-zinc-900/50">
                                        <div className="flex justify-between font-bold text-zinc-300">
                                            <span>{f.category}</span>
                                            <span className="text-[10px] text-red-500 uppercase">{f.severity}</span>
                                        </div>
                                        <p className="text-zinc-500">{f.description}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
