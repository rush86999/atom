import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DollarSign, Search, TrendingUp, Users, Zap, Building2, ArrowUpRight } from 'lucide-react';
import axios from 'axios';
import { useRouter } from 'next/router';
import { toast } from 'sonner';
import { CommentSection } from '@/components/shared/CommentSection';

interface Deal {
    deal: string;
    value: number;
    status: string;
    platform: 'salesforce' | 'hubspot' | 'zoho';
    company?: string;
}

interface Insight {
    anomaly_id: string;
    severity: 'critical' | 'warning' | 'info';
    title: string;
    description: string;
    recommendation: string;
    action_type?: string;
    action_payload?: any;
}

export const SalesCommandCenter: React.FC = () => {
    const router = useRouter();
    const [deals, setDeals] = useState<Deal[]>([]);
    const [insights, setInsights] = useState<Insight[]>([]);
    const [loading, setLoading] = useState(true);
    const [executing, setExecuting] = useState<string | null>(null);

    const fetchDeals = async () => {
        try {
            setLoading(true);
            const response = await axios.get<Deal[]>('/api/sales/pipeline');
            setDeals(response.data);
        } catch (error) {
            console.error('Failed to fetch deals:', error);
            // Fallback for demo
            setDeals([
                { deal: 'Global Logistics Expansion (Mock)', value: 85000, status: 'Negotiation', platform: 'salesforce', company: 'LogiCorp' },
                { deal: 'Software Suite V3 (Mock)', value: 32000, status: 'Qualified', platform: 'hubspot', company: 'TechStart' }
            ]);
        } finally {
            setLoading(false);
        }
    };

    const fetchInsights = async () => {
        try {
            const response = await axios.get<{ insights: Insight[] }>('/api/intelligence/insights');
            setInsights(response.data.insights || []);
        } catch (error) {
            console.error('Failed to fetch insights:', error);
        }
    };

    const handleExecuteAction = async (insight: Insight) => {
        if (!insight.action_type || !insight.action_payload) return;

        // Custom handling for project deep-links
        if (insight.action_type === 'workflow' && insight.action_payload.workflow_id === 'escalate_deal_blocker') {
            const taskId = insight.action_payload.inputs?.task_id;
            if (taskId) {
                toast.info('Navigating to blocking task in Project Command Center...');
                router.push(`/projects?highlight=${taskId}`);
                return;
            }
        }

        try {
            setExecuting(insight.anomaly_id);
            await axios.post('/api/intelligence/execute', {
                action_type: insight.action_type,
                action_payload: insight.action_payload
            });
            toast.success(`Action executed: ${insight.title}`);
            // Refresh insights after action
            fetchInsights();
        } catch (error) {
            console.error('Action failed:', error);
            toast.error('Failed to execute resolution.');
        } finally {
            setExecuting(null);
        }
    };

    useEffect(() => {
        fetchDeals();
        fetchInsights();
    }, []);

    const totalPipeline = deals.reduce((acc, d) => acc + d.value, 0);

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Sales Command Center
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Aggregated CRM pipelines and lead intelligence.
                    </p>
                </div>
                <div className="flex gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search deals..."
                            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                        />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-3 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {[
                            { label: 'Total Pipeline', value: `$${(totalPipeline / 1000).toFixed(1)}k`, icon: DollarSign, color: 'text-green-400' },
                            { label: 'Active Deals', value: deals.length, icon: TrendingUp, color: 'text-blue-400' },
                            { label: 'Key Contacts', value: '142', icon: Users, color: 'text-purple-400' },
                            { label: 'Win Rate', value: '64%', icon: ArrowUpRight, color: 'text-amber-400' }
                        ].map((stat, i) => (
                            <Card key={i} className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-xs font-medium text-muted-foreground uppercase">{stat.label}</CardTitle>
                                    <stat.icon className={`w-4 h-4 ${stat.color}`} />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{stat.value}</div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <Card className="lg:col-span-2 bg-black/40 border-white/5 backdrop-blur-xl overflow-hidden">
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Building2 className="w-5 h-5 text-primary" />
                                    Recent Deals
                                </CardTitle>
                            </CardHeader>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="bg-white/5 text-muted-foreground">
                                        <tr>
                                            <th className="px-6 py-3 font-semibold uppercase text-[10px]">Deal Name</th>
                                            <th className="px-6 py-3 font-semibold uppercase text-[10px]">Value</th>
                                            <th className="px-6 py-3 font-semibold uppercase text-[10px]">Status</th>
                                            <th className="px-6 py-3 font-semibold uppercase text-[10px]">Source</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {deals.map((deal, i) => (
                                            <tr key={i} className="hover:bg-white/5 transition-colors group">
                                                <td className="px-6 py-4">
                                                    <div>
                                                        <div className="font-medium text-white">{deal.deal}</div>
                                                        <div className="text-xs text-muted-foreground">{deal.company}</div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 font-mono font-medium text-green-400">
                                                    ${deal.value.toLocaleString()}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <Badge variant="outline" className="bg-white/5 border-white/10">
                                                        {deal.status}
                                                    </Badge>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <Badge className={deal.platform === 'salesforce' ? 'bg-blue-600/20 text-blue-400' : 'bg-orange-600/20 text-orange-400'}>
                                                        {deal.platform}
                                                    </Badge>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>

                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-lg">Lead Intelligence</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {insights.length > 0 ? (
                                    insights.map((insight) => (
                                        <div
                                            key={insight.anomaly_id}
                                            className={`p-4 rounded-lg border transition-all duration-300 ${insight.severity === 'critical'
                                                ? 'bg-red-500/5 border-red-500/20'
                                                : insight.severity === 'warning'
                                                    ? 'bg-orange-500/5 border-orange-500/20'
                                                    : 'bg-primary/5 border-primary/20'
                                                }`}
                                        >
                                            <div className="flex justify-between items-start mb-1">
                                                <p className={`text-sm font-medium ${insight.severity === 'critical' ? 'text-red-400' : 'text-primary'
                                                    }`}>
                                                    {insight.title}
                                                </p>
                                                <Badge variant="outline" className="text-[9px] px-1 h-4 uppercase opacity-70">
                                                    {insight.severity}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
                                                {insight.description}
                                            </p>
                                            {insight.action_type && (
                                                <button
                                                    onClick={() => handleExecuteAction(insight)}
                                                    disabled={executing === insight.anomaly_id}
                                                    className="w-full py-1.5 bg-white/5 hover:bg-white/10 disabled:opacity-50 rounded-md text-[11px] font-semibold transition-all border border-white/10 flex items-center justify-center gap-2 group"
                                                >
                                                    {executing === insight.anomaly_id ? (
                                                        <div className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                                    ) : (
                                                        <Zap className="w-3 h-3 text-amber-400 group-hover:scale-110 transition-transform" />
                                                    )}
                                                    {insight.action_type === 'workflow' ? 'Resolve via Workflow' : 'Run Auto-Fix'}
                                                </button>
                                            )}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-center py-8 opacity-40">
                                        <Zap className="w-8 h-8 mx-auto mb-2" />
                                        <p className="text-xs">No critical anomalies detected</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                <div className="lg:col-span-1 h-[600px] lg:h-[calc(100vh-200px)] sticky top-6">
                    <CommentSection channel="sales" title="Sales Collab" />
                </div>
            </div>
        </div>
    );
};

export default SalesCommandCenter;
