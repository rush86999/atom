import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    MessageSquare,
    Mail,
    Phone,
    CheckCircle2,
    AlertCircle,
    Clock,
    Plus,
    Search,
    TrendingUp,
    Users,
    X,
    RefreshCw
} from 'lucide-react';
import CommunicationHub from '@/components/shared/CommunicationHub';
import { CommentSection } from '@/components/shared/CommentSection';
import { toast } from 'sonner';
import { useLiveCommunication } from '@/hooks/useLiveCommunication';
import { useCommunicationSearch } from '@/hooks/useCommunicationSearch';
import { useLiveContacts } from '@/hooks/useLiveContacts';
import { PipelineSettingsPanel } from '@/components/shared/PipelineSettingsPanel';
import { useWebSocket } from '@/hooks/useWebSocket';

export const CommunicationCommandCenter: React.FC = () => {
    const [isComposeOpen, setIsComposeOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [showSearchResults, setShowSearchResults] = useState(false);
    const [showSettings, setShowSettings] = useState(false);

    // Parallel Pipeline: Live Data Hooks
    const { data: session } = useSession();
    const { messages: liveMessages } = useLiveCommunication();
    const { results: searchResults, isSearching, searchMessages } = useCommunicationSearch();
    const { contacts: recentContacts, loading: loadingContacts } = useLiveContacts();

    const [stats, setStats] = useState({
        totalUnread: 0,
        activePlatforms: 0,
        responseRate: 0,
        avgResponseTime: '0m'
    });
    const [platformStatus, setPlatformStatus] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const { lastMessage } = useWebSocket({
        initialChannels: ['communication_stats', 'platform_status']
    });

    const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
        const query = e.target.value;
        setSearchQuery(query);
        if (query.length > 2) {
            searchMessages(query);
            setShowSearchResults(true);
        } else {
            setShowSearchResults(false);
        }
    };

    useEffect(() => {
        if (!lastMessage) return;

        if (lastMessage.type === 'status_update') {
            setStats(prev => ({ ...prev, ...lastMessage.data }));
            toast.info('Communication stats updated');
        } else if (lastMessage.type === 'platform_status_change') {
            setPlatformStatus(prev => prev.map(p =>
                p.name.toLowerCase() === lastMessage.data.platform.toLowerCase()
                    ? { ...p, status: lastMessage.data.status }
                    : p
            ));
        }
    }, [lastMessage]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch Analytics
                const analyticsRes = await fetch('/api/atom/communication/memory/analytics');
                if (analyticsRes.ok) {
                    const data = await analyticsRes.json();
                    if (data.success && data.analytics) {
                        setStats({
                            totalUnread: data.analytics.status_distribution?.unread || 0,
                            activePlatforms: data.analytics.summary.unique_apps || 0,
                            responseRate: data.analytics.performance?.response_rate || 0,
                            avgResponseTime: data.analytics.performance?.avg_response_time || '0m'
                        });
                    }
                }

                // Fetch Configured Apps
                const appsRes = await fetch('/api/atom/communication/memory/apps');
                if (appsRes.ok) {
                    const data = await appsRes.json();
                    if (data.apps) {
                        const mappedApps = data.apps.map((app: any) => {
                            let icon = MessageSquare;
                            let color = 'text-gray-500';
                            let bg = 'bg-gray-500/10';

                            if (app.id.includes('slack')) { icon = MessageSquare; color = 'text-purple-500'; bg = 'bg-purple-500/10'; }
                            else if (app.id.includes('mail') || app.id.includes('gmail')) { icon = Mail; color = 'text-blue-500'; bg = 'bg-blue-500/10'; }
                            else if (app.id.includes('teams')) { icon = Users; color = 'text-indigo-500'; bg = 'bg-indigo-500/10'; }
                            else if (app.id.includes('discord')) { icon = MessageSquare; color = 'text-indigo-400'; bg = 'bg-indigo-400/10'; }

                            return {
                                name: app.name,
                                status: app.memory_ingestion_enabled ? 'connected' : 'disconnected',
                                icon,
                                color,
                                bg
                            };
                        });
                        setPlatformStatus(mappedApps);
                    }
                }
            } catch (error) {
                console.error('Failed to fetch communication stats:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);


    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto animate-in fade-in duration-700">
            {/* Header Section */}
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Communication Command Center
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Unified inbox and analytics for all communication channels.
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
                    <button
                        onClick={() => setIsComposeOpen(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg transition-all text-sm font-semibold"
                    >
                        <Plus className="w-4 h-4" />
                        New Message
                    </button>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={handleSearch}
                            placeholder="Search memory..."
                            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => { setSearchQuery(''); setShowSearchResults(false); }}
                                className="absolute right-3 top-1/2 -translate-y-1/2"
                            >
                                <X className="w-4 h-4 text-muted-foreground hover:text-white" />
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Pipeline Settings Panel */}
            <PipelineSettingsPanel isOpen={showSettings} />

            {showSearchResults ? (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold text-white">Search Results for "{searchQuery}"</h2>
                        <button onClick={() => setShowSearchResults(false)} className="text-sm text-primary hover:underline">Clear Search</button>
                    </div>
                    {isSearching ? (
                        <div className="flex items-center gap-2 text-muted-foreground"><Clock className="w-4 h-4 animate-spin" /> Searching...</div>
                    ) : searchResults.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {searchResults.map((result: any) => (
                                <Card key={result.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors pointer-cursor">
                                    <CardContent className="p-4">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="capitalize text-[10px]">{result.app_type}</Badge>
                                                <span className="font-semibold text-white">{result.sender}</span>
                                            </div>
                                            <span className="text-xs text-muted-foreground">{new Date(result.timestamp).toLocaleString()}</span>
                                        </div>
                                        <p className="text-sm text-gray-300 line-clamp-2">{result.content}</p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-white/10 rounded-xl">No results found in memory.</div>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Main Content Area - 3/4 width */}
                    <div className="lg:col-span-3 space-y-6">
                        {/* KPI Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Unread Messages</CardTitle>
                                    <Mail className="w-4 h-4 text-primary" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{stats.totalUnread}</div>
                                    <p className="text-xs text-muted-foreground mt-1">Active sync</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Response Rate</CardTitle>
                                    <TrendingUp className="w-4 h-4 text-green-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{stats.responseRate}%</div>
                                    <p className="text-xs text-muted-foreground mt-1 text-green-400">Target: 95%</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Avg Response</CardTitle>
                                    <Clock className="w-4 h-4 text-blue-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{stats.avgResponseTime}</div>
                                    <p className="text-xs text-muted-foreground mt-1">Within target</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Active Channels</CardTitle>
                                    <Users className="w-4 h-4 text-purple-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{stats.activePlatforms}</div>
                                    <p className="text-xs text-muted-foreground mt-1">Systems online</p>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Communication Hub Embed */}
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl min-h-[600px]">
                            <CommunicationHub
                                showNavigation={false}
                                isComposeOpen={isComposeOpen}
                                onComposeChange={setIsComposeOpen}
                                initialMessages={liveMessages.length > 0 ? liveMessages : undefined}
                                currentUser={session?.user?.name || 'User'}
                            />
                        </Card>
                    </div>

                    {/* Sidebar - 1/4 width */}
                    <div className="lg:col-span-1 space-y-6">
                        {/* Recent Contacts */}
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-lg text-white flex items-center gap-2">
                                    <Users className="w-4 h-4" />
                                    Recent Contacts
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {loadingContacts ? (
                                    <div className="flex justify-center p-4"><Clock className="w-4 h-4 animate-spin text-primary" /></div>
                                ) : recentContacts.length > 0 ? (
                                    recentContacts.map((contact) => (
                                        <div key={contact.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group">
                                            <div className="flex items-center gap-3">
                                                <div className="relative">
                                                    <img src={contact.avatar} alt={contact.name} className="w-8 h-8 rounded-full border border-white/10" />
                                                    <div className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-black ${contact.status === 'online' ? 'bg-green-500' : 'bg-gray-500'}`} />
                                                </div>
                                                <div>
                                                    <div className="text-sm font-medium text-white group-hover:text-primary transition-colors">{contact.name}</div>
                                                    <div className="text-[10px] text-muted-foreground uppercase">{contact.provider}</div>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-xs text-center text-muted-foreground py-4">No recent contacts found.</div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Platform Status */}
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-lg text-white">Platform Status</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {platformStatus.map((platform) => (
                                    <div key={platform.name} className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                                        <div className="flex items-center gap-3">
                                            <div className={`p-2 rounded-md ${platform.bg}`}>
                                                <platform.icon className={`w-4 h-4 ${platform.color}`} />
                                            </div>
                                            <div>
                                                <div className="font-medium text-white text-sm">{platform.name}</div>
                                                <div className="text-xs text-muted-foreground capitalize">{platform.status}</div>
                                            </div>
                                        </div>
                                        {platform.status === 'connected' ? (
                                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <AlertCircle className="w-4 h-4 text-yellow-500" />
                                        )}
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Team Discussion */}
                        <div className="h-[400px]">
                            <CommentSection channel="communication_ops" title="Comm Ops Chat" />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CommunicationCommandCenter;

