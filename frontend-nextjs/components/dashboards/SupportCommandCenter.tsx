import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MessageCircle, Search, Clock, ShieldCheck, AlertCircle, Send, User } from 'lucide-react';
import { CommentSection } from '@/components/shared/CommentSection';

import { useWebSocket } from '@/hooks/useWebSocket';
import { useMemorySearch } from '@/hooks/useMemorySearch';
import { PipelineSettingsPanel } from '@/components/shared/PipelineSettingsPanel';
import { Button } from '@/components/ui/button';
import { RefreshCw, X } from 'lucide-react';
import { toast } from 'sonner';
import { useLiveSupport, Ticket } from '@/hooks/useLiveSupport';

export const SupportCommandCenter: React.FC = () => {
    const { data: session } = useSession();
    const { tickets, isLoading, refresh } = useLiveSupport();
    const [showSettings, setShowSettings] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [showSearchResults, setShowSearchResults] = useState(false);

    // Unified Search
    const { results: searchResults, isSearching, searchMemory, clearSearch } = useMemorySearch({ tag: 'support' });

    // WebSocket for Real-Time Sync Refreshes
    const { lastMessage } = useWebSocket({
        initialChannels: ['communication_stats', 'platform_status']
    });

    useEffect(() => {
        if (lastMessage && lastMessage.type === 'status_update') {
            toast.info('Support sync complete. Refreshing tickets...');
            refresh();
        }
    }, [lastMessage, refresh]);

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

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in duration-700">
            <div className="flex justify-between items-end text-white">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Support Command Center
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Unified inbox for Zendesk, Freshdesk, and Intercom.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowSettings(!showSettings)}
                        className="bg-white/5 border-white/10"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Sync Settings
                    </Button>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search tickets..."
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
                        <div className="flex items-center gap-2 text-muted-foreground"><Clock className="w-4 h-4 animate-spin" /> Searching support memory...</div>
                    ) : searchResults.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {searchResults.map((result: any) => (
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
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-white/10 rounded-xl">No historical tickets found for "{searchQuery}".</div>
                    )}
                </div>
            ) : (

                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    <div className="lg:col-span-3 space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardContent className="pt-6 flex flex-col items-center text-center">
                                    <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
                                    <h4 className="font-bold text-white text-xs">SLA Warning</h4>
                                    <p className="text-[10px] text-muted-foreground mt-1">2 tickets near breach</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardContent className="pt-6 flex flex-col items-center text-center">
                                    <Clock className="w-8 h-8 text-blue-400 mb-2" />
                                    <h4 className="font-bold text-white text-xs">18m Resp</h4>
                                    <p className="text-[10px] text-muted-foreground mt-1">Average response time</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardContent className="pt-6 flex flex-col items-center text-center">
                                    <ShieldCheck className="w-8 h-8 text-green-400 mb-2" />
                                    <h4 className="font-bold text-white text-xs">4.9 CSAT</h4>
                                    <p className="text-[10px] text-muted-foreground mt-1">Customer satisfaction</p>
                                </CardContent>
                            </Card>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <Card className="lg:col-span-1 bg-black/40 border-white/5 backdrop-blur-xl h-[500px]">
                                <CardHeader className="border-b border-white/5">
                                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                                        <MessageCircle className="w-4 h-4 text-primary" />
                                        Ticket Queue
                                    </CardTitle>
                                </CardHeader>
                                <div className="overflow-y-auto h-full pb-10">
                                    {tickets.map((ticket: Ticket) => (
                                        <div key={ticket.id} className="p-4 border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors group">
                                            <div className="flex justify-between items-start mb-1">
                                                <span className="text-[10px] font-mono text-muted-foreground">{ticket.id}</span>
                                                <Badge className={
                                                    ticket.priority === 'High' ? 'bg-red-500/20 text-red-500 border-red-500/20' :
                                                        ticket.priority === 'Medium' ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/20' :
                                                            'bg-blue-500/20 text-blue-500 border-blue-500/20'
                                                }>
                                                    {ticket.priority}
                                                </Badge>
                                            </div>
                                            <h3 className="text-sm font-medium group-hover:text-primary transition-colors text-white">{ticket.subject}</h3>
                                            <div className="flex items-center gap-3 mt-2">
                                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                    <User className="w-3 h-3" /> {ticket.customer}
                                                </span>
                                                <Badge variant="outline" className="text-[10px] capitalize opacity-60">
                                                    {ticket.platform}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </Card>

                            <div className="md:col-span-2 space-y-4">
                                <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                    <CardHeader className="border-b border-white/5">
                                        <div className="flex justify-between items-center">
                                            <div>
                                                <CardTitle className="text-xl text-white">Cloud Sync Failed for Org #55</CardTitle>
                                                <p className="text-sm text-muted-foreground mt-1">Acme Corp • Assigned to {session?.user?.name || "Staff Member"}</p>
                                            </div>
                                            <div className="flex gap-2">
                                                <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">Open</Badge>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="py-6 space-y-6 h-[300px] overflow-y-auto">
                                        <div className="flex gap-4">
                                            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-xs font-bold shrink-0 text-white">JD</div>
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-semibold text-white">John Doe</span>
                                                    <span className="text-xs text-muted-foreground">10:45 AM</span>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-lg text-sm max-w-xl text-muted-foreground">
                                                    Hey team, we're seeing persistent sync failures on the main dashboard for organization #55. Can you take a look?
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex gap-4 flex-row-reverse">
                                            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-xs font-bold shrink-0 text-primary-foreground">
                                                {session?.user?.name ? session.user.name.split(' ').map(n => n[0]).join('') : 'U'}
                                            </div>
                                            <div className="space-y-1 text-right">
                                                <div className="flex flex-row-reverse items-center gap-2">
                                                    <span className="text-sm font-semibold text-white">{session?.user?.name || "You"}</span>
                                                    <span className="text-xs text-muted-foreground">11:02 AM</span>
                                                </div>
                                                <div className="p-3 bg-primary/10 rounded-lg text-sm max-w-xl inline-block text-white">
                                                    Investigating now. It looks like a timeout issue on the legacy API endpoint.
                                                </div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </div>

                    <div className="lg:col-span-1 h-[600px] lg:h-[calc(100vh-200px)] sticky top-6">
                        <CommentSection channel="support" title="Support Collab" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default SupportCommandCenter;
