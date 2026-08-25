import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    BadgeCheck,
    CheckCircle,
    Circle,
    Database,
    GraduationCap,
    Link2,
    Mail,
    PlayCircle,
    Rocket,
    X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api';
import { listTrainingProposals } from '@/lib/maturity-api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const DISMISS_KEY = 'atom.agent_launch_guide.dismissed.v1';

interface LaunchAgent {
    id: string;
    name?: string;
    category?: string;
}

interface AgentLaunchGuideProps {
    agents: LaunchAgent[];
    onAgentsChanged?: () => void;
}

interface TokenInfo {
    provider: string;
    status: string;
}

/**
 * Guided journey for launching a first sales AI employee:
 *   1. Connect Zoho CRM (OAuth)
 *   2. Connect Outlook (OAuth)
 *   3. Create the sales agent (starts as STUDENT)
 *   4. Ingest data scoped to that employee (Zoho sync tags records with the
 *      agent's role; Outlook emails backfill into memory)
 *   5. Train & graduate (blocked STUDENT triggers -> training proposals ->
 *      approve -> complete -> INTERN)
 *
 * Connection state comes from GET /api/v1/auth/oauth/tokens (IntegrationToken
 * rows for the signed-in user); server-side OAuth config from
 * /api/v1/auth/oauth/config-status so unconfigured providers explain what is
 * missing instead of bouncing through a failed consent flow.
 */
export function AgentLaunchGuide({ agents, onAgentsChanged }: AgentLaunchGuideProps) {
    const { toast } = useToast();
    const [dismissed, setDismissed] = useState(true); // SSR-safe: hidden until mounted
    const [connections, setConnections] = useState<{ zoho?: boolean; outlook?: boolean }>({});
    const [serverConfigured, setServerConfigured] = useState<{ zoho?: boolean; microsoft?: boolean }>({});
    const [pendingTraining, setPendingTraining] = useState<number | null>(null);

    // Create-agent dialog
    const [createOpen, setCreateOpen] = useState(false);
    const [newName, setNewName] = useState('Sales Development Rep');
    const [newDescription, setNewDescription] = useState(
        'Owns inbound leads and pipeline. Works Zoho CRM deals, follows up on Outlook email threads, and drafts outreach. Drafts everything for approval until promoted.'
    );
    const [creating, setCreating] = useState(false);

    // Ingestion actions
    const [syncingZoho, setSyncingZoho] = useState(false);
    const [zohoResult, setZohoResult] = useState<string | null>(null);
    const [enablingAutoSync, setEnablingAutoSync] = useState(false);
    const [autoSyncEnabled, setAutoSyncEnabled] = useState(false);
    const [backfillingOutlook, setBackfillingOutlook] = useState(false);
    const [outlookResult, setOutlookResult] = useState<string | null>(null);

    const salesAgent = useMemo(
        () => agents.find(a => (a.category || '').toLowerCase() === 'sales') || null,
        [agents]
    );

    const refreshConnections = useCallback(async () => {
        try {
            const [tokensRes, configRes] = await Promise.allSettled([
                apiClient.get('/api/v1/auth/oauth/tokens'),
                apiClient.get('/api/v1/auth/oauth/config-status'),
            ]);
            if (tokensRes.status === 'fulfilled') {
                const integrations: TokenInfo[] = tokensRes.value?.data?.integrations || [];
                const active = new Set(
                    integrations.filter(t => t.status === 'active').map(t => t.provider)
                );
                setConnections({
                    zoho: [...active].some(p => p.startsWith('zoho')),
                    outlook: [...active].some(p => p === 'outlook' || p === 'microsoft'),
                });
            }
            if (configRes.status === 'fulfilled') {
                setServerConfigured({
                    zoho: !!configRes.value?.data?.zoho,
                    microsoft: !!configRes.value?.data?.microsoft,
                });
            }
        } catch {
            // Leave steps unchecked rather than blocking the page.
        }
    }, []);

    const refreshTrainingCount = useCallback(async () => {
        try {
            const proposals = await listTrainingProposals();
            setPendingTraining(Array.isArray(proposals) ? proposals.length : 0);
        } catch {
            setPendingTraining(null);
        }
    }, []);

    useEffect(() => {
        try {
            setDismissed(localStorage.getItem(DISMISS_KEY) === '1');
        } catch {
            setDismissed(false);
        }
        refreshConnections();
        refreshTrainingCount();
        const onFocus = () => {
            // Returning from the OAuth consent redirect lights up steps.
            refreshConnections();
            refreshTrainingCount();
        };
        window.addEventListener('focus', onFocus);
        return () => window.removeEventListener('focus', onFocus);
    }, [refreshConnections, refreshTrainingCount]);

    const connectProvider = (provider: 'zoho' | 'microsoft') => {
        const token =
            typeof window !== 'undefined'
                ? localStorage.getItem('auth_token') || localStorage.getItem('token')
                : null;
        const url = token
            ? `${API_BASE}/api/v1/auth/oauth/${provider}/initiate?token=${encodeURIComponent(token)}`
            : `${API_BASE}/api/v1/auth/oauth/${provider}/initiate`;
        window.location.href = url;
    };

    const createSalesAgent = async () => {
        setCreating(true);
        try {
            await apiClient.post('/api/agents/custom', {
                name: newName.trim(),
                description: newDescription.trim(),
                category: 'Sales',
                configuration: {},
                schedule_config: {},
            });
            toast({
                title: 'Sales agent created',
                description: `${newName.trim()} starts at STUDENT maturity — ingest data next so it has context to learn from.`,
                duration: 6000,
            });
            setCreateOpen(false);
            onAgentsChanged?.();
        } catch (err: any) {
            const message =
                err?.response?.data?.error?.message ||
                err?.response?.data?.detail ||
                'Could not create the agent. Is the backend running?';
            toast({ title: 'Failed to create agent', description: message, variant: 'error' });
        } finally {
            setCreating(false);
        }
    };

    const syncZoho = async () => {
        if (!salesAgent) return;
        setSyncingZoho(true);
        setZohoResult(null);
        try {
            const res = await apiClient.post(
                `/api/data-ingestion/sync/zoho?agent_id=${encodeURIComponent(salesAgent.id)}&force=true`
            );
            const body = res?.data || {};
            setZohoResult(
                `Fetched ${body.records_fetched ?? 0} records, ingested ${body.records_ingested ?? 0} into ${salesAgent.name || 'your agent'}'s memory.`
            );
        } catch (err: any) {
            const detail =
                err?.response?.data?.error?.message ||
                err?.response?.data?.detail ||
                err?.response?.data?.message ||
                'Sync failed. Confirm the Zoho connection and try again.';
            setZohoResult(detail);
        } finally {
            setSyncingZoho(false);
        }
    };

    const enableAutoSync = async () => {
        if (!salesAgent) return;
        setEnablingAutoSync(true);
        try {
            await apiClient.post('/api/data-ingestion/enable-sync', {
                integration_id: 'zoho',
                sync_last_n_days: 30,
            }, { params: { agent_id: salesAgent.id } });
            setAutoSyncEnabled(true);
            toast({ title: 'Auto-sync enabled', description: 'Zoho records stay fresh in the agent\u2019s memory automatically.' });
        } catch (err: any) {
            const detail =
                err?.response?.data?.error?.message ||
                err?.response?.data?.detail ||
                'Could not enable auto-sync.';
            toast({ title: 'Auto-sync failed', description: detail, variant: 'error' });
        } finally {
            setEnablingAutoSync(false);
        }
    };

    const backfillOutlook = async () => {
        setBackfillingOutlook(true);
        setOutlookResult(null);
        try {
            const res = await apiClient.post('/api/integrations/outlook/memory/backfill', null, {
                params: { limit: 500 },
            });
            const jobId = res?.data?.data?.job_id;
            if (!jobId) {
                setOutlookResult('Backfill started.');
                return;
            }
            // Poll briefly so the user sees progress without leaving the page.
            for (let attempt = 0; attempt < 12; attempt++) {
                await new Promise(r => setTimeout(r, 2500));
                const statusRes = await apiClient.get(
                    `/api/integrations/outlook/memory/backfill/status/${jobId}`
                );
                const status = statusRes?.data?.data || {};
                if (status.state === 'completed' || status.state === 'done') {
                    setOutlookResult(`Backfilled ${status.processed_count ?? status.total_records ?? 0} emails into memory.`);
                    return;
                }
                if (status.state === 'failed' || status.error) {
                    setOutlookResult('Backfill failed — check server logs.');
                    return;
                }
            }
            setOutlookResult('Backfill running in the background — memory updates as emails land.');
        } catch (err: any) {
            const detail =
                err?.response?.data?.detail ||
                err?.response?.data?.error?.message ||
                'Backfill failed. Confirm the Outlook connection and try again.';
            setOutlookResult(detail);
        } finally {
            setBackfillingOutlook(false);
        }
    };

    const coreDone = !!(connections.zoho && connections.outlook && salesAgent);
    if (dismissed && !coreDone) {
        return (
            <button
                onClick={() => {
                    setDismissed(false);
                    try { localStorage.removeItem(DISMISS_KEY); } catch { /* ignore */ }
                }}
                data-testid="agent-launch-restore"
                className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 mb-4"
            >
                <Rocket className="w-4 h-4" /> Sales agent launch guide
            </button>
        );
    }
    if (coreDone) return null;

    const doneCount = [connections.zoho, connections.outlook, !!salesAgent].filter(Boolean).length;

    const stepHeader = (icon: React.ReactNode, title: string, done: boolean) => (
        <>
            {done
                ? <CheckCircle className="w-5 h-5 text-green-500 shrink-0" aria-label="Step complete" />
                : <Circle className="w-5 h-5 text-gray-300 dark:text-gray-600 shrink-0" />}
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
                {icon}
                <p className={`text-sm font-medium truncate ${done ? 'text-gray-400 dark:text-gray-500 line-through' : 'text-gray-800 dark:text-gray-100'}`}>
                    {title}
                </p>
            </div>
        </>
    );

    return (
        <div data-testid="agent-launch-guide" className="mb-6 bg-white dark:bg-gray-800 border border-indigo-100 dark:border-indigo-900 rounded-lg shadow-sm">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    <Rocket className="w-4 h-4 text-indigo-600" />
                    <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                        Launch your first sales AI employee
                    </h2>
                    <span className="text-xs text-gray-400">{doneCount}/3 setup steps complete</span>
                </div>
                <button
                    onClick={() => {
                        setDismissed(true);
                        try { localStorage.setItem(DISMISS_KEY, '1'); } catch { /* ignore */ }
                    }}
                    aria-label="Dismiss launch guide"
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>

            <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {/* Step 1 — Zoho */}
                <div className="flex flex-wrap items-center gap-3 px-4 py-3" data-testid="launch-step-zoho">
                    {stepHeader(<Link2 className="w-4 h-4 text-gray-400" />, 'Connect Zoho CRM', !!connections.zoho)}
                    {!connections.zoho && (
                        serverConfigured.zoho === false ? (
                            <span className="text-xs text-amber-600 dark:text-amber-400">
                                Needs ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET on the server first.
                            </span>
                        ) : (
                            <Button size="sm" variant="outline" onClick={() => connectProvider('zoho')} data-testid="connect-zoho-cta">
                                Connect Zoho
                            </Button>
                        )
                    )}
                </div>

                {/* Step 2 — Outlook */}
                <div className="flex flex-wrap items-center gap-3 px-4 py-3" data-testid="launch-step-outlook">
                    {stepHeader(<Mail className="w-4 h-4 text-gray-400" />, 'Connect Outlook', !!connections.outlook)}
                    {!connections.outlook && (
                        serverConfigured.microsoft === false ? (
                            <span className="text-xs text-amber-600 dark:text-amber-400">
                                Needs MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET on the server first.
                            </span>
                        ) : (
                            <Button size="sm" variant="outline" onClick={() => connectProvider('microsoft')} data-testid="connect-outlook-cta">
                                Connect Outlook
                            </Button>
                        )
                    )}
                </div>

                {/* Step 3 — Create the agent */}
                <div className="flex flex-wrap items-center gap-3 px-4 py-3" data-testid="launch-step-agent">
                    {stepHeader(<BadgeCheck className="w-4 h-4 text-gray-400" />, 'Create your sales agent', !!salesAgent)}
                    {!salesAgent && (
                        <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)} data-testid="create-agent-cta">
                            Create agent
                        </Button>
                    )}
                    {!!salesAgent && (
                        <span className="text-xs text-green-700 dark:text-green-400">
                            {salesAgent.name} is live at STUDENT maturity.
                        </span>
                    )}
                </div>

                {/* Step 4 — Ingest */}
                <div className="px-4 py-3 space-y-2" data-testid="launch-step-ingest">
                    <div className="flex items-center gap-1.5">
                        <Database className="w-4 h-4 text-gray-400" />
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Feed it your sales context</p>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        Synced Zoho records are tagged with the agent&rsquo;s role so recall surfaces them in its work; Outlook email lands in shared memory it can search.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={!salesAgent || syncingZoho}
                            onClick={syncZoho}
                            data-testid="sync-zoho-cta"
                        >
                            {syncingZoho ? 'Syncing…' : 'Sync Zoho now'}
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            disabled={!salesAgent || enablingAutoSync || autoSyncEnabled}
                            onClick={enableAutoSync}
                            data-testid="enable-autosync-cta"
                        >
                            {autoSyncEnabled ? 'Auto-sync on' : 'Enable auto-sync'}
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={backfillingOutlook}
                            onClick={backfillOutlook}
                            data-testid="backfill-outlook-cta"
                        >
                            {backfillingOutlook ? 'Backfilling…' : 'Backfill Outlook email'}
                        </Button>
                    </div>
                    {(zohoResult || outlookResult) && (
                        <div className="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-900/40 rounded p-2 space-y-0.5" data-testid="ingest-results">
                            {zohoResult && <p>{zohoResult}</p>}
                            {outlookResult && <p>{outlookResult}</p>}
                        </div>
                    )}
                </div>

                {/* Step 5 — Train */}
                <div className="px-4 py-3 space-y-1" data-testid="launch-step-train">
                    <div className="flex items-center gap-1.5 justify-between">
                        <div className="flex items-center gap-1.5">
                            <GraduationCap className="w-4 h-4 text-gray-400" />
                            <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Train it, then graduate it</p>
                        </div>
                        {!!pendingTraining && pendingTraining > 0 && (
                            <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400" data-testid="pending-training-badge">
                                {pendingTraining} training proposal{pendingTraining === 1 ? '' : 's'} waiting
                            </span>
                        )}
                    </div>
                    <ul className="text-xs text-gray-500 dark:text-gray-400 list-disc pl-4 space-y-0.5">
                        <li>Run tasks via the Run button below — a STUDENT agent asks before acting.</li>
                        <li>Blocked tasks become training proposals; approve them in Approvals (right panel or <a href="/approvals" className="text-blue-600 underline">/approvals</a>).</li>
                        <li>Complete training with a performance score to promote STUDENT&nbsp;&rarr;&nbsp;INTERN, where it can stream and draft with approval.</li>
                    </ul>
                    <div className="pt-1">
                        <PlayCircle className="inline w-3.5 h-3.5 mr-1 text-gray-400" />
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                            Tip: give feedback with thumbs up/down after runs — ratings steer its confidence.
                        </span>
                    </div>
                </div>
            </div>

            {/* Create-agent dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create your sales agent</DialogTitle>
                        <DialogDescription>
                            It starts as a STUDENT — read-only until it completes training. You can edit this later.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="launch-agent-name">Name</Label>
                            <Input
                                id="launch-agent-name"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                data-testid="launch-agent-name-input"
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="launch-agent-description">Job description</Label>
                            <Textarea
                                id="launch-agent-description"
                                value={newDescription}
                                onChange={(e) => setNewDescription(e.target.value)}
                                className="min-h-[100px]"
                                data-testid="launch-agent-description-input"
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                This steers behavior <em>and</em> which synced Zoho/Outlook records the employee recalls. Write it like a role spec.
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
                        <Button
                            onClick={createSalesAgent}
                            disabled={creating || !newName.trim()}
                            data-testid="launch-agent-submit"
                        >
                            {creating ? 'Creating…' : 'Create agent'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

export default AgentLaunchGuide;
