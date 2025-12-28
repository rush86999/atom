import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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
    Users
} from 'lucide-react';
import CommunicationHub from '@/components/shared/CommunicationHub';
import { CommentSection } from '@/components/shared/CommentSection';
import { toast } from 'sonner';
import { io } from 'socket.io-client';

export const CommunicationCommandCenter: React.FC = () => {
    const [isComposeOpen, setIsComposeOpen] = useState(false);
    const [stats, setStats] = useState({
        totalUnread: 0,
        activePlatforms: 0,
        responseRate: 0,
        avgResponseTime: '0m'
    });
    const [platformStatus, setPlatformStatus] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // WebSocket Connection
        const socket = io(process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'http://localhost:5059', {
            path: '/ws/socket.io',
            transports: ['websocket'],
            autoConnect: true
        });

        socket.on('connect', () => {
            console.log('Communication Command Center connected to WebSocket');
        });

        socket.on('status_update', (data: any) => {
            if (data.type === 'communication_stats') {
                setStats(prev => ({ ...prev, ...data.stats }));
                toast.info('Communication stats updated');
            }
        });

        socket.on('platform_status_change', (data: any) => {
            // Refresh platform list or update local state
            setPlatformStatus(prev => prev.map(p =>
                p.name.toLowerCase() === data.platform.toLowerCase()
                    ? { ...p, status: data.status }
                    : p
            ));
        });

        return () => {
            socket.disconnect();
        };
    }, []);

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
                // Keep default/mock state on error
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
                            placeholder="Search messages..."
                            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                        />
                    </div>
                </div>
            </div>

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
                                <p className="text-xs text-muted-foreground mt-1 text-red-400">
                                    4 urgent items
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Response Rate</CardTitle>
                                <TrendingUp className="w-4 h-4 text-green-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.responseRate}%</div>
                                <p className="text-xs text-muted-foreground mt-1 text-green-400">
                                    +2.4% this week
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Avg Response</CardTitle>
                                <Clock className="w-4 h-4 text-blue-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.avgResponseTime}</div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    Within target
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Active Channels</CardTitle>
                                <Users className="w-4 h-4 text-purple-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">{stats.activePlatforms}</div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    All systems operational
                                </p>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Communication Hub Embed */}
                    <Card className="bg-black/40 border-white/5 backdrop-blur-xl min-h-[600px]">
                        <CommunicationHub
                            showNavigation={false}
                            isComposeOpen={isComposeOpen}
                            onComposeChange={setIsComposeOpen}
                        />
                    </Card>
                </div>

                {/* Sidebar - 1/4 width */}
                <div className="lg:col-span-1 space-y-6">
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
        </div>
    );
};

export default CommunicationCommandCenter;
