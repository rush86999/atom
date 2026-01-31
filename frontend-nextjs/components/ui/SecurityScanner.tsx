'use client';

import React from 'react';
import { Shield, ShieldAlert, ShieldCheck, AlertTriangle, AlertCircle, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface Finding {
    category: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    description: string;
    analyzer: string;
}

interface SecurityScannerProps {
    isScanning: boolean;
    results: {
        isSafe: boolean;
        findings: Finding[];
    } | null;
    onScan: () => void;
}

export const SecurityScanner: React.FC<SecurityScannerProps> = ({ isScanning, results, onScan }) => {
    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'CRITICAL': return 'bg-red-600 text-white';
            case 'HIGH': return 'bg-red-500 text-white';
            case 'MEDIUM': return 'bg-yellow-500 text-black';
            case 'LOW': return 'bg-blue-500 text-white';
            default: return 'bg-gray-500 text-white';
        }
    };

    return (
        <Card className="border-2 border-dashed bg-zinc-900/50 border-zinc-800">
            <CardHeader className="pb-3">
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-emerald-500" />
                        <CardTitle className="text-lg text-white font-black uppercase tracking-tighter">Security Check</CardTitle>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={onScan}
                        disabled={isScanning}
                        type="button"
                        className="border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-500"
                    >
                        {isScanning ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <ShieldCheck className="h-4 w-4 mr-2" />}
                        {isScanning ? 'Scanning...' : 'Scan Skill'}
                    </Button>
                </div>
                <CardDescription className="text-zinc-500">
                    Run semantic analysis on code and instructions.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {!results && !isScanning && (
                    <div className="text-center py-4 bg-zinc-800/20 rounded-lg border border-zinc-800/50">
                        <p className="text-xs text-zinc-400">Ensure your skill is safe from injections and logic flaws.</p>
                    </div>
                )}

                {isScanning && (
                    <div className="flex flex-col items-center justify-center py-6 gap-2">
                        <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
                        <p className="text-xs text-zinc-400">Analyzing security vectors...</p>
                    </div>
                )}

                {results && (
                    <div className="space-y-4">
                        <div className={`flex items-center gap-3 p-3 rounded-lg ${results.isSafe ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
                            {results.isSafe ? (
                                <ShieldCheck className="h-6 w-6 text-emerald-500" />
                            ) : (
                                <ShieldAlert className="h-6 w-6 text-red-500" />
                            )}
                            <div>
                                <p className={`font-black uppercase tracking-tighter ${results.isSafe ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {results.isSafe ? 'No Threats Detected' : `${results.findings.length} Risks Found`}
                                </p>
                                <p className="text-[10px] text-zinc-500 leading-tight">
                                    {results.isSafe
                                        ? 'Skill passed all automated security heuristics.'
                                        : 'Critical vulnerabilities detected. Review before deployment.'}
                                </p>
                            </div>
                        </div>

                        {results.findings.length > 0 && (
                            <div className="space-y-2 max-h-[160px] overflow-y-auto pr-2 custom-scrollbar">
                                {results.findings.map((finding, idx) => (
                                    <div key={idx} className="flex flex-col gap-1 p-2 rounded border border-zinc-800 bg-zinc-950 text-xs">
                                        <div className="flex justify-between items-center">
                                            <span className="font-bold flex items-center gap-1 text-zinc-200">
                                                {finding.severity === 'CRITICAL' || finding.severity === 'HIGH' ? (
                                                    <AlertCircle className="h-3 w-3 text-red-500" />
                                                ) : (
                                                    <AlertTriangle className="h-3 w-3 text-yellow-500" />
                                                )}
                                                {finding.category}
                                            </span>
                                            <Badge className={getSeverityColor(finding.severity)}>
                                                {finding.severity}
                                            </Badge>
                                        </div>
                                        <p className="text-[10px] text-zinc-400">{finding.description}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};
