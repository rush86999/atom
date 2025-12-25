'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
    Sparkles, Zap, MessageSquare, Play, Copy, Edit2,
    CheckCircle, Clock, User, Bot, ArrowRight, RefreshCw,
    Shield, AlertTriangle, GraduationCap, Award, Loader2
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// Agent governance status - matches backend AgentStatus enum
export type AgentMaturityLevel = 'student' | 'intern' | 'supervised' | 'autonomous';

// Agent types with their specialties and governance info
export interface SpecialtyAgent {
    id: string;
    name: string;
    specialty: string;
    description: string;
    icon: string;
    color: string;
    suggestedPrompts: string[];
    capabilities: string[];
    // Governance fields
    maturityLevel: AgentMaturityLevel;
    confidenceScore: number; // 0.0 to 1.0
    canDeployDirectly: boolean; // Based on maturity
}

// Generated workflow from agent
export interface GeneratedWorkflow {
    id: string;
    name: string;
    description: string;
    trigger: {
        type: string;
        service: string;
        event: string;
    };
    steps: {
        id: string;
        type: string;
        service: string;
        action: string;
        config: Record<string, any>;
    }[];
    estimatedTime: string;
    confidence: number;
    requiresApproval: boolean; // Based on agent maturity
}

// Maturity level display config
const MATURITY_CONFIG: Record<AgentMaturityLevel, { label: string; color: string; icon: React.ElementType; description: string }> = {
    student: {
        label: 'Learning',
        color: 'bg-orange-100 text-orange-700 border-orange-200',
        icon: GraduationCap,
        description: 'All workflows require approval'
    },
    intern: {
        label: 'Developing',
        color: 'bg-yellow-100 text-yellow-700 border-yellow-200',
        icon: Clock,
        description: 'Simple workflows can auto-deploy'
    },
    supervised: {
        label: 'Supervised',
        color: 'bg-blue-100 text-blue-700 border-blue-200',
        icon: Shield,
        description: 'Most workflows can auto-deploy'
    },
    autonomous: {
        label: 'Autonomous',
        color: 'bg-green-100 text-green-700 border-green-200',
        icon: Award,
        description: 'Full autonomy to deploy workflows'
    }
};

// Specialty agents catalog with governance maturity
const SPECIALTY_AGENTS: SpecialtyAgent[] = [
    {
        id: 'sales-agent',
        name: 'Sales Agent',
        specialty: 'Sales & CRM',
        description: 'Expert in sales automation, lead management, and CRM workflows',
        icon: '💼',
        color: 'bg-blue-500',
        suggestedPrompts: [
            'Create a lead follow-up sequence',
            'Set up deal stage notifications',
            'Automate lead scoring and enrichment',
            'Build a sales pipeline dashboard update',
        ],
        capabilities: ['Salesforce', 'HubSpot', 'Pipedrive', 'Email', 'Slack'],
        maturityLevel: 'supervised',
        confidenceScore: 0.85,
        canDeployDirectly: true,
    },
    {
        id: 'marketing-agent',
        name: 'Marketing Agent',
        specialty: 'Marketing & Campaigns',
        description: 'Expert in marketing automation, campaigns, and content distribution',
        icon: '📣',
        color: 'bg-pink-500',
        suggestedPrompts: [
            'Create a newsletter subscriber welcome sequence',
            'Automate social media posting schedule',
            'Set up campaign performance alerts',
            'Build a content calendar automation',
        ],
        capabilities: ['Mailchimp', 'Buffer', 'Hootsuite', 'Google Analytics', 'HubSpot'],
        maturityLevel: 'autonomous',
        confidenceScore: 0.92,
        canDeployDirectly: true,
    },
    {
        id: 'support-agent',
        name: 'Support Agent',
        specialty: 'Customer Support',
        description: 'Expert in support automation, ticket routing, and customer success',
        icon: '🎧',
        color: 'bg-green-500',
        suggestedPrompts: [
            'Create an AI ticket triage system',
            'Set up SLA breach alerts',
            'Automate customer feedback collection',
            'Build a support knowledge base updater',
        ],
        capabilities: ['Zendesk', 'Intercom', 'Freshdesk', 'Slack', 'Email'],
        maturityLevel: 'supervised',
        confidenceScore: 0.78,
        canDeployDirectly: true,
    },
    {
        id: 'engineering-agent',
        name: 'Engineering Agent',
        specialty: 'Development & DevOps',
        description: 'Expert in CI/CD, deployments, and engineering workflows',
        icon: '⚙️',
        color: 'bg-gray-600',
        suggestedPrompts: [
            'Create GitHub PR notification workflow',
            'Set up deployment announcements',
            'Automate code review assignments',
            'Build an incident response automation',
        ],
        capabilities: ['GitHub', 'GitLab', 'Jira', 'Slack', 'PagerDuty'],
        maturityLevel: 'autonomous',
        confidenceScore: 0.95,
        canDeployDirectly: true,
    },
    {
        id: 'hr-agent',
        name: 'HR Agent',
        specialty: 'Human Resources',
        description: 'Expert in HR automation, onboarding, and employee workflows',
        icon: '👥',
        color: 'bg-purple-500',
        suggestedPrompts: [
            'Create an employee onboarding sequence',
            'Set up PTO request automation',
            'Automate performance review reminders',
            'Build a new hire equipment provisioning flow',
        ],
        capabilities: ['BambooHR', 'Workday', 'Slack', 'Google Calendar', 'Asana'],
        maturityLevel: 'intern',
        confidenceScore: 0.62,
        canDeployDirectly: false,
    },
    {
        id: 'finance-agent',
        name: 'Finance Agent',
        specialty: 'Finance & Accounting',
        description: 'Expert in financial automation, invoicing, and expense workflows',
        icon: '💰',
        color: 'bg-yellow-500',
        suggestedPrompts: [
            'Create an invoice processing workflow',
            'Set up expense approval automation',
            'Automate monthly financial reports',
            'Build a payment reminder sequence',
        ],
        capabilities: ['QuickBooks', 'Stripe', 'Xero', 'Slack', 'Email'],
        maturityLevel: 'supervised',
        confidenceScore: 0.75,
        canDeployDirectly: true,
    },
    {
        id: 'data-agent',
        name: 'Data Agent',
        specialty: 'Data & Analytics',
        description: 'Expert in data pipelines, ETL, and analytics automation',
        icon: '📊',
        color: 'bg-indigo-500',
        suggestedPrompts: [
            'Create a data sync between apps',
            'Set up daily analytics reports',
            'Automate data enrichment pipeline',
            'Build a data quality monitoring flow',
        ],
        capabilities: ['Google Sheets', 'Airtable', 'PostgreSQL', 'BigQuery', 'Atom Memory'],
        maturityLevel: 'student',
        confidenceScore: 0.45,
        canDeployDirectly: false,
    },
    {
        id: 'productivity-agent',
        name: 'Productivity Agent',
        specialty: 'Productivity & Tasks',
        description: 'Expert in task management, scheduling, and productivity workflows',
        icon: '✨',
        color: 'bg-teal-500',
        suggestedPrompts: [
            'Create a meeting notes automation',
            'Set up task due date reminders',
            'Automate daily standup summaries',
            'Build a project status update flow',
        ],
        capabilities: ['Asana', 'Trello', 'Notion', 'Google Calendar', 'Slack'],
        maturityLevel: 'autonomous',
        confidenceScore: 0.91,
        canDeployDirectly: true,
    },
];

// Sample generated workflow
const generateSampleWorkflow = (prompt: string, agent: SpecialtyAgent): GeneratedWorkflow => {
    // This would be replaced with actual AI generation
    return {
        id: `wf-${Date.now()}`,
        name: prompt.length > 40 ? prompt.substring(0, 40) + '...' : prompt,
        description: `AI-generated workflow by ${agent.name} based on your request`,
        trigger: {
            type: 'webhook',
            service: agent.capabilities[0],
            event: 'New Record',
        },
        steps: [
            {
                id: 'step-1',
                type: 'action',
                service: agent.capabilities[0],
                action: 'Get Data',
                config: {},
            },
            {
                id: 'step-2',
                type: 'ai_node',
                service: 'OpenAI',
                action: 'Process with AI',
                config: { model: 'gpt-4' },
            },
            {
                id: 'step-3',
                type: 'action',
                service: agent.capabilities[agent.capabilities.length - 1],
                action: 'Send Notification',
                config: {},
            },
        ],
        estimatedTime: '~5 minutes to set up',
        confidence: 0.92,
        requiresApproval: !agent.canDeployDirectly, // Based on agent maturity
    };
};

interface AgentWorkflowGeneratorProps {
    onWorkflowGenerated?: (workflow: GeneratedWorkflow) => void;
    onDeployWorkflow?: (workflow: GeneratedWorkflow) => void;
    className?: string;
}

const AgentWorkflowGenerator: React.FC<AgentWorkflowGeneratorProps> = ({
    onWorkflowGenerated,
    onDeployWorkflow,
    className,
}) => {
    const [selectedAgent, setSelectedAgent] = useState<SpecialtyAgent | null>(null);
    const [prompt, setPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [isDeploying, setIsDeploying] = useState(false);
    const [generatedWorkflow, setGeneratedWorkflow] = useState<GeneratedWorkflow | null>(null);
    const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'agent'; content: string }[]>([]);
    const [agentGovernanceData, setAgentGovernanceData] = useState<Record<string, any>>({});
    const [loadingGovernance, setLoadingGovernance] = useState(false);

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
        setChatHistory(prev => [...prev, { role: 'user', content: prompt }]);

        // Simulate AI generation delay
        await new Promise(resolve => setTimeout(resolve, 1500));

        const workflow = generateSampleWorkflow(prompt, selectedAgent);
        setGeneratedWorkflow(workflow);

        setChatHistory(prev => [...prev, {
            role: 'agent',
            content: `I've created a workflow for "${prompt}". It includes ${workflow.steps.length} steps using ${selectedAgent.capabilities.slice(0, 3).join(', ')}. Would you like me to deploy it or make any modifications?`
        }]);

        onWorkflowGenerated?.(workflow);
        setIsGenerating(false);
        setPrompt('');
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
                setChatHistory(prev => [...prev, {
                    role: 'agent',
                    content: `✅ Great! I've deployed the workflow "${generatedWorkflow.name}". It's now active and ready to run. You can view it in the Flows tab.`
                }]);
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

                setChatHistory(prev => [...prev, {
                    role: 'agent',
                    content: `📝 I've submitted the workflow "${generatedWorkflow.name}" for approval. ${submitData.message || 'You will be notified when it is reviewed.'}`
                }]);
            }
        } catch (error) {
            console.error('Deployment check failed:', error);
            // Fallback to local logic
            if (selectedAgent.canDeployDirectly) {
                onDeployWorkflow?.(generatedWorkflow);
                setChatHistory(prev => [...prev, {
                    role: 'agent',
                    content: `Great! I've deployed the workflow "${generatedWorkflow.name}". It's now active and ready to run.`
                }]);
            } else {
                setChatHistory(prev => [...prev, {
                    role: 'agent',
                    content: `📝 This workflow requires approval. I've submitted it for review by a team lead.`
                }]);
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
                                {!selectedAgent.canDeployDirectly && (
                                    <div className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
                                        <AlertTriangle className="w-3 h-3" />
                                        Requires approval
                                    </div>
                                )}
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
                                    ))}

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
        </div>
    );
};

export default AgentWorkflowGenerator;
export { SPECIALTY_AGENTS };
