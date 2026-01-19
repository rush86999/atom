import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Play, GitBranch, Zap, Settings, PauseCircle, Code, MessageSquare, Mail, Globe, Clock, Activity, CheckCircle2, XCircle } from 'lucide-react';

// Helper for Performance Mode Overlay
const PerformanceBadge = ({ analytics }: { analytics: { duration: number; status: string; error?: string } }) => {
    if (!analytics) return null;
    const isSuccess = analytics.status === 'COMPLETED' || analytics.status === 'success';
    const colorClass = isSuccess ? 'bg-green-100 text-green-700 border-green-200' : 'bg-red-100 text-red-700 border-red-200';
    const Icon = isSuccess ? CheckCircle2 : XCircle;

    return (
        <div className={`absolute -top-3 right-2 z-50 flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-bold shadow-sm ${colorClass}`}>
            <Icon className="w-3 h-3" />
            <span>{analytics.duration?.toFixed(0)}ms</span>
        </div>
    );
};

export const TriggerNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[250px] border-l-4 border-l-blue-500 shadow-md relative overflow-visible">
            {data._analytics && <PerformanceBadge analytics={data._analytics} />}
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <Zap className="w-4 h-4 text-blue-500 fill-blue-100" />
                    <CardTitle className="text-sm font-bold">Trigger</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs text-gray-500">
                <div className="space-y-1">
                    <p className="font-semibold text-black">{data.label || 'Webhook'}</p>
                    {data.integration && <Badge variant="secondary">{data.integration}</Badge>}
                    {data.schema && (
                        <div className="mt-2 text-[10px] bg-gray-50 p-1 rounded border">
                            <strong>Input Schema:</strong>
                            <pre>{JSON.stringify(data.schema, null, 2)}</pre>
                        </div>
                    )}
                </div>
                <Handle
                    type="source"
                    position={Position.Bottom}
                    isConnectable={isConnectable}
                    className="w-3 h-3 bg-blue-500"
                />
            </CardContent>
        </Card>
    );
});

export const ActionNode = memo(({ data, isConnectable }: any) => {
    const [testStatus, setTestStatus] = React.useState<'idle' | 'testing' | 'success' | 'error'>('idle');
    const [testDuration, setTestDuration] = React.useState<number | null>(null);
    const [isConnected, setIsConnected] = React.useState<boolean | null>(null);
    const [showRetryConfig, setShowRetryConfig] = React.useState(false);

    // Auto-retry configuration
    const retryConfig = data.retryConfig || {
        enabled: false,
        maxRetries: 3,
        retryDelayMs: 1000,
        exponentialBackoff: true,
    };

    // Check connection status on mount
    React.useEffect(() => {
        if (data.serviceId || data.service) {
            const serviceId = (data.serviceId || data.service || '').toLowerCase().replace(/\s+/g, '');
            fetch(`/api/integrations/${serviceId}/health`)
                .then(res => setIsConnected(res.ok))
                .catch(() => setIsConnected(false));
        }
    }, [data.serviceId, data.service]);

    // Test this step
    const handleTestStep = async () => {
        setTestStatus('testing');
        try {
            const res = await fetch('/api/workflows/test-step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    service: data.serviceId || data.service || 'System',
                    action: data.action || 'execute',
                    parameters: Array.isArray(data.parameters) ? {} : (data.parameters || {}),
                    workflow_id: data._workflowId,
                    step_id: data.id, // 'data.id' might not exist, usually it's passed as prop 'id' to the node component
                }),
            });

            const result = await res.json();

            if (res.ok && result?.duration_ms !== undefined) {
                setTestDuration(result.duration_ms);
            }

            setTestStatus(res.ok ? 'success' : 'error');
            // Reset after 3 seconds
            setTimeout(() => setTestStatus('idle'), 3000);
        } catch {
            setTestStatus('error');
            setTimeout(() => setTestStatus('idle'), 3000);
        }
    };

    // Service branding map
    const serviceBranding: Record<string, { color: string; bgColor: string; icon?: React.ReactNode }> = {
        'Slack': { color: 'border-l-[#4A154B]', bgColor: 'bg-purple-50' },
        'Gmail': { color: 'border-l-red-500', bgColor: 'bg-red-50' },
        'Google Drive': { color: 'border-l-yellow-500', bgColor: 'bg-yellow-50' },
        'GitHub': { color: 'border-l-gray-800', bgColor: 'bg-gray-50' },
        'Notion': { color: 'border-l-black', bgColor: 'bg-gray-50' },
        'Asana': { color: 'border-l-pink-500', bgColor: 'bg-pink-50' },
        'Trello': { color: 'border-l-blue-500', bgColor: 'bg-blue-50' },
        'HubSpot': { color: 'border-l-orange-500', bgColor: 'bg-orange-50' },
        'Salesforce': { color: 'border-l-blue-600', bgColor: 'bg-blue-50' },
        'Discord': { color: 'border-l-indigo-500', bgColor: 'bg-indigo-50' },
        'Stripe': { color: 'border-l-purple-500', bgColor: 'bg-purple-50' },
        'Jira': { color: 'border-l-blue-700', bgColor: 'bg-blue-50' },
        'Zendesk': { color: 'border-l-green-800', bgColor: 'bg-green-50' },
        'Figma': { color: 'border-l-purple-500', bgColor: 'bg-purple-50' },
        'Twilio': { color: 'border-l-red-600', bgColor: 'bg-red-50' },
        'OpenAI': { color: 'border-l-[#412991]', bgColor: 'bg-purple-50' },
        'Google Gemini': { color: 'border-l-[#8E75B2]', bgColor: 'bg-purple-50' },
    };
    const branding = serviceBranding[data.service] || { color: 'border-l-green-500', bgColor: '' };

    return (
        <Card className={`min-w-[220px] border-l-4 ${branding.color} ${branding.bgColor} shadow-sm relative overflow-visible`}>
            {data._analytics && <PerformanceBadge analytics={data._analytics} />}
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center justify-between space-x-2">
                    <div className="flex items-center space-x-2">
                        <Play className="w-4 h-4 text-green-500" />
                        <CardTitle className="text-sm font-bold">{data.service || 'Action'}</CardTitle>
                    </div>
                    {/* Connection Status Indicator */}
                    {isConnected !== null && (
                        isConnected ? (
                            <div className="flex items-center space-x-1">
                                <div className="w-2 h-2 bg-green-500 rounded-full" />
                            </div>
                        ) : (
                            <button
                                onClick={() => window.open(`/integrations/${(data.serviceId || data.service || '').toLowerCase().replace(/\s+/g, '')}`, '_blank')}
                                className="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-200 flex items-center gap-0.5"
                            >
                                Connect
                            </button>
                        )
                    )}
                    {data.waitForInput && <PauseCircle className="w-4 h-4 text-amber-500" />}
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <p className="font-medium text-gray-700">{data.action || data.label || 'Execute'}</p>
                {data.description && (
                    <p className="text-[10px] text-gray-500 mt-1 truncate">{data.description}</p>
                )}

                {/* Show Required Inputs if Paused */}
                {data.waitForInput && data.requiredInputs && (
                    <div className="mt-2 text-[10px] bg-amber-50 text-amber-800 p-1 rounded border border-amber-200">
                        <strong>Waiting for:</strong> {data.requiredInputs.join(', ')}
                    </div>
                )}

                {/* Test Step Button */}
                <div className="mt-2 flex items-center justify-between">
                    <button
                        onClick={handleTestStep}
                        disabled={testStatus === 'testing'}
                        className={`
                            flex items-center gap-1 text-[10px] px-2 py-1 rounded transition-colors
                            ${testStatus === 'success'
                                ? 'bg-green-100 text-green-700'
                                : testStatus === 'error'
                                    ? 'bg-red-100 text-red-700'
                                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'}
                        `}
                    >
                        {testStatus === 'testing' ? (
                            <>
                                <div className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                                Testing...
                            </>
                        ) : testStatus === 'success' ? (
                            <>
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                Success {testDuration !== null ? `(${testDuration}ms)` : ''}
                            </>
                        ) : testStatus === 'error' ? (
                            <>
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                Failed
                            </>
                        ) : (
                            <>
                                <Play className="w-3 h-3" />
                                Test Step
                            </>
                        )}
                    </button>
                </div>

                {/* Auto-Retry Configuration */}
                {retryConfig.enabled && (
                    <div className="mt-2 text-[10px] bg-blue-50 text-blue-800 p-1 rounded border border-blue-200">
                        <div className="flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.582m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            <span>Auto-retry: {retryConfig.maxRetries}x</span>
                            {retryConfig.exponentialBackoff && <span>(exponential)</span>}
                        </div>
                    </div>
                )}

                {/* Retry Config Toggle */}
                <button
                    onClick={() => setShowRetryConfig(!showRetryConfig)}
                    className="mt-1 text-[9px] text-gray-400 hover:text-gray-600 flex items-center gap-1"
                >
                    <Settings className="w-2 h-2" />
                    {showRetryConfig ? 'Hide retry config' : 'Configure retries'}
                </button>

                {showRetryConfig && (
                    <div className="mt-1 p-2 bg-gray-50 rounded text-[10px] space-y-1">
                        <div className="flex items-center justify-between">
                            <span>Max retries:</span>
                            <span className="font-medium">{retryConfig.maxRetries}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span>Delay:</span>
                            <span className="font-medium">{retryConfig.retryDelayMs}ms</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span>Exponential:</span>
                            <span className="font-medium">{retryConfig.exponentialBackoff ? 'Yes' : 'No'}</span>
                        </div>
                    </div>
                )}
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-green-500"
            />
        </Card>
    );
});

export const ConditionNode = memo(({ data, isConnectable }: any) => {
    const type = data.conditionType || 'expression'; // 'expression' | 'llm' | 'code'

    return (
        <Card className="min-w-[200px] border-l-4 border-l-orange-500 shadow-sm">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                        <GitBranch className="w-4 h-4 text-orange-500" />
                        <CardTitle className="text-sm font-bold">Condition</CardTitle>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                {/* Type Indicator */}
                <div className="mb-2 flex space-x-1">
                    {type === 'llm' && <Badge variant="secondary" className="text-[10px] h-5 px-1"><MessageSquare className="w-3 h-3 mr-1" />LLM</Badge>}
                    {type === 'code' && <Badge variant="secondary" className="text-[10px] h-5 px-1"><Code className="w-3 h-3 mr-1" />Code</Badge>}
                    {type === 'visual' && <Badge variant="outline" className="text-[10px] h-5 px-1 bg-green-50">Builder</Badge>}
                </div>

                {type === 'code' ? (
                    <div className="relative group">
                        <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="flex items-center text-[8px] bg-blue-600 text-white px-1 rounded shadow-sm hover:bg-blue-700">
                                <Zap className="w-2 h-2 mr-1" /> AI Gen
                            </button>
                        </div>
                        <pre className="bg-slate-900 text-slate-50 p-2 rounded text-[10px] font-mono overflow-x-auto min-h-[40px]">
                            {data.code || '// Write code here...\nreturn true;'}
                        </pre>
                    </div>
                ) : type === 'llm' ? (
                    <div className="bg-purple-50 border border-purple-100 p-2 rounded text-purple-900 text-[10px]">
                        <span className="font-bold">Prompt:</span> {data.prompt || 'Is sentiment positive?'}
                    </div>
                ) : type === 'visual' ? (
                    <div className="bg-gray-50 p-2 rounded border space-y-1">
                        <div className="flex items-center space-x-1">
                            <span className="font-semibold text-blue-600 bg-blue-50 px-1 rounded">{data.field || 'Field'}</span>
                            <span className="font-bold text-gray-500">{data.operator || '=='}</span>
                            <span className="font-semibold text-green-600 bg-green-50 px-1 rounded">{data.value || 'Value'}</span>
                        </div>
                    </div>
                ) : (
                    <p className="italic mb-2 bg-gray-50 p-1 rounded border">{data.condition || 'If x > y'}</p>
                )}

                <div className="flex justify-between w-full mt-2 relative h-4">
                    <div className="absolute left-2 text-green-600 font-bold text-[10px]">TRUE</div>
                    <div className="absolute right-2 text-red-600 font-bold text-[10px]">FALSE</div>
                </div>
            </CardContent>
            {/* Two Source Handles for Branching */}
            <Handle
                type="source"
                position={Position.Bottom}
                id="true"
                style={{ left: '25%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-green-500"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="false"
                style={{ left: '75%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-red-500"
            />
        </Card>
    );
});

export const AINode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-purple-600 shadow-md bg-purple-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-purple-600 p-1 rounded-full">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /></svg>
                    </div>
                    <CardTitle className="text-sm font-bold text-purple-900">AI Processing</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="mb-2">
                    <span className="font-semibold text-purple-800">Model:</span> {data.model || 'GPT-4'}
                </div>
                <div className="bg-white p-2 rounded border border-purple-200 text-gray-600 italic truncate">
                    {data.prompt || 'Summarize input...'}
                </div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-purple-600"
            />
        </Card>
    );
});

export const DesktopNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[200px] border-l-4 border-l-cyan-500 shadow-md">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-cyan-100 p-1 rounded-full">
                        <Settings className="w-4 h-4 text-cyan-600" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Desktop Action</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="font-semibold">{data.app || 'Application'}</div>
                <div className="text-gray-500">{data.action || 'Open'}</div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-cyan-500"
            />
        </Card>
    );
});

// Email Node - for sending emails
export const EmailNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[200px] border-l-4 border-l-red-500 shadow-md bg-red-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-red-100 p-1 rounded-full">
                        <Mail className="w-4 h-4 text-red-600" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Send Email</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="font-semibold text-gray-700">To: {data.recipient || 'recipient@email.com'}</div>
                <div className="text-gray-500 truncate">Subject: {data.subject || 'Email Subject'}</div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-red-500"
            />
        </Card>
    );
});

// HTTP Request Node - for making API calls
export const HttpNode = memo(({ data, isConnectable }: any) => {
    const methodColors: Record<string, string> = {
        'GET': 'bg-green-100 text-green-700',
        'POST': 'bg-blue-100 text-blue-700',
        'PUT': 'bg-yellow-100 text-yellow-700',
        'DELETE': 'bg-red-100 text-red-700',
        'PATCH': 'bg-purple-100 text-purple-700',
    };
    const method = data.method || 'GET';
    const methodClass = methodColors[method] || 'bg-gray-100 text-gray-700';

    return (
        <Card className="min-w-[220px] border-l-4 border-l-orange-500 shadow-md">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-orange-100 p-1 rounded-full">
                        <Globe className="w-4 h-4 text-orange-600" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">HTTP Request</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="flex items-center space-x-2 mb-1">
                    <Badge className={`text-[10px] ${methodClass}`}>{method}</Badge>
                </div>
                <div className="text-gray-600 truncate font-mono text-[10px]">
                    {data.url || 'https://api.example.com/endpoint'}
                </div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-orange-500"
            />
        </Card>
    );
});

// Timer/Delay Node - for adding delays in workflow
export const TimerNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[180px] border-l-4 border-l-indigo-500 shadow-md bg-indigo-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-indigo-100 p-1 rounded-full">
                        <Clock className="w-4 h-4 text-indigo-600" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Delay</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="flex items-center space-x-1">
                    <span className="text-2xl font-bold text-indigo-700">{data.duration || '5'}</span>
                    <span className="text-gray-500">{data.unit || 'minutes'}</span>
                </div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-indigo-500"
            />
        </Card>
    );
});

// Loop Node - for iterating over arrays (Activepieces-style)
export const LoopNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-teal-500 shadow-md bg-teal-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-teal-100 p-1 rounded-full">
                        <svg className="w-4 h-4 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Loop</CardTitle>
                    <Badge variant="secondary" className="text-[9px]">For Each</Badge>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="bg-white p-2 rounded border border-teal-200">
                    <p className="text-gray-600">
                        <span className="font-semibold text-teal-700">Iterate over:</span>{' '}
                        <span className="font-mono text-[10px] bg-gray-100 px-1 rounded">
                            {data.iterateOver || '{{previousStep.items}}'}
                        </span>
                    </p>
                    {data.maxIterations && (
                        <p className="text-[10px] text-gray-500 mt-1">
                            Max: {data.maxIterations} iterations
                        </p>
                    )}
                </div>
            </CardContent>
            {/* Two outputs: Loop Body and After Loop */}
            <div className="flex justify-between px-3 pb-1">
                <div className="text-[9px] text-teal-600 font-semibold">Body</div>
                <div className="text-[9px] text-gray-500 font-semibold">Done</div>
            </div>
            <Handle
                type="source"
                position={Position.Bottom}
                id="loop_body"
                style={{ left: '25%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-teal-500"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="loop_done"
                style={{ left: '75%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
        </Card>
    );
});

// Approval Node - Human-in-the-loop (Activepieces-style)
export const ApprovalNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-amber-500 shadow-md bg-amber-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-amber-100 p-1 rounded-full">
                        <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Wait for Approval</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="bg-white p-2 rounded border border-amber-200 space-y-1">
                    <p className="text-gray-700 font-medium">
                        {data.message || 'Waiting for human approval'}
                    </p>
                    {data.timeout && (
                        <p className="text-[10px] text-gray-500">
                            Timeout: {data.timeout}
                        </p>
                    )}
                    {data.approvers && (
                        <p className="text-[10px] text-gray-500">
                            Approvers: {data.approvers}
                        </p>
                    )}
                </div>
                <div className="mt-2 flex items-center gap-1 text-[10px] text-amber-700">
                    <PauseCircle className="w-3 h-3" />
                    <span>Workflow pauses until approved</span>
                </div>
            </CardContent>
            {/* Two outputs: Approved and Rejected */}
            <div className="flex justify-between px-3 pb-1">
                <div className="text-[9px] text-green-600 font-semibold">Approved</div>
                <div className="text-[9px] text-red-600 font-semibold">Rejected</div>
            </div>
            <Handle
                type="source"
                position={Position.Bottom}
                id="approved"
                style={{ left: '25%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-green-500"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="rejected"
                style={{ left: '75%' }}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-red-500"
            />
        </Card>
    );
});

// Code Node - Custom JavaScript/TypeScript (Activepieces-style)
export const CodeNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[240px] border-l-4 border-l-slate-700 shadow-md bg-slate-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                        <div className="bg-slate-700 p-1 rounded">
                            <Code className="w-4 h-4 text-white" />
                        </div>
                        <CardTitle className="text-sm font-bold text-gray-800">Code</CardTitle>
                    </div>
                    <Badge variant="secondary" className="text-[9px] bg-blue-100 text-blue-700">
                        {data.language || 'TypeScript'}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="bg-slate-900 text-slate-50 p-2 rounded text-[10px] font-mono overflow-x-auto min-h-[60px] max-h-[80px]">
                    <pre className="whitespace-pre-wrap">
                        {data.code || `// Write your code here
export const code = async (inputs) => {
  return { result: inputs.data };
};`}
                    </pre>
                </div>
                {data.npmPackages && data.npmPackages.length > 0 && (
                    <div className="mt-2 text-[9px] text-gray-500">
                        <span className="font-semibold">npm:</span> {data.npmPackages.join(', ')}
                    </div>
                )}
                {/* ASK AI button */}
                <button className="mt-2 w-full flex items-center justify-center gap-1 text-[10px] bg-purple-100 text-purple-700 py-1 rounded hover:bg-purple-200 transition-colors">
                    <Zap className="w-3 h-3" />
                    Ask AI to write code
                </button>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-slate-700"
            />
        </Card>
    );
});

// Table Node - for database operations (Activepieces-style)
export const TableNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-teal-600 shadow-md bg-teal-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-teal-600 p-1 rounded">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                        </svg>
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Tables</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="bg-white p-2 rounded border border-teal-200">
                    <p className="font-semibold text-teal-700">{data.action || 'Insert Row'}</p>
                    <p className="text-gray-600 text-[10px] mt-1">
                        Table: <span className="font-mono bg-gray-100 px-1 rounded">{data.tableName || 'Select table'}</span>
                    </p>
                </div>
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-teal-600"
            />
        </Card>
    );
});

// SubFlow Node - for calling other flows (Activepieces-style)
export const SubFlowNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-violet-600 shadow-md bg-violet-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-violet-600 p-1 rounded">
                        <Zap className="w-4 h-4 text-white" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Sub Flow</CardTitle>
                    <Badge variant="secondary" className="text-[9px]">{data.async ? 'Async' : 'Sync'}</Badge>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <div className="bg-white p-2 rounded border border-violet-200">
                    <p className="font-semibold text-violet-700">{data.flowName || 'Select flow'}</p>
                    {data.description && (
                        <p className="text-gray-600 text-[10px] mt-1">{data.description}</p>
                    )}
                </div>
                {data.async && (
                    <p className="text-violet-600 text-[10px] mt-2 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Fire and forget
                    </p>
                )}
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-violet-600"
            />
        </Card>
    );
});


// Human-in-the-Loop Form Input Node
export const FormInputNode = memo(({ data, isConnectable }: any) => {
    const fields = data.fields || [
        { name: 'input1', type: 'text', label: 'Input 1' }
    ];

    return (
        <Card className="min-w-[240px] border-l-4 border-l-pink-500 shadow-md bg-pink-50">
            <Handle
                type="target"
                position={Position.Top}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-gray-400"
            />
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-pink-500 p-1 rounded">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Form Input</CardTitle>
                    <Badge variant="secondary" className="text-[9px] bg-pink-100">HITL</Badge>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <p className="text-gray-600 mb-2">{data.description || 'Collect user input via form'}</p>

                {/* Form Fields Preview */}
                <div className="space-y-1 bg-white p-2 rounded border border-pink-200">
                    {fields.slice(0, 3).map((field: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-2 text-[10px]">
                            <span className="text-gray-500">{field.type}:</span>
                            <span className="font-medium">{field.label || field.name}</span>
                            {field.required && <span className="text-red-500">*</span>}
                        </div>
                    ))}
                    {fields.length > 3 && (
                        <p className="text-[9px] text-gray-400">+{fields.length - 3} more fields</p>
                    )}
                </div>

                {/* Assignee */}
                {data.assignTo && (
                    <div className="mt-2 text-[10px] text-pink-700 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        Assigned to: {data.assignTo}
                    </div>
                )}

                {/* Timeout */}
                {data.timeoutHours && (
                    <div className="mt-1 text-[10px] text-gray-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Timeout: {data.timeoutHours}h
                    </div>
                )}
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-pink-500"
            />
        </Card>
    );
});

// Table Trigger Node - triggers workflow on table row changes
export const TableTriggerNode = memo(({ data, isConnectable }: any) => {
    const eventType = data.eventType || 'row_created'; // row_created, row_updated, row_deleted

    const eventConfig: Record<string, { label: string; color: string }> = {
        row_created: { label: 'Row Created', color: 'bg-green-500' },
        row_updated: { label: 'Row Updated', color: 'bg-blue-500' },
        row_deleted: { label: 'Row Deleted', color: 'bg-red-500' },
        any_change: { label: 'Any Change', color: 'bg-purple-500' },
    };

    const config = eventConfig[eventType] || eventConfig.row_created;

    return (
        <Card className="min-w-[220px] border-l-4 border-l-teal-500 shadow-md">
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-teal-500 p-1 rounded">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                    </div>
                    <CardTitle className="text-sm font-bold">Table Trigger</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                {/* Table Name */}
                <div className="bg-teal-50 p-2 rounded border border-teal-200 mb-2">
                    <p className="font-semibold text-teal-700">{data.tableName || 'Select table'}</p>
                </div>

                {/* Event Type */}
                <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${config.color}`}></span>
                    <span className="font-medium">{config.label}</span>
                </div>

                {/* Filters */}
                {data.filters && data.filters.length > 0 && (
                    <div className="mt-2 text-[10px] text-gray-600">
                        <span className="font-medium">Filters:</span> {data.filters.length} condition(s)
                    </div>
                )}
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-teal-500"
            />
        </Card>
    );
});

// Chat Interface Trigger Node - starts workflows from chat messages
export const ChatTriggerNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[220px] border-l-4 border-l-indigo-500 shadow-md bg-indigo-50">
            <CardHeader className="p-3 pb-0">
                <div className="flex items-center space-x-2">
                    <div className="bg-indigo-500 p-1 rounded">
                        <MessageSquare className="w-4 h-4 text-white" />
                    </div>
                    <CardTitle className="text-sm font-bold text-gray-800">Chat Trigger</CardTitle>
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                {/* Trigger Keywords */}
                <div className="bg-white p-2 rounded border border-indigo-200 mb-2">
                    <p className="font-semibold text-indigo-700 mb-1">Trigger on:</p>
                    {data.keywords && data.keywords.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                            {data.keywords.slice(0, 3).map((kw: string, idx: number) => (
                                <Badge key={idx} variant="secondary" className="text-[9px]">{kw}</Badge>
                            ))}
                            {data.keywords.length > 3 && (
                                <span className="text-[9px] text-gray-400">+{data.keywords.length - 3}</span>
                            )}
                        </div>
                    ) : (
                        <p className="text-gray-400 italic">Any message</p>
                    )}
                </div>

                {/* Channel */}
                {data.channel && (
                    <div className="text-[10px] text-indigo-700 flex items-center gap-1 mb-1">
                        <span className="font-medium">Channel:</span> {data.channel}
                    </div>
                )}

                {/* User Filter */}
                {data.userFilter && (
                    <div className="text-[10px] text-gray-600 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        {data.userFilter}
                    </div>
                )}
            </CardContent>
            <Handle
                type="source"
                position={Position.Bottom}
                isConnectable={isConnectable}
                className="w-3 h-3 bg-indigo-500"
            />
        </Card>
    );
});

// Export nodeTypes object - must be after all component definitions
export const nodeTypes = {
    trigger: TriggerNode,
    action: ActionNode,
    condition: ConditionNode,
    ai_node: AINode,
    desktop: DesktopNode,
    email: EmailNode,
    http: HttpNode,
    timer: TimerNode,
    loop: LoopNode,
    approval: ApprovalNode,
    code: CodeNode,
    table: TableNode,
    subflow: SubFlowNode,
    form_input: FormInputNode,
    table_trigger: TableTriggerNode,
    chat_trigger: ChatTriggerNode,
};

