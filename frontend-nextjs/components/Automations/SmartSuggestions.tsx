'use client';

import React, { useMemo } from 'react';
import { Node, Edge } from 'reactflow';
import { Sparkles, ArrowRight, Zap, Clock, GitBranch, Mail, MessageSquare, Database, Users, FileText, AlertCircle } from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * SmartSuggestions Component
 * Analyzes the current workflow and suggests intelligent next steps.
 * Part of Phase 4: Enhanced AI Flow
 */

export interface StepSuggestion {
    id: string;
    title: string;
    description: string;
    type: 'action' | 'trigger' | 'condition' | 'ai_node' | 'loop';
    service?: string;
    icon: React.ComponentType<{ className?: string }>;
    confidence: number; // 0-1, how confident we are this is a good suggestion
    reason: string;
}

// Common workflow patterns for smart suggestions
const WORKFLOW_PATTERNS: Record<string, StepSuggestion[]> = {
    // After a trigger, suggest actions
    'trigger': [
        { id: 'add-condition', title: 'Add Condition', description: 'Branch based on trigger data', type: 'condition', icon: GitBranch, confidence: 0.8, reason: 'Filtering trigger data is common' },
        { id: 'add-action', title: 'Add Action', description: 'Perform an action with the data', type: 'action', icon: Zap, confidence: 0.9, reason: 'Triggers are usually followed by actions' },
        { id: 'add-delay', title: 'Add Delay', description: 'Wait before processing', type: 'action', icon: Clock, confidence: 0.5, reason: 'Timing can be important' },
    ],
    // After Slack message received
    'slack_trigger': [
        { id: 'send-slack-reply', title: 'Reply in Slack', description: 'Send a response message', type: 'action', service: 'slack', icon: MessageSquare, confidence: 0.95, reason: 'Replying to messages is the most common pattern' },
        { id: 'create-ticket', title: 'Create Support Ticket', description: 'Log the message as a ticket', type: 'action', service: 'zendesk', icon: FileText, confidence: 0.7, reason: 'Common for support workflows' },
        { id: 'ai-analyze', title: 'Analyze with AI', description: 'Extract intent from message', type: 'ai_node', icon: Sparkles, confidence: 0.85, reason: 'AI can route based on message content' },
    ],
    // After email trigger
    'gmail': [
        { id: 'ai-summarize', title: 'Summarize Email', description: 'Get key points with AI', type: 'ai_node', icon: Sparkles, confidence: 0.9, reason: 'AI summarization is very helpful' },
        { id: 'create-task', title: 'Create Task', description: 'Track follow-ups', type: 'action', service: 'asana', icon: FileText, confidence: 0.8, reason: 'Emails often need follow-up tasks' },
        { id: 'add-label', title: 'Add Label', description: 'Organize the email', type: 'action', service: 'gmail', icon: Mail, confidence: 0.7, reason: 'Categorizing helps organization' },
    ],
    // After CRM trigger (Salesforce/HubSpot)
    'salesforce': [
        { id: 'update-record', title: 'Update Record', description: 'Modify the opportunity', type: 'action', service: 'salesforce', icon: Users, confidence: 0.9, reason: 'Updating records is the top use case' },
        { id: 'send-notification', title: 'Send Notification', description: 'Alert team on Slack', type: 'action', service: 'slack', icon: MessageSquare, confidence: 0.85, reason: 'Team notifications are common' },
        { id: 'ai-score', title: 'AI Lead Score', description: 'Calculate lead quality', type: 'ai_node', icon: Sparkles, confidence: 0.75, reason: 'AI scoring improves prioritization' },
    ],
    'hubspot': [
        { id: 'update-contact', title: 'Update Contact', description: 'Modify contact properties', type: 'action', service: 'hubspot', icon: Users, confidence: 0.9, reason: 'Keeping contacts updated is essential' },
        { id: 'create-deal', title: 'Create Deal', description: 'Start a new deal', type: 'action', service: 'hubspot', icon: Users, confidence: 0.8, reason: 'Deals often follow contact activity' },
        { id: 'send-email', title: 'Send Email', description: 'Follow up via email', type: 'action', service: 'gmail', icon: Mail, confidence: 0.75, reason: 'Email follow-ups drive conversions' },
    ],
    // After a condition
    'condition': [
        { id: 'true-action', title: 'True Branch Action', description: 'Action when condition is met', type: 'action', icon: Zap, confidence: 0.95, reason: 'Conditions need actions on both branches' },
        { id: 'false-action', title: 'False Branch Action', description: 'Action when condition fails', type: 'action', icon: Zap, confidence: 0.9, reason: 'Handle both cases for robustness' },
        { id: 'nested-condition', title: 'Nested Condition', description: 'Add more complex logic', type: 'condition', icon: GitBranch, confidence: 0.6, reason: 'Some workflows need multi-level branching' },
    ],
    // After an action
    'action': [
        { id: 'next-action', title: 'Add Another Action', description: 'Chain multiple actions', type: 'action', icon: Zap, confidence: 0.8, reason: 'Workflows often have multiple steps' },
        { id: 'add-condition', title: 'Add Condition', description: 'Branch based on result', type: 'condition', icon: GitBranch, confidence: 0.7, reason: 'Check action success/failure' },
        { id: 'store-data', title: 'Store Result', description: 'Save to Atom Memory', type: 'action', service: 'atom-memory', icon: Database, confidence: 0.65, reason: 'Storing data enables learning' },
    ],
    // After AI node
    'ai_node': [
        { id: 'condition-on-ai', title: 'Branch on AI Result', description: 'Different paths based on AI output', type: 'condition', icon: GitBranch, confidence: 0.9, reason: 'AI outputs often need routing' },
        { id: 'use-ai-result', title: 'Use AI Result', description: 'Pass to next action', type: 'action', icon: Zap, confidence: 0.85, reason: 'AI outputs drive downstream actions' },
        { id: 'store-ai-result', title: 'Store AI Result', description: 'Save for future reference', type: 'action', service: 'atom-memory', icon: Database, confidence: 0.7, reason: 'AI insights are valuable to persist' },
    ],
    // Default/empty workflow
    'empty': [
        { id: 'add-trigger', title: 'Add Trigger', description: 'Start with an event source', type: 'trigger', icon: Zap, confidence: 1.0, reason: 'Every workflow needs a trigger' },
    ],
};

interface SmartSuggestionsProps {
    nodes: Node[];
    edges: Edge[];
    onSuggestionClick: (suggestion: StepSuggestion) => void;
    className?: string;
}

export const SmartSuggestions: React.FC<SmartSuggestionsProps> = ({
    nodes,
    edges,
    onSuggestionClick,
    className
}) => {
    // Analyze current workflow and get suggestions
    const suggestions = useMemo(() => {
        // Empty workflow
        if (nodes.length === 0) {
            return WORKFLOW_PATTERNS['empty'];
        }

        // Find the last node (most recently added or end of chain)
        const nodeIds = new Set(nodes.map(n => n.id));
        const connectedTargets = new Set(edges.map(e => e.target));
        const leafNodes = nodes.filter(n =>
            !edges.some(e => e.source === n.id && nodeIds.has(e.target))
        );

        const lastNode = leafNodes[leafNodes.length - 1] || nodes[nodes.length - 1];
        if (!lastNode) return WORKFLOW_PATTERNS['empty'];

        const nodeType = lastNode.type || 'action';
        const nodeData = lastNode.data || {};
        const service = (nodeData.service || nodeData.serviceId || '').toLowerCase();

        // Get pattern-based suggestions
        let patternKey = nodeType;

        // Check for service-specific patterns
        if (service && WORKFLOW_PATTERNS[service]) {
            patternKey = service;
        }
        // Check for trigger + service combo
        else if (nodeType === 'trigger' && service) {
            patternKey = `${service}_trigger`;
            if (!WORKFLOW_PATTERNS[patternKey]) {
                patternKey = 'trigger';
            }
        }

        const baseSuggestions = WORKFLOW_PATTERNS[patternKey] || WORKFLOW_PATTERNS['action'] || [];

        // Boost suggestions based on workflow context
        return baseSuggestions.map(s => ({
            ...s,
            // Boost confidence if the service matches the workflow theme
            confidence: s.service === service ? Math.min(s.confidence + 0.1, 1.0) : s.confidence
        })).sort((a, b) => b.confidence - a.confidence);

    }, [nodes, edges]);

    if (suggestions.length === 0) return null;

    return (
        <div className={cn("bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-200 rounded-lg p-3", className)}>
            <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-violet-600" />
                <span className="font-semibold text-sm text-violet-800">Suggested Next Steps</span>
            </div>

            <div className="space-y-2">
                {suggestions.slice(0, 3).map((suggestion) => {
                    const Icon = suggestion.icon;
                    return (
                        <button
                            key={suggestion.id}
                            onClick={() => onSuggestionClick(suggestion)}
                            className="w-full flex items-center gap-3 p-2 bg-white rounded-md border border-violet-100 hover:border-violet-300 hover:shadow-sm transition-all text-left group"
                        >
                            <div className={cn(
                                "p-1.5 rounded",
                                suggestion.type === 'ai_node' ? 'bg-purple-100 text-purple-600' :
                                    suggestion.type === 'condition' ? 'bg-orange-100 text-orange-600' :
                                        'bg-blue-100 text-blue-600'
                            )}>
                                <Icon className="w-4 h-4" />
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm text-gray-800">{suggestion.title}</span>
                                    {suggestion.confidence >= 0.85 && (
                                        <Badge variant="secondary" className="text-[9px] px-1 py-0 bg-green-100 text-green-700">
                                            Recommended
                                        </Badge>
                                    )}
                                </div>
                                <p className="text-xs text-gray-500 truncate">{suggestion.description}</p>
                            </div>

                            <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-violet-600 transition-colors" />
                        </button>
                    );
                })}
            </div>

            {/* Why these suggestions */}
            <div className="mt-3 pt-2 border-t border-violet-200">
                <button className="flex items-center gap-1 text-[10px] text-violet-600 hover:text-violet-800">
                    <AlertCircle className="w-3 h-3" />
                    Why these suggestions?
                </button>
            </div>
        </div>
    );
};

export default SmartSuggestions;
