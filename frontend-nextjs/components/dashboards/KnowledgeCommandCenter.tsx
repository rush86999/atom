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

export const KnowledgeCommandCenter: React.FC = () => {
    const [items, setItems] = useState<KnowledgeItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [activeType, setActiveType] = useState<string>('all');
    const [activePlatform, setActivePlatform] = useState<string>('all');

    const fetchKnowledge = async () => {
        try {
            setLoading(true);
            const mockResults: KnowledgeItem[] = [
                { id: '1', name: 'Product Strategy 2024.pdf', platform: 'gdrive', type: 'file', modified_at: '2023-12-25' },
                { id: 'j1', name: 'Fix backend timeout bug', platform: 'jira', type: 'task', status: 'In Progress', modified_at: '2023-12-26' },
                { id: 'sf1', name: 'Enterprise License - Acme Corp', platform: 'salesforce', type: 'deal', value: 85000, status: 'Negotiation' },
                { id: 'zd1', name: 'Login issue reporting', platform: 'zendesk', type: 'ticket', status: 'Open', priority: 'High' },
                { id: '3', name: 'Design Assets - Phase 14', platform: 'zoho_workdrive', type: 'file', modified_at: '2023-12-27' },
                { id: 'a1', name: 'Update documentation', platform: 'asana', type: 'task', status: 'To Do', modified_at: '2023-12-28' }
            ];

            setItems(mockResults);
        } catch (error) {
            console.error('Failed to fetch knowledge:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchKnowledge();
    }, []);

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
                                <div className="text-2xl font-bold text-white">{stats.critical}</div>
                                <p className="text-xs text-muted-foreground mt-1">Requiring attention</p>
                            </CardContent>
                        </Card>
                    </div>

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
