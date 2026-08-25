import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    BadgeCheck,
    CheckCircle,
    Circle,
    Database,
    GraduationCap,
    Link2,
    Mail,
    MessageSquare,
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
const ROLE_KEY = 'atom.agent_launch_guide.role.v1';

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

type RoleId = 'sales' | 'marketing' | 'operations' | 'finance' | 'support';

/**
 * One recommendable app. `mode` decides the ingest affordance:
 *  - "sync": hybrid ingestion fetcher -> POST /api/data-ingestion/sync/{id}
 *    (records tagged with the employee's role for recall into its memory)
 *  - "backfill": memory backfill (Outlook email)
 *  - "link": no guided pipeline yet -> deep-link to its integrations page
 */
interface AppSource {
    id: string;
    label: string;
    blurb: string;
    /** token-store providers that satisfy the connection (defaults to [id]) */
    providers?: string[];
    /** /api/v1/auth/oauth/{oauth}/initiate segment, undefined = no direct flow */
    oauth?: string;
    mode: 'sync' | 'backfill' | 'link';
    /** true when offered without appearing in the ingestion registry */
    virtual?: boolean;
}

/** Apps we can describe beyond an id: OAuth flow + human copy. */
const KNOWN_APPS: Record<string, AppSource> = {
    zoho: {
        id: 'zoho',
        label: 'Zoho',
        blurb: 'CRM leads & deals, invoices, projects',
        oauth: 'zoho',
        mode: 'sync',
    },
    outlook: {
        id: 'outlook',
        label: 'Outlook email',
        blurb: 'customer threads & calendar',
        providers: ['outlook', 'microsoft'],
        oauth: 'microsoft',
        mode: 'backfill',
        virtual: true, // memory-backfill path, not in the sync registry
    },
    gmail: {
        id: 'gmail',
        label: 'Gmail',
        blurb: 'email threads & contacts',
        providers: ['google', 'gmail'],
        oauth: 'google',
        mode: 'sync',
    },
    slack: {
        id: 'slack',
        label: 'Slack',
        blurb: 'team conversations',
        oauth: 'slack',
        mode: 'sync',
    },
    salesforce: {
        id: 'salesforce',
        label: 'Salesforce',
        blurb: 'CRM contacts, leads, opportunities',
        oauth: 'salesforce',
        mode: 'sync',
    },
    hubspot: {
        id: 'hubspot',
        label: 'HubSpot',
        blurb: 'contacts, companies, deals',
        mode: 'sync',
    },
    shopify: {
        id: 'shopify',
        label: 'Shopify',
        blurb: 'products, orders, customers',
        mode: 'sync',
    },
    zendesk: {
        id: 'zendesk',
        label: 'Zendesk',
        blurb: 'support tickets & organizations',
        mode: 'sync',
    },
    notion: { id: 'notion', label: 'Notion', blurb: 'docs & databases', oauth: 'notion', mode: 'sync' },
    jira: { id: 'jira', label: 'Jira', blurb: 'issues & projects', mode: 'sync' },
    onedrive: {
        id: 'onedrive',
        label: 'OneDrive files',
        blurb: 'business documents',
        providers: ['outlook', 'microsoft'],
        oauth: 'microsoft',
        mode: 'sync',
    },
};

const genericApp = (id: string): AppSource => ({
    id,
    label: id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    blurb: '',
    mode: 'link',
});

/** Small-business roles and the kinds of apps each one lives in. */
const ROLES: Record<RoleId, {
    label: string;
    agentName: string;
    description: string;
    /** Ordered app preferences: exact registry ids, '*' wildcards (prefix*),
     * and virtual apps (outlook). First hits win; capped at MAX_APPS. */
    prefs: string[];
}> = {
    sales: {
        label: 'Sales',
        agentName: 'Sales Development Rep',
        description:
            'Owns inbound leads and the pipeline. Works CRM deals, follows up on customer email threads, and drafts outreach. Drafts everything for approval until promoted.',
        prefs: ['zoho*', 'salesforce', 'hubspot', 'outlook', 'gmail'],
    },
    marketing: {
        label: 'Marketing',
        agentName: 'Marketing Assistant',
        description:
            'Drafts campaigns and content, tracks what the team discusses, summarizes customer email feedback. Drafts everything for approval until promoted.',
        prefs: ['hubspot', 'gmail', 'slack', 'notion', 'outlook'],
    },
    operations: {
        label: 'Operations',
        agentName: 'Operations Coordinator',
        description:
            'Keeps work moving: summarizes team channels and email, drafts status updates and checklists. Drafts everything for approval until promoted.',
        prefs: ['slack', 'jira', 'notion', 'onedrive', 'gmail', 'outlook'],
    },
    finance: {
        label: 'Finance',
        agentName: 'Bookkeeping Assistant',
        description:
            'Reads invoices and billing records, reconciles against customer email threads, drafts summaries for review. Never posts without approval.',
        prefs: ['zoho*', 'shopify', 'outlook', 'gmail'],
    },
    support: {
        label: 'Support',
        agentName: 'Customer Support Agent',
        description:
            'Triages customer email and tickets, drafts replies and FAQs from past threads. Sends nothing without approval.',
        prefs: ['zendesk*', 'outlook', 'gmail', 'slack'],
    },
};

const MAX_APPS = 3;

const CONFIG_HINTS: Record<string, string> = {
    zoho: 'Needs ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET on the server first.',
    microsoft: 'Needs MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET on the server first.',
    google: 'Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET on the server first.',
    slack: 'Needs SLACK_CLIENT_ID / SLACK_CLIENT_SECRET on the server first.',
    salesforce: 'Needs SALESFORCE_CLIENT_ID / SALESFORCE_CLIENT_SECRET on the server first.',
    notion: 'Needs NOTION_CLIENT_ID / NOTION_CLIENT_SECRET on the server first.',
};

const SOURCE_ICONS: Record<string, React.ReactNode> = {
    outlook: <Mail className="w-4 h-4 text-gray-400" />,
    gmail: <Mail className="w-4 h-4 text-gray-400" />,
    slack: <MessageSquare className="w-4 h-4 text-gray-400" />,
};

/**
 * Guided journey for launching a first AI employee at a small business:
 * pick a role -> the guide MATCHES the role to your actually-available
 * integrations (ingestion registry + OAuth config) -> hire the employee ->
 * feed it context scoped to ITS memory -> train it.
 *
 * Connection state comes from GET /api/v1/auth/oauth/tokens (IntegrationToken
 * rows for the signed-in user); server-side OAuth config from
 * /api/v1/auth/oauth/config-status so unconfigured providers explain what is
 * missing instead of bouncing through a failed consent flow. Auto-hides once
 * every recommended app is connected and the employee exists.
 */
export function AgentLaunchGuide({ agents, onAgentsChanged }: AgentLaunchGuideProps) {
    const { toast } = useToast();
    const [dismissed, setDismissed] = useState(true); // SSR-safe: hidden until mounted
    const [roleId, setRoleId] = useState<RoleId>('sales');
    const [connections, setConnections] = useState<Record<string, boolean>>({});
    const [serverConfigured, setServerConfigured] = useState<Record<string, boolean>>({});
    const [pendingTraining, setPendingTraining] = useState<number | null>(null);
    const [registryIds, setRegistryIdsState] = useState<string[] | null>(null);
    // Mirror for stable-callback access: refreshConnections must keep a
    // constant identity or its presence in the mount effect's deps turns the
    // initial load into an infinite registry-refetch loop.
    const registryIdsRef = useRef<string[] | null>(null);

    // Create-agent dialog
    const [createOpen, setCreateOpen] = useState(false);
    const [creating, setCreating] = useState(false);
    const role = ROLES[roleId];
    const [newName, setNewName] = useState(role.agentName);
    const [newDescription, setNewDescription] = useState(role.description);

    // Ingestion actions
    const [busySource, setBusySource] = useState<string | null>(null);
    const [autoSyncEnabled, setAutoSyncEnabled] = useState<Record<string, boolean>>({});
    const [ingestResults, setIngestResults] = useState<string[]>([]);

    const roleAgents = useMemo(
        () => agents.filter(a => (a.category || '').toLowerCase() === roleId),
        [agents, roleId]
    );
    const primaryAgent = roleAgents[0] || null;

    /**
     * Role -> app matching. Walks the role's ordered prefs against the live
     * ingestion registry (plus virtual apps like Outlook), resolving
     * wildcards ('zoho*' matches 'zoho', 'zoho_crm'). Falls back to Gmail so
     * every role has at least one actionable row even on a bare install.
     */
    const recommendedApps = useMemo<AppSource[]>(() => {
        const matches: AppSource[] = [];
        const push = (app: AppSource) => {
            if (!matches.some(m => m.id === app.id)) matches.push(app);
        };
        for (const pref of role.prefs) {
            if (matches.length >= MAX_APPS) break;
            if (pref === 'outlook') {
                push(KNOWN_APPS.outlook);
                continue;
            }
            const wildcard = pref.endsWith('*')
                ? (id: string) => id.startsWith(pref.slice(0, -1))
                : (id: string) => id === pref;
            const hit = (registryIds || []).find(wildcard);
            if (hit) {
                push(KNOWN_APPS[hit] || genericApp(hit));
            }
        }
        if (matches.length === 0 && registryIds) push(KNOWN_APPS.gmail);
        return matches;
    }, [role, registryIds]);

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
                const next: Record<string, boolean> = {};
                const mark = (id: string, app: AppSource) => {
                    next[id] = (app.providers || [id]).some(p => active.has(p));
                };
                Object.values(KNOWN_APPS).forEach(a => mark(a.id, a));
                (registryIdsRef.current || []).forEach(id => {
                    if (!(id in next)) next[id] = active.has(id);
                });
                setConnections(next);
            }
            if (configRes.status === 'fulfilled') {
                setServerConfigured(configRes.value?.data || {});
            }
        } catch {
            // Leave steps unchecked rather than blocking the page.
        }
    }, []);

    const refreshRegistry = useCallback(async () => {
        try {
            const res = await apiClient.get('/api/data-ingestion/available-integrations');
            const data = res?.data?.data;
            if (Array.isArray(data)) {
                const ids = data.map((i: any) => i.id);
                registryIdsRef.current = ids;
                setRegistryIdsState(ids);
            }
        } catch {
            setRegistryIdsState(null); // fall back to preference defaults
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
            const saved = localStorage.getItem(ROLE_KEY) as RoleId | null;
            if (saved && ROLES[saved]) {
                setRoleId(saved);
                setNewName(ROLES[saved].agentName);
                setNewDescription(ROLES[saved].description);
            }
        } catch {
            setDismissed(false);
        }
        refreshRegistry();
        refreshConnections();
        refreshTrainingCount();
        const onFocus = () => {
            // Returning from the OAuth consent redirect lights up steps.
            refreshConnections();
            refreshTrainingCount();
        };
        window.addEventListener('focus', onFocus);
        return () => window.removeEventListener('focus', onFocus);
    }, [refreshRegistry, refreshTrainingCount, refreshConnections]);

    const pickRole = (id: RoleId) => {
        setRoleId(id);
        setNewName(ROLES[id].agentName);
        setNewDescription(ROLES[id].description);
        try { localStorage.setItem(ROLE_KEY, id); } catch { /* ignore */ }
    };

    const connectProvider = (oauth: string) => {
        const token =
            typeof window !== 'undefined'
                ? localStorage.getItem('auth_token') || localStorage.getItem('token')
                : null;
        const url = token
            ? `${API_BASE}/api/v1/auth/oauth/${oauth}/initiate?token=${encodeURIComponent(token)}`
            : `${API_BASE}/api/v1/auth/oauth/${oauth}/initiate`;
        window.location.href = url;
    };

    const pushResult = (line: string) =>
        setIngestResults(prev => [...prev.slice(-3), line]);

    const createEmployee = async () => {
        setCreating(true);
        try {
            await apiClient.post('/api/agents/custom', {
                name: newName.trim(),
                description: newDescription.trim(),
                category: role.label,
                configuration: {},
                schedule_config: {},
            });
            toast({
                title: `${role.label} employee hired`,
                description: `${newName.trim()} starts as a trainee — connect data next so it has context to learn from.`,
                duration: 6000,
            });
            setCreateOpen(false);
            onAgentsChanged?.();
        } catch (err: any) {
            const message =
                err?.response?.data?.error?.message ||
                err?.response?.data?.detail ||
                'Could not create the employee. Is the backend running?';
            toast({ title: 'Failed to create employee', description: message, variant: 'error' });
        } finally {
            setCreating(false);
        }
    };

    const runSync = async (sid: string) => {
        if (!primaryAgent) return;
        setBusySource(sid);
        try {
            const res = await apiClient.post(
                `/api/data-ingestion/sync/${sid}?agent_id=${encodeURIComponent(primaryAgent.id)}&force=true`
            );
            const body = res?.data || {};
            const label = KNOWN_APPS[sid]?.label || sid;
            pushResult(
                `${label}: fetched ${body.records_fetched ?? 0} records, ingested ${body.records_ingested ?? 0} into ${primaryAgent.name || 'your employee'}'s memory.` +
                (body.message && body.records_fetched === 0 ? ` (${body.message})` : '')
            );
        } catch (err: any) {
            pushResult(
                `${KNOWN_APPS[sid]?.label || sid}: ${err?.response?.data?.error?.message ||
                    err?.response?.data?.detail ||
                    err?.response?.data?.message ||
                    'sync failed. Confirm the connection and try again.'}`
            );
        } finally {
            setBusySource(null);
        }
    };

    const runOutlookBackfill = async () => {
        setBusySource('outlook');
        try {
            const res = await apiClient.post('/api/integrations/outlook/memory/backfill', null, {
                params: { limit: 500 },
            });
            const jobId = res?.data?.data?.job_id;
            if (!jobId) {
                pushResult('Outlook: backfill started.');
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
                    pushResult(`Outlook: backfilled ${status.processed_count ?? status.total_records ?? 0} emails into memory.`);
                    return;
                }
                if (status.state === 'failed' || status.error) {
                    pushResult('Outlook: backfill failed — check server logs.');
                    return;
                }
            }
            pushResult('Outlook: backfill running in the background — memory updates as emails land.');
        } catch (err: any) {
            pushResult(
                `Outlook: ${err?.response?.data?.detail ||
                    err?.response?.data?.error?.message ||
                    'backfill failed. Confirm the connection and try again.'}`
            );
        } finally {
            setBusySource(null);
        }
    };

    const enableAutoSync = async (sid: string) => {
        if (!primaryAgent) return;
        setBusySource(sid);
        try {
            await apiClient.post('/api/data-ingestion/enable-sync', {
                integration_id: sid,
                sync_last_n_days: 30,
            }, { params: { agent_id: primaryAgent.id } });
            setAutoSyncEnabled(prev => ({ ...prev, [sid]: true }));
            toast({ title: 'Auto-sync enabled', description: `${KNOWN_APPS[sid]?.label || sid} stays fresh in your employee\u2019s memory automatically.` });
        } catch (err: any) {
            toast({
                title: 'Auto-sync failed',
                description: err?.response?.data?.error?.message ||
                    err?.response?.data?.detail ||
                    'Could not enable auto-sync.',
                variant: 'error',
            });
        } finally {
            setBusySource(null);
        }
    };

    const allSourcesConnected = recommendedApps.every(app => connections[app.id]);
    const coreDone = registryIds !== null && recommendedApps.length > 0 && allSourcesConnected && !!primaryAgent;
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
                <Rocket className="w-4 h-4" /> First AI employee guide
            </button>
        );
    }
    if (coreDone) return null;

    const doneCount = recommendedApps.filter(app => connections[app.id]).length + (primaryAgent ? 1 : 0);
    const totalSteps = recommendedApps.length + 1;

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
                        Hire your first AI employee
                    </h2>
                    <span className="text-xs text-gray-400">{doneCount}/{totalSteps} setup steps complete</span>
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

            {/* Role picker drives app matching below */}
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex flex-wrap items-center gap-2" data-testid="launch-role-picker">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200 mr-1">Hire for:</span>
                {(Object.keys(ROLES) as RoleId[]).map(id => (
                    <button
                        key={id}
                        onClick={() => pickRole(id)}
                        data-testid={`launch-role-${id}`}
                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                            roleId === id
                                ? 'bg-indigo-600 text-white border-indigo-600'
                                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:border-indigo-400'
                        }`}
                    >
                        {ROLES[id].label}
                    </button>
                ))}
            </div>

            <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {/* Matched-app connect steps */}
                {recommendedApps.map((app, idx) => {
                    const connected = !!connections[app.id];
                    const configured = app.oauth ? serverConfigured[app.oauth] !== false : true;
                    return (
                        <div key={app.id} className="flex flex-wrap items-center gap-3 px-4 py-3" data-testid={`launch-step-${app.id}`}>
                            {stepHeader(SOURCE_ICONS[app.id] || <Link2 className="w-4 h-4 text-gray-400" />, `Connect ${app.label}`, connected)}
                            {!connected && (
                                configured ? (
                                    app.oauth ? (
                                        <Button size="sm" variant="outline" onClick={() => connectProvider(app.oauth!)} data-testid={`connect-${app.id}-cta`}>
                                            Connect {app.label}
                                        </Button>
                                    ) : (
                                        <Button size="sm" variant="outline" onClick={() => { window.location.href = `/integrations/${app.id}`; }} data-testid={`setup-${app.id}-cta`}>
                                            Set up {app.label}
                                        </Button>
                                    )
                                ) : (
                                    <span className="text-xs text-amber-600 dark:text-amber-400">
                                        {CONFIG_HINTS[app.oauth || '']}
                                    </span>
                                )
                            )}
                            {app.blurb && <span className="text-xs text-gray-400 basis-full sm:basis-auto">{app.blurb}</span>}
                            <span className="sr-only">Step {idx + 1}</span>
                        </div>
                    );
                })}

                {/* Hire the employee */}
                <div className="flex flex-wrap items-center gap-3 px-4 py-3" data-testid="launch-step-agent">
                    {stepHeader(<BadgeCheck className="w-4 h-4 text-gray-400" />, `Hire your ${role.label.toLowerCase()} employee`, !!primaryAgent)}
                    {!primaryAgent && (
                        <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)} data-testid="create-agent-cta">
                            Hire {role.agentName}
                        </Button>
                    )}
                    {!!primaryAgent && (
                        <span className="text-xs text-green-700 dark:text-green-400">
                            {primaryAgent.name} is live as a trainee.
                        </span>
                    )}
                </div>

                {/* Feed it context */}
                <div className="px-4 py-3 space-y-2" data-testid="launch-step-ingest">
                    <div className="flex items-center gap-1.5">
                        <Database className="w-4 h-4 text-gray-400" />
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Give it your business context</p>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        Synced records are tagged with this employee&rsquo;s role, so when you ask it something it recalls the records, threads and messages that belong to its job.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {recommendedApps.map(app => {
                            const busy = busySource === app.id;
                            if (app.mode === 'backfill') {
                                return (
                                    <Button
                                        key={app.id}
                                        size="sm"
                                        variant="outline"
                                        disabled={busy}
                                        onClick={runOutlookBackfill}
                                        data-testid={`backfill-${app.id}-cta`}
                                    >
                                        {busy ? 'Backfilling…' : `Backfill ${app.label}`}
                                    </Button>
                                );
                            }
                            if (app.mode === 'sync') {
                                return (
                                    <React.Fragment key={app.id}>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={!primaryAgent || busy}
                                            onClick={() => runSync(app.id)}
                                            data-testid={`sync-${app.id}-cta`}
                                        >
                                            {busy ? 'Syncing…' : `Sync ${app.label}`}
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            disabled={!primaryAgent || busy || autoSyncEnabled[app.id]}
                                            onClick={() => enableAutoSync(app.id)}
                                            data-testid={`enable-autosync-${app.id}-cta`}
                                        >
                                            {autoSyncEnabled[app.id] ? `${app.label} auto-sync on` : `Auto-sync ${app.label}`}
                                        </Button>
                                    </React.Fragment>
                                );
                            }
                            return (
                                <span key={app.id} className="text-xs text-gray-400 self-center">
                                    Ingest {app.label} data from its integrations page once connected.
                                </span>
                            );
                        })}
                    </div>
                    {ingestResults.length > 0 && (
                        <div className="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-900/40 rounded p-2 space-y-0.5" data-testid="ingest-results">
                            {ingestResults.map((line, i) => <p key={i}>{line}</p>)}
                        </div>
                    )}
                </div>

                {/* Train */}
                <div className="px-4 py-3 space-y-1" data-testid="launch-step-train">
                    <div className="flex items-center gap-1.5 justify-between">
                        <div className="flex items-center gap-1.5">
                            <GraduationCap className="w-4 h-4 text-gray-400" />
                            <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Train it, then give it more autonomy</p>
                        </div>
                        {!!pendingTraining && pendingTraining > 0 && (
                            <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400" data-testid="pending-training-badge">
                                {pendingTraining} training proposal{pendingTraining === 1 ? '' : 's'} waiting
                            </span>
                        )}
                    </div>
                    <ul className="text-xs text-gray-500 dark:text-gray-400 list-disc pl-4 space-y-0.5">
                        <li>New employees are trainees: they show you what they plan to do and ask before acting.</li>
                        <li>Run tasks with the Run button; approve their training plans under <a href="/approvals" className="text-blue-600 underline">Approvals</a>.</li>
                        <li>Finish training with a performance score to promote them — each level unlocks more they can do on their own.</li>
                    </ul>
                    <div className="pt-1">
                        <PlayCircle className="inline w-3.5 h-3.5 mr-1 text-gray-400" />
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                            Tip: thumbs up/down after runs teaches it your standards.
                        </span>
                    </div>
                </div>
            </div>

            {/* Hire dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Hire your {role.label.toLowerCase()} AI employee</DialogTitle>
                        <DialogDescription>
                            They start as a trainee — nothing risky happens without your OK. You can edit this later.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="launch-agent-name">Name &amp; job title</Label>
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
                                This steers behavior <em>and</em> which synced records they recall. Write it like a role spec: responsibilities, systems, boundaries.
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
                        <Button
                            onClick={createEmployee}
                            disabled={creating || !newName.trim()}
                            data-testid="launch-agent-submit"
                        >
                            {creating ? 'Hiring…' : 'Hire'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

export default AgentLaunchGuide;
