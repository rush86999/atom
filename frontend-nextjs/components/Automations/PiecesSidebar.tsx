'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Search, ChevronRight, CheckCircle, Plus, Zap, Mail, MessageSquare, Calendar, FileText, Users, CreditCard, Database, Globe, Code, Settings, Repeat, UserCheck, Clock, Cog, Sparkles, ShoppingCart, BarChart, Shield, Cpu, Smartphone, GraduationCap, Heart, Scale, Home, Package, Loader2 } from 'lucide-react';
import { FaGoogle, FaSlack, FaGithub, FaMicrosoft, FaSalesforce, FaHubspot, FaTrello, FaDropbox } from 'react-icons/fa';
import { SiNotion, SiAsana, SiJira, SiZendesk, SiStripe, SiQuickbooks, SiMailchimp, SiZoom } from 'react-icons/si';
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// Piece definition - each integration/service
export interface Piece {
    id: string;
    name: string;
    icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
    color: string;
    category: string;
    actions: PieceAction[];
    triggers: PieceTrigger[];
    connected?: boolean;
}

// Import catalog types
import {
    Integration,
    INTEGRATION_COUNT,
} from "@/lib/integrations-catalog";

// Piece definition - each integration/service
// These are UI-specific pieces that merge local and catalog data

export interface PieceAction {
    id: string;
    name: string;
    description: string;
}

export interface PieceTrigger {
    id: string;
    name: string;
    description: string;
}

// All available pieces - modeled after Activepieces
const PIECES: Piece[] = [
    // Core Pieces (built-in control flow)
    {
        id: 'loop',
        name: 'Loop',
        icon: Repeat,
        color: '#14B8A6',
        category: 'core',
        triggers: [],
        actions: [
            { id: 'for_each', name: 'For Each', description: 'Iterate over items in an array' },
            { id: 'repeat', name: 'Repeat', description: 'Repeat steps a specified number of times' },
        ],
    },
    {
        id: 'code',
        name: 'Code',
        icon: Code,
        color: '#334155',
        category: 'core',
        triggers: [],
        actions: [
            { id: 'run_code', name: 'Run TypeScript', description: 'Execute custom TypeScript code' },
            { id: 'run_js', name: 'Run JavaScript', description: 'Execute custom JavaScript code' },
        ],
    },
    {
        id: 'approval',
        name: 'Wait for Approval',
        icon: UserCheck,
        color: '#F59E0B',
        category: 'core',
        triggers: [],
        actions: [
            { id: 'wait_approval', name: 'Wait for Approval', description: 'Pause workflow until approved' },
            { id: 'request_input', name: 'Request Input', description: 'Request additional input from user' },
        ],
    },
    {
        id: 'http',
        name: 'HTTP Request',
        icon: Globe,
        color: '#EA580C',
        category: 'core',
        triggers: [
            { id: 'webhook', name: 'Webhook', description: 'Receive HTTP requests' },
        ],
        actions: [
            { id: 'get_request', name: 'GET Request', description: 'Make an HTTP GET request' },
            { id: 'post_request', name: 'POST Request', description: 'Make an HTTP POST request' },
            { id: 'custom_request', name: 'Custom Request', description: 'Make a custom HTTP request' },
        ],
    },
    {
        id: 'delay',
        name: 'Delay',
        icon: Clock,
        color: '#6366F1',
        category: 'core',
        triggers: [
            { id: 'schedule', name: 'Schedule', description: 'Trigger at scheduled time' },
        ],
        actions: [
            { id: 'wait', name: 'Delay', description: 'Wait for a specified duration' },
            { id: 'wait_until', name: 'Delay Until', description: 'Wait until a specific time' },
        ],
    },
    {
        id: 'tables',
        name: 'Tables',
        icon: Database,
        color: '#0D9488',
        category: 'core',
        triggers: [
            { id: 'row_created', name: 'Row Created', description: 'Trigger when a new row is added' },
            { id: 'row_updated', name: 'Row Updated', description: 'Trigger when a row is modified' },
        ],
        actions: [
            { id: 'insert_row', name: 'Insert Row', description: 'Add a new row to a table' },
            { id: 'update_row', name: 'Update Row', description: 'Update an existing row' },
            { id: 'find_rows', name: 'Find Rows', description: 'Search for rows matching criteria' },
            { id: 'delete_row', name: 'Delete Row', description: 'Remove a row from a table' },
        ],
    },
    {
        id: 'subflow',
        name: 'Sub Flows',
        icon: Zap,
        color: '#8B5CF6',
        category: 'core',
        triggers: [],
        actions: [
            { id: 'call_flow', name: 'Call Flow', description: 'Execute another flow and return result' },
            { id: 'trigger_flow', name: 'Trigger Flow', description: 'Start another flow asynchronously' },
        ],
    },
    {
        id: 'storage',
        name: 'Storage',
        icon: Database,
        color: '#059669',
        category: 'core',
        triggers: [],
        actions: [
            { id: 'put_value', name: 'Put Value', description: 'Store a value with a key' },
            { id: 'get_value', name: 'Get Value', description: 'Retrieve a stored value' },
            { id: 'delete_value', name: 'Delete Value', description: 'Remove a stored value' },
            { id: 'append_list', name: 'Append to List', description: 'Add item to a stored list' },
        ],
    },

    // Communication
    {
        id: 'gmail',
        name: 'Gmail',
        icon: FaGoogle,
        color: '#EA4335',
        category: 'communication',
        triggers: [
            { id: 'new_email', name: 'New Email', description: 'Triggers when a new email is received' },
            { id: 'new_labeled', name: 'New Labeled Email', description: 'Triggers when an email gets a specific label' },
        ],
        actions: [
            { id: 'send_email', name: 'Send Email', description: 'Send an email to one or more recipients' },
            { id: 'create_draft', name: 'Create Draft', description: 'Create a draft email' },
            { id: 'add_label', name: 'Add Label', description: 'Add a label to an email' },
        ],
    },
    {
        id: 'slack',
        name: 'Slack',
        icon: FaSlack,
        color: '#4A154B',
        category: 'communication',
        triggers: [
            { id: 'new_message', name: 'New Message', description: 'Triggers when a message is posted to a channel' },
            { id: 'new_mention', name: 'New Mention', description: 'Triggers when you are mentioned' },
        ],
        actions: [
            { id: 'send_message', name: 'Send Message', description: 'Send a message to a channel or user' },
            { id: 'create_channel', name: 'Create Channel', description: 'Create a new Slack channel' },
            { id: 'update_status', name: 'Update Status', description: 'Update your Slack status' },
        ],
    },
    {
        id: 'outlook',
        name: 'Outlook',
        icon: FaMicrosoft,
        color: '#0078D4',
        category: 'communication',
        triggers: [
            { id: 'new_email', name: 'New Email', description: 'Triggers when a new email arrives' },
        ],
        actions: [
            { id: 'send_email', name: 'Send Email', description: 'Send an email via Outlook' },
            { id: 'create_event', name: 'Create Event', description: 'Create a calendar event' },
        ],
    },
    {
        id: 'teams',
        name: 'Microsoft Teams',
        icon: FaMicrosoft,
        color: '#6264A7',
        category: 'communication',
        triggers: [
            { id: 'new_message', name: 'New Message', description: 'Triggers on new team message' },
        ],
        actions: [
            { id: 'send_message', name: 'Send Message', description: 'Send a message to a Teams channel' },
            { id: 'create_meeting', name: 'Create Meeting', description: 'Schedule a Teams meeting' },
        ],
    },
    {
        id: 'zoom',
        name: 'Zoom',
        icon: SiZoom,
        color: '#2D8CFF',
        category: 'communication',
        triggers: [
            { id: 'meeting_ended', name: 'Meeting Ended', description: 'Triggers when a meeting ends' },
        ],
        actions: [
            { id: 'create_meeting', name: 'Create Meeting', description: 'Schedule a new Zoom meeting' },
            { id: 'get_recording', name: 'Get Recording', description: 'Get meeting recording' },
        ],
    },

    // Productivity
    {
        id: 'notion',
        name: 'Notion',
        icon: SiNotion,
        color: '#000000',
        category: 'productivity',
        triggers: [
            { id: 'page_updated', name: 'Page Updated', description: 'Triggers when a page is updated' },
        ],
        actions: [
            { id: 'create_page', name: 'Create Page', description: 'Create a new Notion page' },
            { id: 'update_page', name: 'Update Page', description: 'Update page properties' },
            { id: 'add_block', name: 'Add Block', description: 'Append content to a page' },
        ],
    },
    {
        id: 'asana',
        name: 'Asana',
        icon: SiAsana,
        color: '#F06A6A',
        category: 'productivity',
        triggers: [
            { id: 'new_task', name: 'New Task', description: 'Triggers when a task is created' },
            { id: 'task_completed', name: 'Task Completed', description: 'Triggers when a task is marked complete' },
        ],
        actions: [
            { id: 'create_task', name: 'Create Task', description: 'Create a new Asana task' },
            { id: 'update_task', name: 'Update Task', description: 'Update task details' },
            { id: 'add_comment', name: 'Add Comment', description: 'Add a comment to a task' },
        ],
    },
    {
        id: 'trello',
        name: 'Trello',
        icon: FaTrello,
        color: '#0079BF',
        category: 'productivity',
        triggers: [
            { id: 'new_card', name: 'New Card', description: 'Triggers when a card is created' },
            { id: 'card_moved', name: 'Card Moved', description: 'Triggers when a card moves to another list' },
        ],
        actions: [
            { id: 'create_card', name: 'Create Card', description: 'Create a new Trello card' },
            { id: 'move_card', name: 'Move Card', description: 'Move a card to another list' },
        ],
    },
    {
        id: 'jira',
        name: 'Jira',
        icon: SiJira,
        color: '#0052CC',
        category: 'productivity',
        triggers: [
            { id: 'new_issue', name: 'New Issue', description: 'Triggers when an issue is created' },
            { id: 'issue_updated', name: 'Issue Updated', description: 'Triggers when an issue is updated' },
        ],
        actions: [
            { id: 'create_issue', name: 'Create Issue', description: 'Create a new Jira issue' },
            { id: 'update_issue', name: 'Update Issue', description: 'Update issue fields' },
            { id: 'add_comment', name: 'Add Comment', description: 'Add a comment to an issue' },
        ],
    },
    {
        id: 'google_calendar',
        name: 'Google Calendar',
        icon: FaGoogle,
        color: '#4285F4',
        category: 'productivity',
        triggers: [
            { id: 'event_start', name: 'Event Starting', description: 'Triggers before an event starts' },
            { id: 'new_event', name: 'New Event', description: 'Triggers when an event is created' },
        ],
        actions: [
            { id: 'create_event', name: 'Create Event', description: 'Create a new calendar event' },
            { id: 'update_event', name: 'Update Event', description: 'Update event details' },
            { id: 'delete_event', name: 'Delete Event', description: 'Delete a calendar event' },
        ],
    },

    // CRM
    {
        id: 'salesforce',
        name: 'Salesforce',
        icon: FaSalesforce,
        color: '#00A1E0',
        category: 'crm',
        triggers: [
            { id: 'new_lead', name: 'New Lead', description: 'Triggers when a new lead is created' },
            { id: 'opportunity_updated', name: 'Opportunity Updated', description: 'Triggers when an opportunity is updated' },
        ],
        actions: [
            { id: 'create_lead', name: 'Create Lead', description: 'Create a new Salesforce lead' },
            { id: 'update_record', name: 'Update Record', description: 'Update any Salesforce record' },
            { id: 'create_task', name: 'Create Task', description: 'Create a follow-up task' },
        ],
    },
    {
        id: 'hubspot',
        name: 'HubSpot',
        icon: FaHubspot,
        color: '#FF7A59',
        category: 'crm',
        triggers: [
            { id: 'new_contact', name: 'New Contact', description: 'Triggers when a contact is created' },
            { id: 'deal_stage_change', name: 'Deal Stage Changed', description: 'Triggers when a deal moves stages' },
        ],
        actions: [
            { id: 'create_contact', name: 'Create Contact', description: 'Create a new HubSpot contact' },
            { id: 'create_deal', name: 'Create Deal', description: 'Create a new deal' },
            { id: 'send_email', name: 'Send Email', description: 'Send a marketing email' },
        ],
    },

    // Development
    {
        id: 'github',
        name: 'GitHub',
        icon: FaGithub,
        color: '#181717',
        category: 'development',
        triggers: [
            { id: 'new_pr', name: 'New Pull Request', description: 'Triggers on new PR' },
            { id: 'issue_created', name: 'New Issue', description: 'Triggers when an issue is created' },
            { id: 'push', name: 'New Push', description: 'Triggers on repository push' },
        ],
        actions: [
            { id: 'create_issue', name: 'Create Issue', description: 'Create a new GitHub issue' },
            { id: 'add_comment', name: 'Add Comment', description: 'Add comment to issue or PR' },
            { id: 'create_pr', name: 'Create Pull Request', description: 'Create a new pull request' },
        ],
    },

    // Finance
    {
        id: 'stripe',
        name: 'Stripe',
        icon: SiStripe,
        color: '#635BFF',
        category: 'finance',
        triggers: [
            { id: 'payment_received', name: 'Payment Received', description: 'Triggers when a payment succeeds' },
            { id: 'subscription_created', name: 'New Subscription', description: 'Triggers on new subscription' },
        ],
        actions: [
            { id: 'create_invoice', name: 'Create Invoice', description: 'Create a new Stripe invoice' },
            { id: 'send_invoice', name: 'Send Invoice', description: 'Send invoice to customer' },
        ],
    },
    {
        id: 'quickbooks',
        name: 'QuickBooks',
        icon: SiQuickbooks,
        color: '#2CA01C',
        category: 'finance',
        triggers: [
            { id: 'new_invoice', name: 'New Invoice', description: 'Triggers when invoice is created' },
        ],
        actions: [
            { id: 'create_invoice', name: 'Create Invoice', description: 'Create a QuickBooks invoice' },
            { id: 'create_customer', name: 'Create Customer', description: 'Create a new customer' },
        ],
    },

    // Storage
    {
        id: 'google_drive',
        name: 'Google Drive',
        icon: FaGoogle,
        color: '#0F9D58',
        category: 'storage',
        triggers: [
            { id: 'new_file', name: 'New File', description: 'Triggers when a file is uploaded' },
        ],
        actions: [
            { id: 'upload_file', name: 'Upload File', description: 'Upload a file to Drive' },
            { id: 'create_folder', name: 'Create Folder', description: 'Create a new folder' },
        ],
    },
    {
        id: 'dropbox',
        name: 'Dropbox',
        icon: FaDropbox,
        color: '#0061FF',
        category: 'storage',
        triggers: [
            { id: 'new_file', name: 'New File', description: 'Triggers on new file upload' },
        ],
        actions: [
            { id: 'upload_file', name: 'Upload File', description: 'Upload a file to Dropbox' },
            { id: 'create_shared_link', name: 'Create Shared Link', description: 'Create a shareable link' },
        ],
    },

    // Support
    {
        id: 'zendesk',
        name: 'Zendesk',
        icon: SiZendesk,
        color: '#03363D',
        category: 'support',
        triggers: [
            { id: 'new_ticket', name: 'New Ticket', description: 'Triggers when a ticket is created' },
        ],
        actions: [
            { id: 'create_ticket', name: 'Create Ticket', description: 'Create a support ticket' },
            { id: 'update_ticket', name: 'Update Ticket', description: 'Update ticket status' },
        ],
    },

    // Marketing
    {
        id: 'mailchimp',
        name: 'Mailchimp',
        icon: SiMailchimp,
        color: '#FFE01B',
        category: 'marketing',
        triggers: [
            { id: 'new_subscriber', name: 'New Subscriber', description: 'Triggers on new list subscriber' },
        ],
        actions: [
            { id: 'add_subscriber', name: 'Add Subscriber', description: 'Add a subscriber to a list' },
            { id: 'send_campaign', name: 'Send Campaign', description: 'Send an email campaign' },
        ],
    },

    // AI
    {
        id: 'openai',
        name: 'OpenAI',
        icon: Zap,
        color: '#412991',
        category: 'ai',
        triggers: [],
        actions: [
            { id: 'generate_text', name: 'Generate Text', description: 'Generate text with GPT' },
            { id: 'summarize', name: 'Summarize', description: 'Summarize long text' },
            { id: 'analyze_sentiment', name: 'Analyze Sentiment', description: 'Analyze text sentiment' },
        ],
    },
    {
        id: 'gemini',
        name: 'Google Gemini',
        icon: FaGoogle,
        color: '#8E75B2',
        category: 'ai',
        triggers: [],
        actions: [
            { id: 'generate_content', name: 'Generate Content', description: 'Generate content with Gemini' },
            { id: 'analyze_image', name: 'Analyze Image', description: 'Analyze an image' },
        ],
    },
];

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    core: Cog,
    communication: MessageSquare,
    productivity: FileText,
    crm: Users,
    development: Code,
    finance: CreditCard,
    storage: Database,
    marketing: Mail,
    support: Settings,
    ai: Zap,
    ecommerce: ShoppingCart,
    form: FileText,
    scheduling: Calendar,
    hr: Users,
    social: MessageSquare,
    analytics: BarChart,
    security: Shield,
    iot: Cpu,
    media: Smartphone,
    education: GraduationCap,
    healthcare: Heart,
    legal: Scale,
    real_estate: Home,
    other: Package,
};

const CATEGORY_LABELS: Record<string, string> = {
    core: 'Core Pieces',
    communication: 'Communication',
    productivity: 'Productivity',
    crm: 'CRM & Sales',
    development: 'Development',
    finance: 'Finance',
    storage: 'File Storage',
    marketing: 'Marketing',
    support: 'Customer Support',
    ai: 'AI & Automation',
    ecommerce: 'E-Commerce',
    form: 'Forms & Surveys',
    scheduling: 'Scheduling',
    hr: 'HR & Recruiting',
    social: 'Social Media',
    analytics: 'Analytics',
    security: 'Security',
    iot: 'IoT & Devices',
    media: 'Media & Content',
    education: 'Education',
    healthcare: 'Healthcare',
    legal: 'Legal',
    real_estate: 'Real Estate',
    other: 'Other',
};



interface PiecesSidebarProps {
    onSelectPiece: (piece: Piece, type: 'trigger' | 'action', item: PieceAction | PieceTrigger) => void;
    className?: string;
}

const PiecesSidebar: React.FC<PiecesSidebarProps> = ({ onSelectPiece, className }) => {
    const [search, setSearch] = useState('');
    const [expandedPiece, setExpandedPiece] = useState<string | null>(null);
    const [connectedPieces, setConnectedPieces] = useState<Set<string>>(new Set());
    const [allPieces, setAllPieces] = useState<Piece[]>(PIECES);
    const [isLoading, setIsLoading] = useState(true);

    // Fetched catalog logic restored - Source from Node.js Bridge
    useEffect(() => {
        const fetchExternalPieces = async () => {
            try {
                const response = await fetch('/api/v1/external-integrations/');
                if (!response.ok) throw new Error("Failed to fetch");

                const externalPiecesRaw = await response.json();

                // Map external pieces to UI format
                const externalPieces: Piece[] = externalPiecesRaw.map((p: any) => ({
                    id: p.name, // e.g., @activepieces/piece-slack
                    name: p.displayName,
                    icon: () => p.logoUrl ? <img src={p.logoUrl} className="w-5 h-5 object-contain" alt={p.displayName} /> : <Globe className="w-5 h-5" />,
                    color: '#64748b', // Default color
                    category: 'other', // Default category or map from p.tags
                    actions: Object.values(p.actions).map((a: any) => ({
                        id: a.name,
                        name: a.displayName,
                        description: a.description
                    })),
                    triggers: Object.values(p.triggers).map((t: any) => ({
                        id: t.name,
                        name: t.displayName,
                        description: t.description
                    })),
                    connected: false
                }));

                setAllPieces([...PIECES, ...externalPieces]);
            } catch (err) {
                console.error("Failed to load external pieces:", err);
                // Fallback to just local pieces
                setAllPieces(PIECES);
            } finally {
                setIsLoading(false);
            }
        };

        fetchExternalPieces();
    }, []);

    // Check connection status for popular pieces only
    useEffect(() => {
        const checkConnections = async () => {
            const connected = new Set<string>();
            // Only check local hardcoded pieces for health status for now
            const piecesToCheck = PIECES.slice(0, 30);
            await Promise.all(
                piecesToCheck.map(async (piece) => {
                    try {
                        const res = await fetch(`/api/integrations/${piece.id}/health`);
                        if (res.ok) connected.add(piece.id);
                    } catch { /* ignore */ }
                })
            );
            setConnectedPieces(connected);
        };
        checkConnections();
    }, []);

    // Filter pieces based on search
    const filteredPieces = useMemo(() => {
        if (!search.trim()) return allPieces;
        const query = search.toLowerCase();
        return allPieces.filter(
            (p) =>
                p.name.toLowerCase().includes(query) ||
                p.actions.some((a) => a.name.toLowerCase().includes(query)) ||
                p.triggers.some((t) => t.name.toLowerCase().includes(query))
        );
    }, [search, allPieces]);

    // Group by category
    const groupedPieces = useMemo(() => {
        const groups: Record<string, Piece[]> = {};
        filteredPieces.forEach((piece) => {
            if (!groups[piece.category]) groups[piece.category] = [];
            groups[piece.category].push(piece);
        });
        return groups;
    }, [filteredPieces]);

    return (
        <div className={cn("w-72 border-r bg-gray-50 dark:bg-gray-900 flex flex-col", className)} data-testid="pieces-sidebar">
            {/* Header */}
            <div className="p-4 border-b bg-white dark:bg-gray-800">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="font-bold text-lg">Pieces</h3>
                    <Badge variant="secondary" className="text-xs">
                        {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : `${allPieces.length}+`}
                    </Badge>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search pieces & actions..."
                        className="pl-10"
                        data-testid="piece-search"
                    />
                </div>
                <p className="text-xs text-gray-500 mt-2">
                    {PIECES.length} pieces • {PIECES.reduce((a, p) => a + p.actions.length + p.triggers.length, 0)} actions
                </p>
            </div>

            {/* Pieces List */}
            <ScrollArea className="flex-1">
                <div className="p-2">
                    {Object.entries(groupedPieces).map(([category, pieces]) => {
                        const CategoryIcon = CATEGORY_ICONS[category] || Globe;
                        return (
                            <div key={category} className="mb-4">
                                {/* Category Header */}
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-semibold text-gray-500 uppercase">
                                    <CategoryIcon className="w-3 h-3" />
                                    {CATEGORY_LABELS[category] || category}
                                </div>

                                {/* Pieces in category */}
                                {pieces.map((piece) => {
                                    const IconComponent = piece.icon;
                                    const isExpanded = expandedPiece === piece.id;
                                    const isConnected = connectedPieces.has(piece.id);

                                    return (
                                        <div key={piece.id} className="mb-1">
                                            {/* Piece Header */}
                                            <button
                                                onClick={() => setExpandedPiece(isExpanded ? null : piece.id)}
                                                className={cn(
                                                    "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors",
                                                    "hover:bg-white dark:hover:bg-gray-800",
                                                    isExpanded && "bg-white dark:bg-gray-800 shadow-sm"
                                                )}
                                            >
                                                <IconComponent style={{ color: piece.color }} className="w-5 h-5 flex-shrink-0" />
                                                <span className="font-medium text-sm flex-1">{piece.name}</span>
                                                {isConnected && (
                                                    <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0" />
                                                )}
                                                <ChevronRight
                                                    className={cn(
                                                        "w-4 h-4 text-gray-400 transition-transform",
                                                        isExpanded && "rotate-90"
                                                    )}
                                                />
                                            </button>

                                            {/* Expanded Actions/Triggers */}
                                            {isExpanded && (
                                                <div className="ml-4 mt-1 space-y-1 pl-4 border-l-2 border-gray-200">
                                                    {/* Triggers */}
                                                    {piece.triggers.length > 0 && (
                                                        <>
                                                            <div className="text-[10px] uppercase text-gray-400 font-semibold px-2 pt-1">
                                                                Triggers
                                                            </div>
                                                            {piece.triggers.map((trigger) => (
                                                                <button
                                                                    key={trigger.id}
                                                                    onClick={() => onSelectPiece(piece, 'trigger', trigger)}
                                                                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-blue-50 dark:hover:bg-blue-900/20 group"
                                                                >
                                                                    <Zap className="w-3 h-3 text-blue-500" />
                                                                    <div className="flex-1 min-w-0">
                                                                        <div className="text-sm font-medium truncate">{trigger.name}</div>
                                                                        <div className="text-[10px] text-gray-500 truncate">{trigger.description}</div>
                                                                    </div>
                                                                    <Plus className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100" />
                                                                </button>
                                                            ))}
                                                        </>
                                                    )}

                                                    {/* Actions */}
                                                    {piece.actions.length > 0 && (
                                                        <>
                                                            <div className="text-[10px] uppercase text-gray-400 font-semibold px-2 pt-1">
                                                                Actions
                                                            </div>
                                                            {piece.actions.map((action) => (
                                                                <button
                                                                    key={action.id}
                                                                    onClick={() => onSelectPiece(piece, 'action', action)}
                                                                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-green-50 dark:hover:bg-green-900/20 group"
                                                                >
                                                                    <Settings className="w-3 h-3 text-green-500" />
                                                                    <div className="flex-1 min-w-0">
                                                                        <div className="text-sm font-medium truncate">{action.name}</div>
                                                                        <div className="text-[10px] text-gray-500 truncate">{action.description}</div>
                                                                    </div>
                                                                    <Plus className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100" />
                                                                </button>
                                                            ))}
                                                        </>
                                                    )}

                                                    {/* Connect button if not connected */}
                                                    {!isConnected && (
                                                        <button
                                                            onClick={() => window.open(`/integrations/${piece.id}`, '_blank')}
                                                            className="w-full flex items-center justify-center gap-1 px-2 py-1.5 mt-1 text-xs text-blue-600 hover:bg-blue-50 rounded"
                                                        >
                                                            <Plus className="w-3 h-3" />
                                                            Connect {piece.name}
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        );
                    })}

                    {filteredPieces.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                            <p className="text-sm">No pieces found</p>
                            <p className="text-xs">Try a different search term</p>
                        </div>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};

export default PiecesSidebar;
export { PIECES, CATEGORY_LABELS, CATEGORY_ICONS };
