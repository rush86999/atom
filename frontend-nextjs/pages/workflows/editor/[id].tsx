import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import WorkflowBuilder from '@/components/Automations/WorkflowBuilder';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Loader2 } from 'lucide-react';
import { Node, Edge } from 'reactflow';

export default function WorkflowEditorPage() {
    const router = useRouter();
    const { id } = router.query;
    const { toast } = useToast();
    const [isLoading, setIsLoading] = useState(true);
    const [initialData, setInitialData] = useState<{ nodes: Node[], edges: Edge[] } | undefined>(undefined);
    const [templateName, setTemplateName] = useState('');

    // First-run checklist: required inputs + integration readiness for the
    // imported workflow. Advisory only — never blocks editing.
    const [requiredInputs, setRequiredInputs] = useState<string[]>([]);
    const [missingDeps, setMissingDeps] = useState<string[]>([]);
    const [connectUrls, setConnectUrls] = useState<string[]>([]);
    const [checklistDismissed, setChecklistDismissed] = useState(false);

    // Run flow: parameter entry dialog generated from the template's inputs.
    const [templateInputs, setTemplateInputs] = useState<any[]>([]);
    const [runOpen, setRunOpen] = useState(false);
    const [paramValues, setParamValues] = useState<Record<string, string>>({});
    const [isRunning, setIsRunning] = useState(false);
    const [lastRun, setLastRun] = useState<{ id: string; status: string | null } | null>(null);
    const [resultsOpen, setResultsOpen] = useState(false);
    const [runResults, setRunResults] = useState<{
        steps: { step_id?: string; step_type?: string; status?: string; notes?: string | null }[];
        outputs: Record<string, any> | null;
    } | null>(null);

    useEffect(() => {
        if (!id) return;
        fetchWorkflow(id as string);
    }, [id]);

    const fetchWorkflow = async (workflowId: string) => {
        setIsLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const res = await fetch(`/api/workflow-templates/${workflowId}`, {
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                }
            });
            if (!res.ok) throw new Error('Failed to load workflow');

            const template = await res.json();
            setTemplateName(template.name);
            setTemplateInputs(template.inputs || []);
            setRequiredInputs(
                (template.inputs || [])
                    .filter((i: any) => i.required)
                    .map((i: any) => i.label || i.name)
            );

            // Integration readiness (fail-soft; personal starters declare deps).
            fetch(`/api/workflow-templates/${workflowId}/readiness`, {
                headers: { ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
            })
                .then(r => (r.ok ? r.json() : null))
                .then(d => {
                    if (d && typeof d.ready === 'boolean' && !d.ready) {
                        setMissingDeps(d.missing || []);
                        setConnectUrls(d.connect_urls || []);
                    }
                })
                .catch(() => {});

            // Convert Backend Template -> React Flow Nodes/Edges
            const newNodes: Node[] = [];
            const newEdges: Edge[] = [];

            if (template.steps && template.steps.length > 0) {
                template.steps.forEach((step: any, idx: number) => {
                    // Simple layout strategy: Staggered diagonal
                    newNodes.push({
                        id: step.step_id,
                        type: mapStepTypeToNode(step.step_type),
                        position: { x: 250, y: 100 + (idx * 150) },
                        data: {
                            label: step.name,
                            description: step.description,
                            ...step
                        }
                    });

                    // Edges
                    if (step.depends_on) {
                        step.depends_on.forEach((depId: string) => {
                            newEdges.push({
                                id: `e-${depId}-${step.step_id}`,
                                source: depId,
                                target: step.step_id,
                                type: 'addStepEdge'
                            });
                        });
                    }
                });
            } else {
                // Default start node if empty
                newNodes.push({
                    id: 'start',
                    type: 'trigger',
                    position: { x: 250, y: 50 },
                    data: { label: 'Start Trigger' }
                });
            }

            setInitialData({ nodes: newNodes, edges: newEdges });

        } catch (error) {
            console.error(error);
            toast({ title: 'Error', description: 'Failed to load workflow template', variant: 'error' });
        } finally {
            setIsLoading(false);
        }
    };

    const mapStepTypeToNode = (stepType: string): string => {
        // Map backend types to frontend node types
        switch (stepType) {
            case 'agent_execution': return 'agent';
            case 'llm_process': return 'ai_node';
            case 'condition': return 'condition';
            case 'trigger': return 'trigger';
            default: return 'action';
        }
    };

    const handleSave = async (data: { nodes: Node[], edges: Edge[] }) => {
        try {
            // Convert React Flow -> Backend JSON
            const steps = data.nodes.map(node => ({
                step_id: node.id,
                name: node.data.label,
                description: node.data.description,
                step_type: mapNodeToStepType(node.type),
                parameters: node.data.parameters || [],
                depends_on: data.edges
                    .filter(e => e.target === node.id)
                    .map(e => e.source)
            }));

            const payload = {
                name: templateName,
                description: "Updated via Visual Editor",
                steps: steps
            };

            const token = localStorage.getItem('auth_token');
            const res = await fetch(`/api/workflow-templates/${id}`, {
                method: 'PUT',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error('Failed to save to backend');

            toast({ title: 'Saved', description: 'Workflow template updated successfully.' });

        } catch (error) {
            console.error(error);
            toast({ title: 'Error', description: 'Failed to save workflow', variant: 'error' });
        }
    };

    const mapNodeToStepType = (nodeType: string | undefined): string => {
        switch (nodeType) {
            case 'agent': return 'agent_execution';
            case 'ai_node': return 'llm_process';
            case 'condition': return 'condition';
            case 'trigger': return 'trigger';
            default: return 'action';
        }
    };

    const TERMINAL_STATUSES = new Set([
        'completed', 'success', 'succeeded', 'failed', 'error', 'cancelled', 'canceled'
    ]);

    const pollExecutionStatus = (executionId: string, attempt = 0) => {
        if (attempt > 20) return;
        const token = localStorage.getItem('auth_token');
        fetch(`/api/workflow-templates/executions/${encodeURIComponent(executionId)}/status`, {
            headers: { ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
        })
            .then(r => (r.ok ? r.json() : null))
            .then(d => {
                if (!d || !d.status) return;
                setLastRun(prev =>
                    prev && prev.id === executionId ? { ...prev, status: d.status } : prev
                );
                if (!TERMINAL_STATUSES.has(String(d.status).toLowerCase())) {
                    setTimeout(() => pollExecutionStatus(executionId, attempt + 1), 3000);
                }
            })
            .catch(() => {});
    };

    const fetchRunResults = (executionId: string) => {
        const token = localStorage.getItem('auth_token');
        fetch(`/api/workflow-templates/executions/${encodeURIComponent(executionId)}/results`, {
            headers: { ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
        })
            .then(r => (r.ok ? r.json() : null))
            .then(d => {
                if (!d) return;
                setRunResults({ steps: d.steps || [], outputs: d.outputs || null });
                if (d.error) {
                    setLastRun(prev => (prev && prev.id === executionId ? { ...prev, status: 'failed' } : prev));
                }
            })
            .catch(() => {});
    };

    const toggleResultsPanel = () => {
        if (!lastRun) return;
        const next = !resultsOpen;
        setResultsOpen(next);
        if (next && runResults === null) {
            fetchRunResults(lastRun.id);
        }
    };

    const openRunDialog = () => {
        setParamValues(
            Object.fromEntries(
                templateInputs.map(i => [i.name, i.default_value != null ? String(i.default_value) : ''])
            )
        );
        setRunOpen(true);
    };

    const handleRunSubmit = async () => {
        const missing = templateInputs.filter(
            i => i.required && !(paramValues[i.name] ?? '').toString().trim()
                && (i.default_value == null || i.default_value === '')
        );
        if (missing.length > 0) {
            toast({
                title: 'Missing required inputs',
                description: `Please provide: ${missing.map(i => i.label || i.name).join(', ')}`,
                variant: 'error'
            });
            return;
        }

        setIsRunning(true);
        try {
            const token = localStorage.getItem('auth_token');
            const res = await fetch(`/api/workflow-templates/${id}/execute`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(paramValues)
            });
            const data = await res.json().catch(() => null);

            if (!res.ok) {
                throw new Error(data?.detail || data?.message || `Execution failed (${res.status})`);
            }

            toast({
                title: 'Workflow started',
                description: data?.execution_id
                    ? `Execution ${data.execution_id} is running. Approval gates will pause for your OK.`
                    : 'Execution started.'
            });
            if (data?.execution_id) {
                setLastRun({ id: data.execution_id, status: null });
                pollExecutionStatus(data.execution_id);
            }
            setRunOpen(false);
        } catch (error) {
            console.error(error);
            toast({
                title: 'Error',
                description: error instanceof Error ? error.message : 'Failed to execute workflow',
                variant: 'error'
            });
        } finally {
            setIsRunning(false);
        }
    };

    if (isLoading) return (
        <div className="flex h-screen items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
        </div>
    );

    const showChecklist =
        !checklistDismissed &&
        (requiredInputs.length > 0 || missingDeps.length > 0);

    return (
        <div className="h-[calc(100vh-64px)] w-full bg-gray-50 dark:bg-gray-800">
            {showChecklist && (
                <div
                  data-testid="first-run-checklist"
                  className="flex flex-col gap-2 border-b border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900/50 dark:bg-amber-950/30 sm:flex-row sm:items-center sm:justify-between"
                >
                    <div className="text-amber-900 dark:text-amber-200">
                        <span className="font-medium">Before first run:</span>{' '}
                        {requiredInputs.length > 0 && (
                            <span>
                                set {requiredInputs.length} required input
                                {requiredInputs.length > 1 ? 's' : ''}
                                {' '}({requiredInputs.join(', ')})
                            </span>
                        )}
                        {requiredInputs.length > 0 && missingDeps.length > 0 && ' · '}
                        {missingDeps.length > 0 && (
                            <span>connect {missingDeps.join(', ')}</span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {connectUrls.map(url => (
                            <a
                              key={url}
                              href={url}
                              className="rounded-md bg-amber-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-900 dark:bg-amber-700 dark:hover:bg-amber-600"
                            >
                                Connect {decodeURIComponent(url.split('connect=')[1] || '')}
                            </a>
                        ))}
                        <button
                          onClick={() => setChecklistDismissed(true)}
                          className="text-xs font-medium text-amber-700 underline hover:text-amber-900 dark:text-amber-300"
                        >
                            Dismiss
                        </button>
                    </div>
                </div>
            )}
            <WorkflowBuilder
                initialData={initialData}
                onSave={handleSave}
                workflowId={id as string}
                onRun={openRunDialog}
            />

            <Dialog open={runOpen} onOpenChange={setRunOpen}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Run &quot;{templateName}&quot;</DialogTitle>
                        <DialogDescription>
                            Provide values for this run. Approval gates still pause
                            for your OK before anything sends.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-2">
                        {templateInputs.length === 0 && (
                            <p className="text-sm text-muted-foreground">
                                This workflow has no inputs — run as-is.
                            </p>
                        )}
                        {templateInputs.map(input => (
                            <div key={input.name} className="space-y-1.5">
                                <label className="text-sm font-medium" htmlFor={`param-${input.name}`}>
                                    {input.label || input.name}
                                    {input.required && <span className="text-red-500 ml-1">*</span>}
                                </label>
                                {input.description && (
                                    <p className="text-xs text-muted-foreground">{input.description}</p>
                                )}
                                {input.options && input.options.length > 0 ? (
                                    <select
                                        id={`param-${input.name}`}
                                        className="w-full h-9 rounded-md border bg-transparent px-3 text-sm"
                                        value={paramValues[input.name] ?? ''}
                                        onChange={(e) => setParamValues(v => ({ ...v, [input.name]: e.target.value }))}
                                    >
                                        <option value="">Select…</option>
                                        {input.options.map((opt: string) => (
                                            <option key={opt} value={opt}>{opt}</option>
                                        ))}
                                    </select>
                                ) : (
                                    <Input
                                        id={`param-${input.name}`}
                                        type={input.type === 'number' ? 'number' : 'text'}
                                        value={paramValues[input.name] ?? ''}
                                        onChange={(e) => setParamValues(v => ({ ...v, [input.name]: e.target.value }))}
                                    />
                                )}
                            </div>
                        ))}
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRunOpen(false)}>Cancel</Button>
                        <Button onClick={handleRunSubmit} disabled={isRunning}>
                            {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                            {isRunning ? 'Starting…' : 'Run workflow'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {lastRun && (
                <div
                  data-testid="execution-status-chip"
                  className="fixed bottom-4 right-4 z-50 rounded-lg border bg-white px-3 py-2 text-xs shadow-md dark:bg-gray-900 dark:border-gray-700"
                >
                    <button
                      onClick={toggleResultsPanel}
                      className="flex items-center gap-2"
                      title="Toggle step results"
                    >
                        <span className="text-muted-foreground">Last run </span>
                        <span className="font-mono">{lastRun.id.slice(0, 12)}…</span>{' '}
                        <span
                          className={
                            lastRun.status == null
                                ? 'font-medium text-blue-600 dark:text-blue-400'
                                : ['completed', 'success', 'succeeded'].includes(lastRun.status.toLowerCase())
                                  ? 'font-medium text-green-600 dark:text-green-400'
                                  : ['failed', 'error', 'cancelled', 'canceled'].includes(lastRun.status.toLowerCase())
                                    ? 'font-medium text-red-600 dark:text-red-400'
                                    : 'font-medium text-amber-600 dark:text-amber-400'
                          }
                        >
                            {lastRun.status ?? 'starting…'}
                        </span>
                    </button>

                    {resultsOpen && (
                        <div
                          data-testid="execution-results-panel"
                          className="mt-2 max-h-72 w-72 overflow-y-auto border-t pt-2 dark:border-gray-700"
                        >
                            {runResults === null && (
                                <p className="text-muted-foreground">Loading results…</p>
                            )}
                            {runResults && runResults.steps.length === 0 && (
                                <p className="text-muted-foreground">No step history recorded.</p>
                            )}
                            {runResults?.steps.map((step, idx) => (
                                <div key={`${step.step_id}-${idx}`} className="mb-1.5 flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="truncate font-mono">{step.step_id || `step-${idx}`}</div>
                                        {step.notes && (
                                            <div className="truncate text-[11px] text-muted-foreground">{step.notes}</div>
                                        )}
                                    </div>
                                    <span
                                      className={
                                        step.status === 'completed' || step.status === 'success'
                                            ? 'font-medium text-green-600 dark:text-green-400'
                                            : step.status === 'failed' || step.status === 'error'
                                              ? 'font-medium text-red-600 dark:text-red-400'
                                              : 'font-medium text-amber-600 dark:text-amber-400'
                                      }
                                    >
                                        {step.status ?? 'unknown'}
                                    </span>
                                </div>
                            ))}
                            {runResults && !runResults.steps.some(s => s.status === 'failed') && runResults.error && (
                                <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">
                                    Error: {runResults.error}
                                </p>
                            )}
                            {runResults?.outputs && (
                                <pre className="mt-2 max-h-32 overflow-auto rounded bg-muted p-2 text-[10px] leading-tight">
                                    {JSON.stringify(runResults.outputs, null, 2).slice(0, 2000)}
                                </pre>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
