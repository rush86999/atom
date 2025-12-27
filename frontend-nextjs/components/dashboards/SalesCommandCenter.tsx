import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DollarSign, Search, TrendingUp, Users, Zap, Building2, ArrowUpRight } from 'lucide-react';
import axios from 'axios';
import { CommentSection } from '@/components/shared/CommentSection';

interface Deal {
    deal: string;
    value: number;
    status: string;
    platform: 'salesforce' | 'hubspot' | 'zoho';
    company?: string;
}

export const SalesCommandCenter: React.FC = () => {
    const [deals, setDeals] = useState<Deal[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setDeals([
            { deal: 'Global Logistics Expansion', value: 85000, status: 'Negotiation', platform: 'salesforce', company: 'LogiCorp' },
            { deal: 'Software Suite V3', value: 32000, status: 'Qualified', platform: 'hubspot', company: 'TechStart' },
            { deal: 'Q4 Consulting Contract', value: 15000, status: 'Closed Won', platform: 'salesforce', company: 'BuildIt' },
            { deal: 'Infrastructure Upgrade', value: 120000, status: 'Discovery', platform: 'hubspot', company: 'CloudNet' }
        ]);
        setLoading(false);
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
                                <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
                                    <p className="text-sm font-medium text-primary">Opportunity Found</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        LogiCorp recently expanded their headcount by 20%. Potential for upsell on the Logistics deal.
                                    </p>
                                </div>
                                <div className="p-4 rounded-lg bg-orange-500/5 border border-orange-500/10">
                                    <p className="text-sm font-medium text-orange-400">Churn Risk</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        CloudNet hasn't logged into the support portal in 14 days.
                                    </p>
                                </div>
                                <button className="w-full py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors border border-white/10 text-white">
                                    View Full Insights
                                </button>
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
