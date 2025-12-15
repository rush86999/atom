import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Play, GitBranch, Zap, Settings, PauseCircle, Code, MessageSquare } from 'lucide-react';

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
    return (
        <Card className="min-w-[200px] border-l-4 border-l-green-500 shadow-sm">
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
                    {data.waitForInput && <PauseCircle className="w-4 h-4 text-amber-500" title="Waits for Input" />}
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

export const nodeTypes = {
    trigger: TriggerNode,
    action: ActionNode,
    condition: ConditionNode,
    ai_node: AINode,
};
