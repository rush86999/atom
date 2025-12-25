'use client';

import React, { useState, useMemo } from 'react';
import {
    Search, Zap, Star, Clock, Users, TrendingUp, Mail, Calendar,
    MessageSquare, FileText, Database, ShoppingCart, Headphones,
    Sparkles, ArrowRight, Copy, Eye, Heart, Filter
} from 'lucide-react';
import { FaSlack, FaGoogle, FaGithub, FaSalesforce, FaHubspot } from 'react-icons/fa';
import { SiNotion, SiAsana, SiStripe } from 'react-icons/si';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Template definition
export interface WorkflowTemplate {
    id: string;
    name: string;
    description: string;
    category: 'sales' | 'marketing' | 'support' | 'hr' | 'engineering' | 'finance' | 'productivity' | 'ai';
    difficulty: 'beginner' | 'intermediate' | 'advanced';
    estimatedTime: string;
    uses: number;
    rating: number;
    services: string[];
    steps: number;
    trigger: string;
    featured?: boolean;
    new?: boolean;
}

// Pre-built templates catalog
const TEMPLATES: WorkflowTemplate[] = [
    // Sales Templates
    {
        id: 'lead-to-slack',
        name: 'New Lead Notification',
        description: 'Get instant Slack notifications when new leads come in from any source',
        category: 'sales',
        difficulty: 'beginner',
        estimatedTime: '5 min',
        uses: 12500,
        rating: 4.9,
        services: ['HubSpot', 'Slack'],
        steps: 3,
        trigger: 'New Contact in HubSpot',
        featured: true,
    },
    {
        id: 'lead-enrichment',
        name: 'AI Lead Enrichment',
        description: 'Automatically enrich new leads with company data and AI-generated insights',
        category: 'sales',
        difficulty: 'intermediate',
        estimatedTime: '15 min',
        uses: 8200,
        rating: 4.8,
        services: ['Salesforce', 'OpenAI', 'Clearbit'],
        steps: 6,
        trigger: 'New Lead in Salesforce',
        featured: true,
    },
    {
        id: 'deal-stage-alerts',
        name: 'Deal Stage Change Alerts',
        description: 'Notify team members when deals move between pipeline stages',
        category: 'sales',
        difficulty: 'beginner',
        estimatedTime: '10 min',
        uses: 5600,
        rating: 4.7,
        services: ['HubSpot', 'Slack', 'Email'],
        steps: 4,
        trigger: 'Deal Stage Changed',
    },

    // Marketing Templates
    {
        id: 'social-to-notion',
        name: 'Social Mentions to Notion',
        description: 'Track brand mentions across social media and organize in Notion',
        category: 'marketing',
        difficulty: 'intermediate',
        estimatedTime: '20 min',
        uses: 3200,
        rating: 4.6,
        services: ['Twitter', 'Notion'],
        steps: 5,
        trigger: 'New Mention',
    },
    {
        id: 'newsletter-automation',
        name: 'Newsletter Subscriber Welcome',
        description: 'Send personalized welcome emails and add to CRM when someone subscribes',
        category: 'marketing',
        difficulty: 'beginner',
        estimatedTime: '10 min',
        uses: 9800,
        rating: 4.8,
        services: ['Mailchimp', 'HubSpot'],
        steps: 4,
        trigger: 'New Subscriber',
        featured: true,
    },

    // Support Templates  
    {
        id: 'ticket-triage',
        name: 'AI Ticket Triage',
        description: 'Automatically categorize and prioritize support tickets using AI',
        category: 'support',
        difficulty: 'intermediate',
        estimatedTime: '15 min',
        uses: 7400,
        rating: 4.9,
        services: ['Zendesk', 'OpenAI', 'Slack'],
        steps: 5,
        trigger: 'New Support Ticket',
        featured: true,
        new: true,
    },
    {
        id: 'customer-feedback',
        name: 'Customer Feedback Loop',
        description: 'Collect NPS responses and route to appropriate teams',
        category: 'support',
        difficulty: 'beginner',
        estimatedTime: '10 min',
        uses: 4100,
        rating: 4.5,
        services: ['Typeform', 'Slack', 'Asana'],
        steps: 4,
        trigger: 'New Survey Response',
    },

    // Engineering Templates
    {
        id: 'github-slack',
        name: 'GitHub PR Notifications',
        description: 'Get Slack notifications for new PRs, reviews, and merges',
        category: 'engineering',
        difficulty: 'beginner',
        estimatedTime: '5 min',
        uses: 15200,
        rating: 4.9,
        services: ['GitHub', 'Slack'],
        steps: 3,
        trigger: 'New Pull Request',
    },
    {
        id: 'deploy-notify',
        name: 'Deployment Announcements',
        description: 'Announce successful deployments to team channels',
        category: 'engineering',
        difficulty: 'intermediate',
        estimatedTime: '15 min',
        uses: 6300,
        rating: 4.7,
        services: ['GitHub', 'Slack', 'Discord'],
        steps: 4,
        trigger: 'Workflow Completed',
    },

    // HR Templates
    {
        id: 'onboarding',
        name: 'Employee Onboarding',
        description: 'Automate new hire onboarding with scheduled tasks and notifications',
        category: 'hr',
        difficulty: 'advanced',
        estimatedTime: '30 min',
        uses: 4800,
        rating: 4.8,
        services: ['BambooHR', 'Slack', 'Google Calendar', 'Asana'],
        steps: 8,
        trigger: 'New Employee Added',
    },

    // Productivity Templates
    {
        id: 'meeting-notes',
        name: 'AI Meeting Notes',
        description: 'Automatically transcribe meetings and create summaries in Notion',
        category: 'productivity',
        difficulty: 'intermediate',
        estimatedTime: '15 min',
        uses: 11200,
        rating: 4.9,
        services: ['Zoom', 'OpenAI', 'Notion'],
        steps: 5,
        trigger: 'Meeting Ended',
        featured: true,
        new: true,
    },
    {
        id: 'daily-digest',
        name: 'Daily Task Digest',
        description: 'Get a morning summary of your tasks across all apps',
        category: 'productivity',
        difficulty: 'beginner',
        estimatedTime: '10 min',
        uses: 8900,
        rating: 4.7,
        services: ['Asana', 'Trello', 'Email'],
        steps: 4,
        trigger: 'Schedule (Daily)',
    },

    // AI Templates
    {
        id: 'content-generator',
        name: 'AI Content Generator',
        description: 'Generate blog posts, social content, and emails from prompts',
        category: 'ai',
        difficulty: 'intermediate',
        estimatedTime: '20 min',
        uses: 6700,
        rating: 4.6,
        services: ['OpenAI', 'Notion', 'Buffer'],
        steps: 6,
        trigger: 'Manual or Schedule',
        new: true,
    },
    {
        id: 'data-analysis',
        name: 'AI Data Analyst',
        description: 'Analyze spreadsheet data and generate insights automatically',
        category: 'ai',
        difficulty: 'advanced',
        estimatedTime: '25 min',
        uses: 3400,
        rating: 4.5,
        services: ['Google Sheets', 'OpenAI', 'Slack'],
        steps: 7,
        trigger: 'New Row Added',
    },
];

const CATEGORY_CONFIG: Record<string, { icon: React.ComponentType<any>; label: string; color: string }> = {
    sales: { icon: TrendingUp, label: 'Sales', color: 'bg-blue-100 text-blue-700' },
    marketing: { icon: Mail, label: 'Marketing', color: 'bg-pink-100 text-pink-700' },
    support: { icon: Headphones, label: 'Support', color: 'bg-green-100 text-green-700' },
    hr: { icon: Users, label: 'HR', color: 'bg-purple-100 text-purple-700' },
    engineering: { icon: FileText, label: 'Engineering', color: 'bg-gray-100 text-gray-700' },
    finance: { icon: Database, label: 'Finance', color: 'bg-yellow-100 text-yellow-700' },
    productivity: { icon: Calendar, label: 'Productivity', color: 'bg-indigo-100 text-indigo-700' },
    ai: { icon: Sparkles, label: 'AI', color: 'bg-violet-100 text-violet-700' },
};

const SERVICE_ICONS: Record<string, React.ComponentType<any>> = {
    'Slack': FaSlack,
    'HubSpot': FaHubspot,
    'Salesforce': FaSalesforce,
    'GitHub': FaGithub,
    'Google Sheets': FaGoogle,
    'Notion': SiNotion,
    'Asana': SiAsana,
    'Stripe': SiStripe,
};

interface TemplateGalleryProps {
    onUseTemplate?: (template: WorkflowTemplate) => void;
    className?: string;
}

const TemplateGallery: React.FC<TemplateGalleryProps> = ({ onUseTemplate, className }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

    // Filter templates
    const filteredTemplates = useMemo(() => {
        let result = TEMPLATES;

        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            result = result.filter(t =>
                t.name.toLowerCase().includes(query) ||
                t.description.toLowerCase().includes(query) ||
                t.services.some(s => s.toLowerCase().includes(query))
            );
        }

        if (selectedCategory) {
            result = result.filter(t => t.category === selectedCategory);
        }

        return result;
    }, [searchQuery, selectedCategory]);

    // Featured templates
    const featuredTemplates = TEMPLATES.filter(t => t.featured);

    const handleUseTemplate = (template: WorkflowTemplate) => {
        onUseTemplate?.(template);
    };

    return (
        <div className={cn("flex flex-col h-full bg-gray-50", className)}>
            {/* Header */}
            <div className="bg-gradient-to-r from-violet-600 to-indigo-600 text-white p-8">
                <h1 className="text-3xl font-bold mb-2">Workflow Templates</h1>
                <p className="text-violet-100 mb-6">
                    Get started in minutes with pre-built automations. Just connect your apps and go!
                </p>
                <div className="flex gap-4 max-w-2xl">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                        <Input
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search templates..."
                            className="pl-11 bg-white text-gray-900 border-0 h-12"
                        />
                    </div>
                </div>
            </div>

            {/* Category Filter */}
            <div className="bg-white border-b px-8 py-4 flex gap-2 flex-wrap">
                <Button
                    size="sm"
                    variant={selectedCategory === null ? 'default' : 'outline'}
                    onClick={() => setSelectedCategory(null)}
                >
                    All
                </Button>
                {Object.entries(CATEGORY_CONFIG).map(([key, config]) => {
                    const Icon = config.icon;
                    return (
                        <Button
                            key={key}
                            size="sm"
                            variant={selectedCategory === key ? 'default' : 'outline'}
                            onClick={() => setSelectedCategory(key)}
                        >
                            <Icon className="w-4 h-4 mr-1" />
                            {config.label}
                        </Button>
                    );
                })}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-8">
                {/* Featured Section */}
                {!searchQuery && !selectedCategory && (
                    <div className="mb-10">
                        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                            <Star className="w-5 h-5 text-yellow-500" />
                            Featured Templates
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {featuredTemplates.slice(0, 3).map(template => (
                                <TemplateCard
                                    key={template.id}
                                    template={template}
                                    onUse={handleUseTemplate}
                                    featured
                                />
                            ))}
                        </div>
                    </div>
                )}

                {/* All Templates */}
                <div>
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-bold">
                            {selectedCategory
                                ? `${CATEGORY_CONFIG[selectedCategory]?.label} Templates`
                                : 'All Templates'}
                        </h2>
                        <span className="text-sm text-gray-500">
                            {filteredTemplates.length} template{filteredTemplates.length !== 1 ? 's' : ''}
                        </span>
                    </div>

                    {filteredTemplates.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {filteredTemplates.map(template => (
                                <TemplateCard
                                    key={template.id}
                                    template={template}
                                    onUse={handleUseTemplate}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-gray-500">
                            <Search className="w-12 h-12 mx-auto mb-3 opacity-30" />
                            <p className="font-medium">No templates found</p>
                            <p className="text-sm">Try a different search term or category</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// Template Card Component
const TemplateCard: React.FC<{
    template: WorkflowTemplate;
    onUse: (t: WorkflowTemplate) => void;
    featured?: boolean;
}> = ({ template, onUse, featured }) => {
    const categoryConfig = CATEGORY_CONFIG[template.category];
    const CategoryIcon = categoryConfig?.icon || Zap;

    return (
        <Card className={cn(
            "hover:shadow-lg transition-shadow cursor-pointer group",
            featured && "border-2 border-violet-200 bg-gradient-to-br from-violet-50 to-white"
        )}>
            <CardHeader className="pb-2">
                <div className="flex justify-between items-start mb-2">
                    <Badge className={cn("text-xs", categoryConfig?.color)}>
                        <CategoryIcon className="w-3 h-3 mr-1" />
                        {categoryConfig?.label}
                    </Badge>
                    <div className="flex gap-1">
                        {template.new && (
                            <Badge className="bg-green-100 text-green-700 text-[10px]">NEW</Badge>
                        )}
                        {template.featured && (
                            <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                        )}
                    </div>
                </div>
                <CardTitle className="text-base leading-tight">{template.name}</CardTitle>
            </CardHeader>

            <CardContent className="pb-2">
                <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                    {template.description}
                </p>

                {/* Services */}
                <div className="flex flex-wrap gap-1 mb-3">
                    {template.services.slice(0, 3).map(service => {
                        const Icon = SERVICE_ICONS[service];
                        return (
                            <Badge key={service} variant="secondary" className="text-[10px] py-0.5">
                                {Icon && <Icon className="w-3 h-3 mr-1" />}
                                {service}
                            </Badge>
                        );
                    })}
                    {template.services.length > 3 && (
                        <Badge variant="secondary" className="text-[10px] py-0.5">
                            +{template.services.length - 3}
                        </Badge>
                    )}
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {template.estimatedTime}
                    </span>
                    <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {template.steps} steps
                    </span>
                    <span className="flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        {template.uses.toLocaleString()}
                    </span>
                </div>
            </CardContent>

            <CardFooter className="pt-2">
                <Button
                    className="w-full group-hover:bg-violet-600 group-hover:text-white transition-colors"
                    variant="outline"
                    onClick={() => onUse(template)}
                >
                    Use Template
                    <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
            </CardFooter>
        </Card>
    );
};

export default TemplateGallery;
export { TEMPLATES };
