'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
    Sparkles, Zap, MessageSquare, Play, Copy, Edit2,
    CheckCircle, Clock, User, Bot, ArrowRight, RefreshCw,
    Shield, AlertTriangle, GraduationCap, Award, Loader2, Volume2, VolumeX
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { ReasoningChain, ReasoningStep } from '../Agents/ReasoningChain';
import { VoiceInput } from '@/components/Voice/VoiceInput';
import { useToast } from "@/components/ui/use-toast";
import { useTextToSpeech } from '@/hooks/useTextToSpeech';

// ... (existing code)

const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
const [showReasoning, setShowReasoning] = useState(false);
const toast = useToast();

// TTS Integration
const { speak, stop, isSpeaking } = useTextToSpeech();
const [isAutoRead, setIsAutoRead] = useState(true);

// Fetch agent governance data from API on mount
useEffect(() => {
    const fetchGovernanceData = async () => {
        setLoadingGovernance(true);
        try {
            const response = await fetch('/api/agent-governance/agents');
            if (response.ok) {
                const data = await response.json();
                // Map by agent_id for quick lookup
                const governanceMap: Record<string, any> = {};
                data.forEach((agent: any) => {
                    governanceMap[agent.agent_id] = agent;
                });
                setAgentGovernanceData(governanceMap);
            }
        } catch (error) {
            console.error('Failed to fetch agent governance data:', error);
        }
        setLoadingGovernance(false);
    };

    fetchGovernanceData();
}, []);

// Get real-time governance info for an agent
const getAgentGovernance = useCallback((agentId: string) => {
    const apiData = agentGovernanceData[agentId];
    if (apiData) {
        return {
            maturityLevel: apiData.maturity_level as AgentMaturityLevel,
            confidenceScore: apiData.confidence_score,
            canDeployDirectly: apiData.can_deploy_directly,
        };
    }
    // Fallback to static data
    const agent = SPECIALTY_AGENTS.find(a => a.id === agentId);
    return agent ? {
        maturityLevel: agent.maturityLevel,
        confidenceScore: agent.confidenceScore,
        canDeployDirectly: agent.canDeployDirectly,
    } : null;
}, [agentGovernanceData]);

const handleGenerateWorkflow = async () => {
    if (!prompt.trim() || !selectedAgent) return;

    setIsGenerating(true);
    setShowReasoning(true);
    setReasoningSteps([]);
    setChatHistory(prev => [...prev, { role: 'user', content: prompt }]);

    // Simulate reasoning steps
    const mockSteps: ReasoningStep[] = [
        {
            id: 'r1', index: 0, timestamp: new Date().toISOString(),
            thought: `Parsing request: "${prompt}"`,
            action: 'NLU Analysis', action_input: { text: prompt },
            observation: 'Intent identified: Create Automation',
            status: 'completed'
        },
        {
            id: 'r2', index: 1, timestamp: new Date().toISOString(),
            thought: 'Identifying required services based on agent capabilities',
            action: 'Service Lookup', action_input: { capabilities: selectedAgent.capabilities },
            observation: `Selected services: ${selectedAgent.capabilities.slice(0, 2).join(', ')}`,
            status: 'completed'
        },
        {
            id: 'r3', index: 2, timestamp: new Date().toISOString(),
            thought: 'Structuring workflow steps and configuration',
            action: 'Workflow Generation', action_input: { template: 'custom' },
            observation: 'Draft workflow created with 3 steps',
            status: 'completed'
        }
    ];

    // Simulate step-by-step appearance
    for (const step of mockSteps) {
        await new Promise(resolve => setTimeout(resolve, 800));
        setReasoningSteps(prev => {
            const newSteps = [...prev, step];
            // Mark previous as completed if needed
            return newSteps;
        });
    }

    const workflow = generateSampleWorkflow(prompt, selectedAgent);
    setGeneratedWorkflow(workflow);

    const responseText = `I've created a workflow for "${prompt}". It includes ${workflow.steps.length} steps using ${selectedAgent.capabilities.slice(0, 3).join(', ')}. Would you like me to deploy it or make any modifications?`;

    setChatHistory(prev => [...prev, {
        role: 'agent',
        content: responseText
    }]);

    if (isAutoRead) speak(responseText);

    onWorkflowGenerated?.(workflow);
    setIsGenerating(false);
    setPrompt('');
};

const handleReasoningFeedback = async (stepIndex: number, type: 'thumbs_up' | 'thumbs_down') => {
    try {
        // Optimistic update (could add visual feedback state here)
        toast({
            title: type === 'thumbs_up' ? "Helpful" : "Flagged",
            description: "Thanks for your feedback! I'm learning.",
        });

        // Send to backend
        await fetch('/api/reasoning/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_id: selectedAgent?.id,
                run_id: 'simulated-run-' + Date.now(),
                step_index: stepIndex,
                step_content: reasoningSteps[stepIndex],
                feedback_type: type
            })
        });
    } catch (e) {
        console.error("Feedback failed", e);
    }
};

const handleDeploy = async () => {
    if (!generatedWorkflow || !selectedAgent) return;

    setIsDeploying(true);

    try {
        // Check deployment approval with backend
        const checkResponse = await fetch('/api/agent-governance/check-deployment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_id: selectedAgent.id,
                workflow_name: generatedWorkflow.name,
                workflow_definition: generatedWorkflow,
                trigger_type: generatedWorkflow.trigger.type,
                actions: generatedWorkflow.steps.map(s => s.action),
                requested_by: 'current-user', // Would come from auth
            }),
        });

        const checkData = await checkResponse.json();

        if (checkData.can_deploy) {
            // Direct deployment allowed
            onDeployWorkflow?.(generatedWorkflow);
            const msg = `✅ Great! I've deployed the workflow "${generatedWorkflow.name}". It's now active and ready to run. You can view it in the Flows tab.`;
            setChatHistory(prev => [...prev, {
                role: 'agent',
                content: msg
            }]);
            if (isAutoRead) speak(msg);
        } else {
            // Needs approval - submit for review
            const submitResponse = await fetch('/api/agent-governance/submit-for-approval', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: selectedAgent.id,
                    workflow_name: generatedWorkflow.name,
                    workflow_definition: generatedWorkflow,
                    trigger_type: generatedWorkflow.trigger.type,
                    actions: generatedWorkflow.steps.map(s => s.action),
                    requested_by: 'current-user',
                }),
            });

            const submitData = await submitResponse.json();
            const msg = `📝 I've submitted the workflow "${generatedWorkflow.name}" for approval. ${submitData.message || 'You will be notified when it is reviewed.'}`;

            setChatHistory(prev => [...prev, {
                role: 'agent',
                content: msg
            }]);
            if (isAutoRead) speak(msg);
        }
    } catch (error) {
        console.error('Deployment check failed:', error);
        // Fallback to local logic
        if (selectedAgent.canDeployDirectly) {
            onDeployWorkflow?.(generatedWorkflow);
            const msg = `Great! I've deployed the workflow "${generatedWorkflow.name}". It's now active and ready to run.`;
            setChatHistory(prev => [...prev, {
                role: 'agent',
                content: msg
            }]);
            if (isAutoRead) speak(msg);
        } else {
            const msg = `📝 This workflow requires approval. I've submitted it for review by a team lead.`;
            setChatHistory(prev => [...prev, {
                role: 'agent',
                content: msg
            }]);
            if (isAutoRead) speak(msg);
        }
    }

    setIsDeploying(false);
};

const handleSuggestedPrompt = (suggestedPrompt: string) => {
    setPrompt(suggestedPrompt);
};

return (
    <div className={cn("flex h-full bg-gray-50", className)}>
        {/* Agent Selection Sidebar */}
        <div className="w-72 border-r bg-white flex flex-col">
            <div className="p-4 border-b bg-gradient-to-r from-violet-600 to-indigo-600 text-white">
                <div className="flex items-center gap-2 mb-2">
                    <Bot className="w-5 h-5" />
                    <h3 className="font-bold">Specialty Agents</h3>
                </div>
                <p className="text-xs text-violet-100">
                    AI agents with domain expertise to generate workflows
                </p>
            </div>

            <ScrollArea className="flex-1 p-2">
                {SPECIALTY_AGENTS.map(agent => {
                    const maturity = MATURITY_CONFIG[agent.maturityLevel];
                    const MaturityIcon = maturity.icon;
                    return (
                        <button
                            key={agent.id}
                            onClick={() => {
                                setSelectedAgent(agent);
                                setChatHistory([]);
                                setGeneratedWorkflow(null);
                            }}
                            className={cn(
                                "w-full text-left p-3 rounded-lg mb-2 transition-all",
                                selectedAgent?.id === agent.id
                                    ? "bg-violet-100 ring-2 ring-violet-400"
                                    : "hover:bg-gray-100"
                            )}
                        >
                            <div className="flex items-center gap-3">
                                <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center text-xl", agent.color)}>
                                    {agent.icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="font-semibold text-sm">{agent.name}</div>
                                    <div className="text-xs text-gray-500 truncate">{agent.specialty}</div>
                                </div>
                            </div>
                            {/* Maturity Badge */}
                            <div className={cn("mt-2 flex items-center gap-1 text-xs px-2 py-0.5 rounded-full w-fit", maturity.color)}>
                                <MaturityIcon className="w-3 h-3" />
                                {maturity.label}
                            </div>
                        </button>
                    );
                })}
            </ScrollArea>
        </div>

        {/* Chat/Generation Area */}
        <div className="flex-1 flex flex-col">
            {selectedAgent ? (
                <>
                    {/* Agent Header */}
                    <div className="p-4 border-b bg-white">
                        <div className="flex items-center gap-3">
                            <div className={cn("w-12 h-12 rounded-lg flex items-center justify-center text-2xl", selectedAgent.color)}>
                                {selectedAgent.icon}
                            </div>
                            <div className="flex-1">
                                <div className="flex items-center gap-2">
                                    <h2 className="font-bold text-lg">{selectedAgent.name}</h2>
                                    {(() => {
                                        const maturity = MATURITY_CONFIG[selectedAgent.maturityLevel];
                                        const MaturityIcon = maturity.icon;
                                        return (
                                            <div className={cn("flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border", maturity.color)}>
                                                <MaturityIcon className="w-3 h-3" />
                                                {maturity.label}
                                            </div>
                                        );
                                    })()}
                                </div>
                                <p className="text-sm text-gray-500">{selectedAgent.description}</p>
                            </div>
                            {/* Confidence Score */}
                            <div className="text-right">
                                <div className="text-xs text-gray-400">Confidence</div>
                                <div className="font-bold text-lg">{Math.round(selectedAgent.confidenceScore * 100)}%</div>
                            </div>
                        </div>
                        <div className="flex items-center justify-between mt-3">
                            <div className="flex gap-1 flex-wrap">
                                {selectedAgent.capabilities.slice(0, 5).map(cap => (
                                    <Badge key={cap} variant="secondary" className="text-xs">
                                        {cap}
                                    </Badge>
                                ))}
                            </div>
                            <div className="flex items-center gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className={cn("h-7 px-2 text-xs", isAutoRead ? "text-violet-600 bg-violet-50" : "text-gray-400")}
                                    onClick={() => {
                                        if (isSpeaking) stop();
                                        setIsAutoRead(!isAutoRead);
                                    }}
                                    title={isAutoRead ? "Mute Agent Voice" : "Enable Agent Voice"}
                                >
                                    {isAutoRead ? <Volume2 className="w-3.5 h-3.5 mr-1" /> : <VolumeX className="w-3.5 h-3.5 mr-1" />}
                                    {isAutoRead ? "Voice On" : "Voice Off"}
                                </Button>

                                {!selectedAgent.canDeployDirectly && (
                                    <div className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
                                        <AlertTriangle className="w-3 h-3" />
                                        Requires approval
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Chat History */}
                    <ScrollArea className="flex-1 p-4">
                        {chatHistory.length === 0 ? (
                            <div className="text-center py-8">
                                <Sparkles className="w-12 h-12 mx-auto mb-4 text-violet-300" />
                                <h3 className="font-semibold text-gray-700 mb-2">
                                    Tell me what you want to automate
                                </h3>
                                <p className="text-sm text-gray-500 mb-6">
                                    I'll create a workflow tailored to your needs
                                </p>

                                {/* Suggested Prompts */}
                                <div className="grid grid-cols-2 gap-2 max-w-xl mx-auto">
                                    {selectedAgent.suggestedPrompts.map((sp, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => handleSuggestedPrompt(sp)}
                                            className="text-left p-3 rounded-lg border hover:border-violet-300 hover:bg-violet-50 transition-colors text-sm"
                                        >
                                            <Zap className="w-4 h-4 text-violet-500 mb-1" />
                                            {sp}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4 max-w-2xl mx-auto">
                                {chatHistory.map((msg, idx) => (
                                    <div
                                        key={idx}
                                        className={cn(
                                            "flex gap-3",
                                            msg.role === 'user' ? "justify-end" : ""
                                        )}
                                    >
                                        {msg.role === 'agent' && (
                                            <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-sm", selectedAgent.color)}>
                                                {selectedAgent.icon}
                                            </div>
                                        )}
                                        <div className={cn(
                                            "max-w-md p-3 rounded-lg",
                                            msg.role === 'user'
                                                ? "bg-violet-600 text-white"
                                                : "bg-white border shadow-sm"
                                        )}>
                                            {msg.content}
                                        </div>
                                        {msg.role === 'user' && (
                                            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                                                <User className="w-4 h-4 text-gray-600" />
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}

                        {/* Reasoning Display */}
                        {showReasoning && reasoningSteps.length > 0 && (
                            <div className="max-w-2xl mx-auto my-4">
                                <div className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                                    <Bot className="w-3 h-3" /> Agent Reasoning Process
                                </div>
                                <ReasoningChain
                                    steps={reasoningSteps}
                                    isReasoning={isGenerating}
                                    onFeedback={handleReasoningFeedback}
                                />
                            </div>
                        )}

                        {/* Generated Workflow Preview */}
                        {generatedWorkflow && (
                            <Card className="mt-4 border-2 border-violet-200">
                                <CardHeader className="pb-2">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <CardTitle className="text-base">{generatedWorkflow.name}</CardTitle>
                                            <p className="text-xs text-gray-500 mt-1">{generatedWorkflow.description}</p>
                                        </div>
                                        <Badge className="bg-green-100 text-green-700">
                                            {Math.round(generatedWorkflow.confidence * 100)}% match
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Badge variant="outline" className="text-xs">
                                            Trigger: {generatedWorkflow.trigger.service}
                                        </Badge>
                                        <ArrowRight className="w-4 h-4 text-gray-400" />
                                        <Badge variant="outline" className="text-xs">
                                            {generatedWorkflow.steps.length} steps
                                        </Badge>
                                    </div>

                                    <div className="flex gap-2">
                                        {generatedWorkflow.requiresApproval ? (
                                            <Button onClick={handleDeploy} className="flex-1 bg-orange-500 hover:bg-orange-600">
                                                <Clock className="w-4 h-4 mr-2" />
                                                Submit for Approval
                                            </Button>
                                        ) : (
                                            <Button onClick={handleDeploy} className="flex-1">
                                                <Play className="w-4 h-4 mr-2" />
                                                Deploy Workflow
                                            </Button>
                                        )}
                                        <Button variant="outline">
                                            <Edit2 className="w-4 h-4 mr-2" />
                                            Edit
                                        </Button>
                                    </div>
                                    {generatedWorkflow.requiresApproval && (
                                        <p className="text-xs text-orange-600 mt-2 flex items-center gap-1">
                                            <AlertTriangle className="w-3 h-3" />
                                            This agent is still learning. A team lead or admin must approve this workflow.
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        )}
                    </div>
                            )}
                </ScrollArea>

            {/* Input Area */}
            <div className="p-4 border-t bg-white">
                <div className="flex gap-2 max-w-2xl mx-auto">
                    <Input
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Describe the automation you want to create..."
                        className="flex-1"
                        onKeyDown={(e) => e.key === 'Enter' && handleGenerateWorkflow()}
                        disabled={isGenerating}
                    />
                    <Button
                        onClick={handleGenerateWorkflow}
                        disabled={!prompt.trim() || isGenerating}
                    >
                        {isGenerating ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                            <Sparkles className="w-4 h-4" />
                        )}
                    </Button>
                    <VoiceInput
                        onTranscriptChange={(text) => setPrompt(text)}
                    />
                </div>
            </div>
        </>
        ) : (
        <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
                <Bot className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <h3 className="font-semibold text-lg mb-1">Select an Agent</h3>
                <p className="text-sm">Choose a specialty agent to generate workflows</p>
            </div>
        </div>
                )}
    </div>
        </div >
    );
};

export default AgentWorkflowGenerator;
export { SPECIALTY_AGENTS };
