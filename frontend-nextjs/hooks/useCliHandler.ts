'use client';

import { useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { toast } from 'sonner';

export const useCliHandler = () => {
    const { data: session } = useSession() as any;

    useEffect(() => {
        const checkCli = async () => {
            if (typeof window === 'undefined' || !window.__TAURI__) return;

            try {
                // Adapt to Upstream Tauri plugin pattern
                const { getMatches } = await import('@tauri-apps/plugin-cli');
                const matches = await getMatches();

                if (matches.subcommand?.name === 'scan') {
                    const scanPath = (matches.subcommand.matches.args.path as any).value;
                    console.log(`[CLI] Invoking security scan for: ${scanPath}`);

                    toast.loading(`Scanning ${scanPath} for vulnerabilities...`);

                    try {
                        const invoke = (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke;

                        const result = await invoke('execute_command', {
                            command: 'python3',
                            args: ['-m', 'atom_security', scanPath, '--format', 'text'],
                        });

                        if (result && result.success) {
                            console.log('[CLI] Scan Results:\n', result.stdout);
                            toast.success('Security scan complete. Check console for details.', {
                                duration: 5000,
                            });
                        } else if (result) {
                            console.warn('[CLI] Scan found issues or failed:\n', result.stderr || result.stdout);
                            toast.error('Security scan detected potential vulnerabilities.');
                        }
                    } catch (scanErr: any) {
                        console.error('[CLI] Scan execution error:', scanErr);
                        toast.error(`Security scan failed: ${scanErr.message}`);
                    }
                }
            } catch (err) {
                console.error('[CLI] Error checking CLI matches:', err);
            }
        };

        checkCli();
    }, [session]);
};
