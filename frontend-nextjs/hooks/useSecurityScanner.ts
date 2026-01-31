'use client';

import { useState, useCallback } from 'react';
import { toast } from 'sonner';

interface Finding {
    category: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    description: string;
    analyzer: string;
}

interface ScanResult {
    isSafe: boolean;
    findings: Finding[];
}

export const useSecurityScanner = () => {
    const [isScanning, setIsScanning] = useState(false);
    const [results, setResults] = useState<ScanResult | null>(null);

    const scanSkill = useCallback(async (
        skillName: string,
        instructionBody: string,
        fileContents: Record<string, string> = {}
    ) => {
        setIsScanning(true);
        setResults(null);

        try {
            const isTauri = typeof window !== 'undefined' && '__TAURI__' in window;

            if (isTauri) {
                // Desktop Mode: Try local CLI scanner first via Tauri bridge
                console.log('[Security] Running desktop scan...');

                let invoke;
                try {
                    // Adapt to Upstream Tauri bridge pattern
                    invoke = (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke;
                    if (!invoke) {
                        const tauriCore = await import('@tauri-apps/api/core');
                        invoke = tauriCore.invoke;
                    }
                } catch (e) {
                    console.warn('[Security] Could not load Tauri invoke:', e);
                }

                if (invoke) {
                    // 1. Prepare temp file for scanning
                    const filename = `temp_scan_${Date.now()}.py`;
                    const content = fileContents['main.py'] || instructionBody;

                    try {
                        const writeResult = await invoke('write_file_content', {
                            path: `./temp/${filename}`,
                            content: content
                        });

                        if (writeResult && (writeResult.success || writeResult === true)) {
                            const scanResult = await invoke('execute_command', {
                                command: 'python3',
                                args: ['-m', 'atom_security', `./temp/${filename}`, '--format', 'json'],
                            });

                            if (scanResult && scanResult.success) {
                                const rawFindings = JSON.parse(scanResult.stdout || '[]');
                                const findings: Finding[] = rawFindings.map((f: any) => ({
                                    category: f.category,
                                    severity: f.severity,
                                    description: f.description,
                                    analyzer: 'static'
                                }));

                                setResults({
                                    isSafe: findings.length === 0,
                                    findings: findings
                                });
                                return;
                            }
                        }
                    } catch (tauriError) {
                        console.error('[Security] Tauri scan error:', tauriError);
                    }
                }
            }

            // Web Mode or Desktop Fallback: Use Local/BYOK Backend if available
            // In Open Source, the backend also expose this endpoint
            const response = await fetch('/api/protection/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    skill_name: skillName,
                    instruction_body: instructionBody,
                    file_contents: fileContents
                })
            });

            if (!response.ok) throw new Error('Security scan API failed');

            const data = await response.json();
            setResults({
                isSafe: data.is_safe,
                findings: data.findings
            });

        } catch (error: any) {
            console.error('[Security] Scan error:', error);
            // Fallback for missing sonner in upstream if needed, but assuming it exists
            toast.error(`Security scan failed: ${error.message}`);
        } finally {
            setIsScanning(false);
        }
    }, []);

    return {
        scanSkill,
        isScanning,
        results,
        setResults
    };
};
