import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DollarSign, TrendingUp, CreditCard, Activity, Search, RefreshCw, AlertCircle, X, Clock } from 'lucide-react';
import { useLiveFinance, UnifiedTransaction } from '@/hooks/useLiveFinance';
import { useMemorySearch } from '@/hooks/useMemorySearch';
import { CommentSection } from '@/components/shared/CommentSection';
import { PipelineSettingsPanel } from '@/components/shared/PipelineSettingsPanel';
import { toast } from 'sonner';

import { useWebSocket } from '@/hooks/useWebSocket';

export const FinanceCommandCenter: React.FC = () => {
    const { transactions, stats, isLoading, activeProviders, refresh } = useLiveFinance();
    const [showSettings, setShowSettings] = useState(false);

    // WebSocket for Real-Time Sync Refreshes
    const { lastMessage } = useWebSocket({
        initialChannels: ['communication_stats']
    });

    useEffect(() => {
        if (lastMessage && lastMessage.type === 'status_update') {
            toast.info('Sync complete: Refreshing finance data...');
            refresh();
        }
    }, [lastMessage, refresh]);

    // Unified Search
    const [searchQuery, setSearchQuery] = useState('');
    const [showSearchResults, setShowSearchResults] = useState(false);
    const { results: searchResults, isSearching, searchMemory, clearSearch } = useMemorySearch({ tag: 'finance' });

    const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
        const query = e.target.value;
        setSearchQuery(query);
        if (query.length > 2) {
            searchMemory(query);
            setShowSearchResults(true);
        } else {
            setShowSearchResults(false);
            clearSearch();
        }
    };

    const formatCurrency = (amount: number, currency: string = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency.toUpperCase(),
        }).format(amount);
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in duration-700">
            {/* Header */}
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Finance Command Center
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Real-time financial aggregator (Stripe, Xero, QuickBooks).
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowSettings(!showSettings)}
                        className="bg-white/5 border-white/10"
                    >
                        <RefreshCw className={`w-4 h-4 mr-2`} />
                        Sync Settings
                    </Button>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search transactions..."
                            className="pl-10 pr-10 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                            value={searchQuery}
                            onChange={handleSearch}
                        />
                        {searchQuery && (
                            <button
                                onClick={() => { setSearchQuery(''); setShowSearchResults(false); clearSearch(); }}
                                className="absolute right-3 top-1/2 -translate-y-1/2"
                            >
                                <X className="w-4 h-4 text-muted-foreground hover:text-white" />
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <PipelineSettingsPanel isOpen={showSettings} />

            {showSearchResults ? (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold text-white">Search Results for "{searchQuery}"</h2>
                        <button onClick={() => { setShowSearchResults(false); setSearchQuery(''); clearSearch(); }} className="text-sm text-primary hover:underline">Clear Search</button>
                    </div>
                    {isSearching ? (
                        <div className="flex items-center gap-2 text-muted-foreground"><Clock className="w-4 h-4 animate-spin" /> Searching memory...</div>
                    ) : searchResults.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {searchResults.map((result) => (
                                <Card key={result.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors pointer-cursor">
                                    <CardContent className="p-4">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="capitalize text-[10px]">{result.app_type}</Badge>
                                                <span className="font-semibold text-white">{result.subject || result.sender}</span>
                                            </div>
                                            <span className="text-xs text-muted-foreground">{new Date(result.timestamp).toLocaleString()}</span>
                                        </div>
                                        <p className="text-sm text-gray-300 line-clamp-2">{result.content}</p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-white/10 rounded-xl">No historical records found for "{searchQuery}".</div>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Main Content Area */}
                    <div className="lg:col-span-3 space-y-6">

                        {/* Stats Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-xs font-medium text-muted-foreground uppercase">Total Revenue</CardTitle>
                                    <DollarSign className="w-4 h-4 text-green-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">
                                        {formatCurrency(stats.total_revenue)}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1">Unified Revenue Stream</p>
                                </CardContent>
                            </Card>

                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-xs font-medium text-muted-foreground uppercase">Pending</CardTitle>
                                    <Activity className="w-4 h-4 text-amber-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">
                                        {formatCurrency(stats.pending_revenue)}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1">Unpaid Invoices</p>
                                </CardContent>
                            </Card>

                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-xs font-medium text-muted-foreground uppercase">Transactions</CardTitle>
                                    <CreditCard className="w-4 h-4 text-blue-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">
                                        {stats.transaction_count}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1">Last 30 Days</p>
                                </CardContent>
                            </Card>

                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-xs font-medium text-muted-foreground uppercase">Active Sources</CardTitle>
                                    <TrendingUp className="w-4 h-4 text-purple-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white flex gap-2">
                                        {Object.keys(activeProviders).length}
                                    </div>
                                    <div className="flex gap-1 mt-1">
                                        {activeProviders.stripe && <Badge variant="outline" className="text-[10px] bg-indigo-500/10 text-indigo-400 border-indigo-500/20">Stripe</Badge>}
                                        {activeProviders.xero && <Badge variant="outline" className="text-[10px] bg-sky-500/10 text-sky-400 border-sky-500/20">Xero</Badge>}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Transactions List */}
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl overflow-hidden min-h-[400px]">
                            <CardHeader>
                                <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Recent Transactions</CardTitle>
                            </CardHeader>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="bg-white/5 text-muted-foreground text-xs uppercase">
                                        <tr>
                                            <th className="px-6 py-3 font-semibold">Description</th>
                                            <th className="px-6 py-3 font-semibold">Amount</th>
                                            <th className="px-6 py-3 font-semibold">Date</th>
                                            <th className="px-6 py-3 font-semibold">Source</th>
                                            <th className="px-6 py-3 font-semibold">Status</th>
                                            <th className="px-6 py-3 font-semibold">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {isLoading ? (
                                            Array.from({ length: 5 }).map((_, i) => (
                                                <tr key={i} className="animate-pulse">
                                                    <td colSpan={6} className="px-6 py-4 h-12 bg-white/2" />
                                                </tr>
                                            ))
                                        ) : transactions.filter(tx => tx.description.toLowerCase().includes(searchQuery.toLowerCase())).length > 0 ? (
                                            transactions.filter(tx => tx.description.toLowerCase().includes(searchQuery.toLowerCase())).map((tx) => (
                                                <tr key={tx.id} className="hover:bg-white/5 transition-colors group">
                                                    <td className="px-6 py-4">
                                                        <div className="font-medium text-white">{tx.description}</div>
                                                        {tx.customer_name && <div className="text-xs text-muted-foreground">{tx.customer_name}</div>}
                                                    </td>
                                                    <td className="px-6 py-4 font-mono font-medium">
                                                        {formatCurrency(tx.amount, tx.currency)}
                                                    </td>
                                                    <td className="px-6 py-4 text-muted-foreground">
                                                        {new Date(tx.date).toLocaleDateString()}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <Badge variant="outline" className={`capitalize 
                                                             ${tx.platform === 'stripe' ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20' :
                                                                tx.platform === 'xero' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' :
                                                                    'bg-white/5 text-muted-foreground'}`}>
                                                            {tx.platform}
                                                        </Badge>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium 
                                                            ${tx.status === 'succeeded' || tx.status === 'paid' ? 'bg-green-500/10 text-green-400' :
                                                                tx.status === 'pending' || tx.status === 'open' ? 'bg-amber-500/10 text-amber-400' :
                                                                    'bg-red-500/10 text-red-400'}`}>
                                                            {tx.status}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        {tx.url && (
                                                            <a href={tx.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-medium text-xs">
                                                                View
                                                            </a>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                                                    No transactions found for current filter.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>

                    {/* Sidebar - Collaboration */}
                    <div className="lg:col-span-1 h-[600px] lg:h-[calc(100vh-200px)] sticky top-6">
                        <CommentSection channel="finance" title="Finance Team" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default FinanceCommandCenter;
