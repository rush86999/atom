import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Play, GitBranch, Zap, Settings, PauseCircle, Code, MessageSquare, Mail, Globe, Clock } from 'lucide-react';

export const TriggerNode = memo(({ data, isConnectable }: any) => {
    return (
        <Card className="min-w-[250px] border-l-4 border-l-blue-500 shadow-md">
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
    };
    const branding = serviceBranding[data.service] || { color: 'border-l-green-500', bgColor: '' };

    return (
        <Card className={`min-w-[200px] border-l-4 ${branding.color} ${branding.bgColor} shadow-sm`}>
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
                    {data.waitForInput && <PauseCircle className="w-4 h-4 text-amber-500" />}
                </div>
            </CardHeader>
            <CardContent className="p-3 text-xs">
                <p>{data.action || 'Execute'}</p>
                {/* Show Required Inputs if Paused */}
                {data.waitForInput && data.requiredInputs && (
                    <div className="mt-2 text-[10px] bg-amber-50 text-amber-800 p-1 rounded border border-amber-200">
                        <strong>Waiting for:</strong> {data.requiredInputs.join(', ')}
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

export const nodeTypes = {
    trigger: TriggerNode,
    action: ActionNode,
    condition: ConditionNode,
    ai_node: AINode,
    desktop: DesktopNode,
    email: EmailNode,
    http: HttpNode,
    timer: TimerNode,
};
