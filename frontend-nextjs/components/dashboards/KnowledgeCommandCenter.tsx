import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
    FileText, Search, Folder, Download, ExternalLink, HardDrive,
    Filter, Clock, CheckCircle2, Ticket, DollarSign, User, AlertCircle, MessageSquare
} from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { CommentSection } from '@/components/shared/CommentSection';
import { cn } from '@/lib/utils';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useToast } from '@/components/ui/use-toast';

interface KnowledgeItem {
    id: string;
    name: string;
    platform: string;
    type: 'file' | 'task' | 'deal' | 'ticket';
    modified_at?: string;
    status?: string;
    value?: number;
    priority?: string;
}

interface SmartInsight {
    anomaly_id: string;
    severity: 'critical' | 'warning' | 'info';
    title: string;
    description: string;
    affected_entities: string[];
    platforms: string[];
    recommendation: string;
    timestamp: string;
}

export const KnowledgeCommandCenter: React.FC = () => {
    const [items, setItems] = useState<KnowledgeItem[]>([]);
    const [insights, setInsights] = useState<SmartInsight[]>([]);
    const [loading, setLoading] = useState(true);
    const [insightsLoading, setInsightsLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [activeType, setActiveType] = useState<string>('all');
    const [activePlatform, setActivePlatform] = useState<string>('all');
    const { toast: uiToast } = useToast();
    const { lastMessage, isConnected } = useWebSocket({ workspaceId: 'demo-workspace' });

    const fetchKnowledge = async () => {
        try {
            setLoading(true);
            const response = await axios.get<{ status: string, entities: any[] }>('/api/intelligence/entities');
            if (response.data?.status === 'success') {
                const mappedItems: KnowledgeItem[] = response.data.entities.map(e => ({
                    id: e.id,
                    name: e.name,
                    platform: e.platforms[0] || 'unknown',
                    type: e.type,
                    status: e.status,
                    value: e.value,
                    modified_at: e.modified_at
                }));
                setItems(mappedItems);
            }
        } catch (error) {
            console.error('Failed to fetch knowledge:', error);
            toast.error('Failed to fetch real-time intelligence data');
        } finally {
            setLoading(false);
        }
    };

    const fetchInsights = async () => {
        try {
            setInsightsLoading(true);
            const response = await axios.get<{ status: string, insights: SmartInsight[] }>('/api/intelligence/insights');
            if (response.data?.status === 'success') {
                setInsights(response.data.insights);
            }
        } catch (error) {
            console.error('Failed to fetch insights:', error);
        } finally {
            setInsightsLoading(false);
        }
    };

    useEffect(() => {
        fetchKnowledge();
        fetchInsights();
    }, []);

    // Listen for real-time critical alerts
    useEffect(() => {
        if (lastMessage && lastMessage.type === 'urgent_alert') {
            toast.error(lastMessage.message, {
                duration: 5000,
            });
            // Refresh insights as well
            fetchInsights();
        }
    }, [lastMessage]);

    const getTypeIcon = (type: string) => {
        switch (type) {
            case 'file': return <FileText className="w-4 h-4 text-primary" />;
            case 'task': return <CheckCircle2 className="w-4 h-4 text-blue-400" />;
            case 'deal': return <DollarSign className="w-4 h-4 text-green-400" />;
            case 'ticket': return <Ticket className="w-4 h-4 text-orange-400" />;
            default: return <FileText className="w-4 h-4" />;
        }
    };

    const getPlatformBadge = (platform: string) => {
        const colors: Record<string, string> = {
            gdrive: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
            jira: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
            salesforce: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
            zendesk: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
            zoho_workdrive: 'bg-red-500/10 text-red-400 border-red-500/20',
            asana: 'bg-rose-500/10 text-rose-400 border-rose-500/20'
        };
        return (
            <Badge variant="outline" className={cn("text-[10px] uppercase font-bold", colors[platform] || 'bg-white/5')}>
                {platform.replace('_', ' ')}
            </Badge>
        );
    };

    const filteredItems = items.filter(item => {
        const matchesSearch = item.name.toLowerCase().includes(search.toLowerCase());
        const matchesType = activeType === 'all' || item.type === activeType;
        const matchesPlatform = activePlatform === 'all' || item.platform === activePlatform;
        return matchesSearch && matchesType && matchesPlatform;
    });

    const stats = {
        total: items.length,
        files: items.filter(i => i.type === 'file').length,
        tasks: items.filter(i => i.type === 'task').length,
        critical: items.filter(i => i.priority === 'High' || i.status === 'Urgent').length
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in duration-700">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Global Intelligence Hub
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Cross-platform knowledge search and business intelligence.
                    </p>
                </div>
                <div className="flex gap-3 text-white items-center">
                    <button
                        className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-primary text-xs font-bold hover:bg-primary/10 transition-colors uppercase"
                        onClick={() => toast.success('Redirecting to Atom Agent for knowledge query...')}
                    >
                        <MessageSquare className="w-3 h-3" />
                        Ask Atom
                    </button>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Deep search across all systems..."
                            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-96 text-white"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-3 space-y-6">
                    {/* Filter Bar */}
                    <div className="flex flex-wrap gap-2 items-center bg-white/5 p-2 rounded-xl border border-white/5">
                        <div className="flex bg-black/40 p-1 rounded-lg border border-white/5 mr-2">
                            {['all', 'file', 'task', 'deal', 'ticket'].map(type => (
                                <button
                                    key={type}
                                    onClick={() => setActiveType(type)}
                                    className={cn(
                                        "px-3 py-1 text-xs rounded-md transition-all uppercase font-semibold",
                                        activeType === type ? "bg-primary text-white" : "text-muted-foreground hover:text-white"
                                    )}
                                >
                                    {type}s
                                </button>
                            ))}
                        </div>
                        <select
                            value={activePlatform}
                            onChange={(e) => setActivePlatform(e.target.value)}
                            className="bg-black/40 border border-white/10 rounded-lg px-3 py-1 text-xs text-white focus:outline-none"
                        >
                            <option value="all">All Platforms</option>
                            <option value="gdrive">Google Drive</option>
                            <option value="jira">Jira</option>
                            <option value="salesforce">Salesforce</option>
                            <option value="zendesk">Zendesk</option>
                            <option value="zoho_workdrive">Zoho</option>
                        </select>
                        <div className="flex-1" />
                        <button
                            onClick={() => { setActiveType('all'); setActivePlatform('all'); setSearch('') }}
                            className="text-[10px] text-muted-foreground hover:text-white uppercase font-bold"
                        >
                            Reset
                        </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Global Objects</CardTitle>
                                <HardDrive className="w-4 h-4 text-blue-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.total}</div>
                                <p className="text-xs text-muted-foreground mt-1">Across 6 platforms</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Tasks</CardTitle>
                                <CheckCircle2 className="w-4 h-4 text-green-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.tasks}</div>
                                <p className="text-xs text-muted-foreground mt-1">Found in global scan</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Critical Alerts</CardTitle>
                                <AlertCircle className="w-4 h-4 text-red-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.critical + insights.filter(i => i.severity === 'critical').length}</div>
                                <p className="text-xs text-muted-foreground mt-1">Requiring action</p>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Smart Insights Panel */}
                    {insights.length > 0 && (
                        <div className="animate-in slide-in-from-top duration-500">
                            <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20 backdrop-blur-xl overflow-hidden">
                                <CardHeader className="pb-2 border-b border-white/5 bg-white/5">
                                    <div className="flex justify-between items-center">
                                        <CardTitle className="text-xs font-bold text-primary uppercase tracking-tighter flex items-center gap-2">
                                            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                                            Smart Intelligence Insights
                                        </CardTitle>
                                        <Badge className="bg-primary/20 text-primary border-primary/30 text-[9px]">AI POWERED</Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {insights.slice(0, 2).map((insight, idx) => (
                                            <div key={idx} className="bg-black/40 border border-white/5 p-4 rounded-xl space-y-3 relative group overflow-hidden transition-all hover:border-primary/30">
                                                <div className={cn(
                                                    "absolute top-0 right-0 w-1 h-full",
                                                    insight.severity === 'critical' ? 'bg-red-500' : 'bg-orange-500'
                                                )} />
                                                <div className="flex justify-between items-start gap-2">
                                                    <h3 className="font-bold text-sm text-white group-hover:text-primary transition-colors">{insight.title}</h3>
                                                    <Badge variant="outline" className={cn(
                                                        "text-[9px] uppercase",
                                                        insight.severity === 'critical' ? 'text-red-400 border-red-500/20' : 'text-orange-400 border-orange-500/20'
                                                    )}>
                                                        {insight.severity}
                                                    </Badge>
                                                </div>
                                                <p className="text-xs text-muted-foreground leading-relaxed">{insight.description}</p>
                                                <div className="p-2 bg-white/5 rounded-lg border border-white/5">
                                                    <p className="text-[10px] text-white/70 italic font-medium">💡 Recommendation: {insight.recommendation}</p>
                                                </div>
                                                <div className="flex justify-between items-center pt-2">
                                                    <div className="flex gap-1">
                                                        {insight.platforms.map((p, i) => (
                                                            <span key={i} className="text-[9px] px-1.5 py-0.5 bg-white/5 rounded border border-white/10 text-muted-foreground uppercase font-bold">{p}</span>
                                                        ))}
                                                    </div>
                                                    <button className="text-[10px] text-primary hover:underline font-bold uppercase tracking-tighter">Take Action</button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    <Card className="bg-black/40 border-white/5 backdrop-blur-xl overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="bg-white/5 text-muted-foreground">
                                    <tr>
                                        <th className="px-6 py-4 font-semibold uppercase text-[10px]">Title / Name</th>
                                        <th className="px-6 py-4 font-semibold uppercase text-[10px]">Type</th>
                                        <th className="px-6 py-4 font-semibold uppercase text-[10px]">Platform</th>
                                        <th className="px-6 py-4 font-semibold uppercase text-[10px]">Status / Value</th>
                                        <th className="px-6 py-4 font-semibold uppercase text-[10px]">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {filteredItems.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                                                No intelligence found matching your criteria.
                                            </td>
                                        </tr>
                                    ) : filteredItems.map(item => (
                                        <tr key={item.id} className="hover:bg-white/5 transition-colors group text-white">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    {getTypeIcon(item.type)}
                                                    <span className="font-medium group-hover:text-primary transition-colors">{item.name}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="text-xs text-muted-foreground capitalize">{item.type}</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                {getPlatformBadge(item.platform)}
                                            </td>
                                            <td className="px-6 py-4">
                                                {item.type === 'deal' ? (
                                                    <span className="text-green-400 font-mono font-semibold">${item.value?.toLocaleString()}</span>
                                                ) : item.status ? (
                                                    <Badge variant="outline" className="text-[10px] bg-white/5">{item.status}</Badge>
                                                ) : (
                                                    <span className="text-muted-foreground text-xs">{item.modified_at}</span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex gap-4">
                                                    <button
                                                        className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 group/btn"
                                                        title="Ask Atom about this"
                                                        onClick={() => toast.success(`Asking Atom about ${item.name}...`)}
                                                    >
                                                        <MessageSquare className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />
                                                        <span className="text-[10px] hidden group-hover:inline uppercase font-bold text-primary">Ask</span>
                                                    </button>
                                                    <button className="text-muted-foreground hover:text-white transition-colors">
                                                        <ExternalLink className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Card>
                </div>

                <div className="lg:col-span-1 h-[600px] lg:h-[calc(100vh-200px)] sticky top-6">
                    <CommentSection channel="knowledge" title="Intelligence Collab" />
                </div>
            </div>
        </div>
    );
};

export default KnowledgeCommandCenter;
