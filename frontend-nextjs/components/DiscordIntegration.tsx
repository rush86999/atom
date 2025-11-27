/**
 * Discord Integration Component
 * Real-time communication and community platform
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Plug,
    Unplug,
    RefreshCw,
    Server,
    Users,
    BarChart3,
    Settings,
    Hash,
    Bell,
    Shield,
    Loader2,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Alert, AlertDescription } from '@/components/ui/alert';

// Discord brand color
const DISCORD_COLOR = '#5865F2';

const DiscordIntegration = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [loading, setLoading] = useState({
        connect: false,
        data: false,
        save: false
    });
    const [integrationData, setIntegrationData] = useState({
        profile: null as any,
        guilds: [] as any[],
        channels: [] as any[],
        messages: [] as any[],
        analytics: null as any
    });
    const [selectedTab, setSelectedTab] = useState('servers');

    const { toast } = useToast();

    // Check connection status
    const checkConnectionStatus = useCallback(async () => {
        try {
            const response = await fetch("/api/integrations/discord/health");
            const data = await response.json();

            setIsConnected(data.success);
        } catch (error) {
            console.error("Connection check failed:", error);
            setIsConnected(false);
        }
    }, []);

    // Load integration data
    const loadIntegrationData = useCallback(async () => {
        if (!isConnected) return;

        setLoading(prev => ({ ...prev, data: true }));

        try {
            const [profileResponse, guildsResponse] = await Promise.all([
                fetch("/api/integrations/discord/profile", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: "current" })
                }),
                fetch("/api/integrations/discord/guilds", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: "current" })
                })
            ]);

            const [profileData, guildsData] = await Promise.all([
                profileResponse.json(),
                guildsResponse.json()
            ]);

            setIntegrationData({
                profile: profileData.success ? profileData.data : null,
                guilds: guildsData.success ? guildsData.data : [],
                channels: [],
                messages: [],
                analytics: null
            });

        } catch (error) {
            console.error("Failed to load integration data:", error);
            toast({
                title: "Failed to load data",
                variant: "destructive",
            });
        } finally {
            setLoading(prev => ({ ...prev, data: false }));
        }
    }, [isConnected, toast]);

    // Connect integration
    const connectIntegration = useCallback(async () => {
        setLoading(prev => ({ ...prev, connect: true }));

        try {
            const response = await fetch("/api/integrations/discord/auth/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "current" })
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = data.authorization_url;
            } else {
                toast({
                    title: "Connection failed",
                    description: data.error,
                    variant: "destructive",
                });
            }
        } catch (error) {
            console.error("Connection failed:", error);
            toast({
                title: "Connection failed",
                description: "An error occurred while connecting",
                variant: "destructive",
            });
        } finally {
            setLoading(prev => ({ ...prev, connect: false }));
        }
    }, [toast]);

    // Disconnect integration
    const disconnectIntegration = useCallback(async () => {
        try {
            const response = await fetch("/api/integrations/discord/revoke", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "current" })
            });

            const data = await response.json();

            if (data.success) {
                setIsConnected(false);
                setIntegrationData({
                    profile: null,
                    guilds: [],
                    channels: [],
                    messages: [],
                    analytics: null
                });
                toast({
                    title: "Disconnected successfully",
                });
            }
        } catch (error) {
            console.error("Disconnection failed:", error);
            toast({
                title: "Disconnection failed",
                description: "An error occurred while disconnecting",
                variant: "destructive",
            });
        }
    }, [toast]);

    useEffect(() => {
        checkConnectionStatus();
    }, [checkConnectionStatus]);

    useEffect(() => {
        if (isConnected) {
            loadIntegrationData();
        }
    }, [isConnected, loadIntegrationData]);

    return (
        <div className="p-6 max-w-[1200px] mx-auto">
            <div className="flex flex-col space-y-6">
                {/* Header */}
                <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-4">
                        <div className="p-2 rounded-lg" style={{ backgroundColor: DISCORD_COLOR }}>
                            <svg className="w-10 h-10 text-white" viewBox="0 0 71 55" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <g clipPath="url(#clip0)">
                                    <path d="M60.1045 4.8978C55.5792 2.8214 50.7265 1.2916 45.6527 0.41542C45.5603 0.39851 45.468 0.440769 45.4204 0.525289C44.7963 1.6353 44.105 3.0834 43.6209 4.2216C38.1637 3.4046 32.7345 3.4046 27.3892 4.2216C26.905 3.0581 26.1886 1.6353 25.5617 0.525289C25.5141 0.443589 25.4218 0.40133 25.3294 0.41542C20.2584 1.2888 15.4057 2.8186 10.8776 4.8978C10.8384 4.9147 10.8048 4.9429 10.7825 4.9795C1.57795 18.7309 -0.943561 32.1443 0.293408 45.3914C0.299005 45.4562 0.335386 45.5182 0.385761 45.5576C6.45866 50.0174 12.3413 52.7249 18.1147 54.5195C18.2071 54.5477 18.305 54.5139 18.3638 54.4378C19.7295 52.5728 20.9469 50.6063 21.9907 48.5383C22.0523 48.4172 21.9935 48.2735 21.8676 48.2256C19.9366 47.4931 18.0979 46.6 16.3292 45.5858C16.1893 45.5041 16.1781 45.304 16.3068 45.2082C16.679 44.9293 17.0513 44.6391 17.4067 44.3461C17.471 44.2926 17.5606 44.2813 17.6362 44.3151C29.2558 49.6202 41.8354 49.6202 53.3179 44.3151C53.3935 44.2785 53.4831 44.2898 53.5502 44.3433C53.9057 44.6363 54.2779 44.9293 54.6529 45.2082C54.7816 45.304 54.7732 45.5041 54.6333 45.5858C52.8646 46.6197 51.0259 47.4931 49.0921 48.2228C48.9662 48.2707 48.9102 48.4172 48.9718 48.5383C50.038 50.6034 51.2554 52.5699 52.5959 54.435C52.6519 54.5139 52.7526 54.5477 52.845 54.5195C58.6464 52.7249 64.529 50.0174 70.6019 45.5576C70.6551 45.5182 70.6887 45.459 70.6943 45.3942C72.1747 30.0791 68.2147 16.7757 60.1968 4.9823C60.1772 4.9429 60.1437 4.9147 60.1045 4.8978ZM23.7259 37.3253C20.2276 37.3253 17.3451 34.1136 17.3451 30.1693C17.3451 26.225 20.1717 23.0133 23.7259 23.0133C27.308 23.0133 30.1626 26.2532 30.1066 30.1693C30.1066 34.1136 27.28 37.3253 23.7259 37.3253ZM47.3178 37.3253C43.8196 37.3253 40.9371 34.1136 40.9371 30.1693C40.9371 26.225 43.7636 23.0133 47.3178 23.0133C50.9 23.0133 53.7545 26.2532 53.6986 30.1693C53.6986 34.1136 50.9 37.3253 47.3178 37.3253Z" fill="currentColor" />
                                </g>
                                <defs>
                                    <clipPath id="clip0">
                                        <rect width="71" height="55" fill="white" />
                                    </clipPath>
                                </defs>
                            </svg>
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-gray-800">Discord Integration</h1>
                            <p className="text-sm text-gray-600">
                                Real-time communication and community platform
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Badge variant={isConnected ? "default" : "destructive"} className="px-3 py-1">
                            {isConnected ? "Connected" : "Not Connected"}
                        </Badge>

                        {!isConnected ? (
                            <Button
                                onClick={connectIntegration}
                                disabled={loading.connect}
                                style={{ backgroundColor: DISCORD_COLOR }}
                                className="hover:opacity-90"
                            >
                                {loading.connect ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <Plug className="mr-2 h-4 w-4" />
                                )}
                                Connect Discord
                            </Button>
                        ) : (
                            <Button
                                variant="outline"
                                onClick={disconnectIntegration}
                                className="text-red-600 border-red-600 hover:bg-red-50"
                            >
                                <Unplug className="mr-2 h-4 w-4" />
                                Disconnect
                            </Button>
                        )}

                        <Button
                            variant="outline"
                            onClick={() => {
                                checkConnectionStatus();
                                loadIntegrationData();
                            }}
                            disabled={loading.data}
                        >
                            {loading.data ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="mr-2 h-4 w-4" />
                            )}
                            Refresh
                        </Button>
                    </div>
                </div>

                {isConnected ? (
                    <>
                        {/* Profile Card */}
                        {integrationData.profile && (
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center space-x-4">
                                        <Avatar className="w-16 h-16">
                                            <AvatarImage src={integrationData.profile.avatar_url} />
                                            <AvatarFallback>{integrationData.profile.username?.slice(0, 2)}</AvatarFallback>
                                        </Avatar>
                                        <div className="flex-1">
                                            <h2 className="text-xl font-semibold">{integrationData.profile.username}</h2>
                                            <p className="text-gray-600">#{integrationData.profile.discriminator}</p>
                                            <div className="flex items-center space-x-4 mt-2">
                                                <Badge variant="secondary" className="flex items-center space-x-1">
                                                    <Users className="w-3 h-3" />
                                                    <span>{integrationData.profile.servers_count} Servers</span>
                                                </Badge>
                                                <Badge variant="secondary" className="flex items-center space-x-1">
                                                    <Hash className="w-3 h-3" />
                                                    <span>{integrationData.profile.channels_count} Channels</span>
                                                </Badge>
                                            </div>
                                        </div>
                                        <Button variant="ghost" size="sm">
                                            <Settings className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </CardHeader>
                            </Card>
                        )}

                        {/* Tabs */}
                        <Tabs value={selectedTab} onValueChange={setSelectedTab}>
                            <TabsList>
                                <TabsTrigger value="servers" className="flex items-center space-x-2">
                                    <Server className="w-4 h-4" />
                                    <span>Servers</span>
                                </TabsTrigger>
                                <TabsTrigger value="channels" className="flex items-center space-x-2">
                                    <Hash className="w-4 h-4" />
                                    <span>Channels</span>
                                </TabsTrigger>
                                <TabsTrigger value="analytics" className="flex items-center space-x-2">
                                    <BarChart3 className="w-4 h-4" />
                                    <span>Analytics</span>
                                </TabsTrigger>
                                <TabsTrigger value="notifications" className="flex items-center space-x-2">
                                    <Bell className="w-4 h-4" />
                                    <span>Notifications</span>
                                </TabsTrigger>
                            </TabsList>

                            {/* Servers Tab */}
                            <TabsContent value="servers" className="space-y-6 mt-6">
                                <h2 className="text-xl font-semibold">Discord Servers</h2>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {integrationData.guilds.map((guild) => (
                                        <Card key={guild.id} className="border">
                                            <CardContent className="pt-6">
                                                <div className="flex items-center space-x-4">
                                                    <Avatar>
                                                        <AvatarImage src={guild.icon_url} />
                                                        <AvatarFallback>{guild.name?.slice(0, 2)}</AvatarFallback>
                                                    </Avatar>
                                                    <div className="flex flex-col space-y-1 flex-1">
                                                        <h3 className="font-semibold">{guild.name}</h3>
                                                        <p className="text-xs text-gray-500">
                                                            {guild.member_count} members • {guild.channel_count} channels
                                                        </p>
                                                        {guild.owner && (
                                                            <Badge variant="secondary" className="w-fit text-xs">
                                                                Owner
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </TabsContent>

                            {/* Channels Tab */}
                            <TabsContent value="channels" className="mt-6">
                                <Alert>
                                    <AlertDescription>
                                        Channel management coming soon
                                    </AlertDescription>
                                </Alert>
                            </TabsContent>

                            {/* Analytics Tab */}
                            <TabsContent value="analytics" className="space-y-6 mt-6">
                                <h2 className="text-xl font-semibold">Discord Analytics</h2>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-1">
                                                <p className="text-sm font-medium text-muted-foreground">Total Servers</p>
                                                <div className="text-2xl font-bold">{integrationData.guilds.length}</div>
                                                <p className="text-xs text-muted-foreground">Connected servers</p>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-1">
                                                <p className="text-sm font-medium text-muted-foreground">Active Channels</p>
                                                <div className="text-2xl font-bold">0</div>
                                                <p className="text-xs text-muted-foreground">Text & voice channels</p>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-1">
                                                <p className="text-sm font-medium text-muted-foreground">Messages Today</p>
                                                <div className="text-2xl font-bold">0</div>
                                                <p className="text-xs text-muted-foreground">Messages sent</p>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-1">
                                                <p className="text-sm font-medium text-muted-foreground">Active Users</p>
                                                <div className="text-2xl font-bold">0</div>
                                                <p className="text-xs text-muted-foreground">Users online</p>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>
                            </TabsContent>

                            {/* Notifications Tab */}
                            <TabsContent value="notifications" className="mt-6">
                                <Alert>
                                    <AlertDescription>
                                        Notification management coming soon
                                    </AlertDescription>
                                </Alert>
                            </TabsContent>
                        </Tabs>
                    </>
                ) : (
                    <Alert className="border-yellow-200 bg-yellow-50">
                        <AlertDescription>
                            <div className="flex flex-col space-y-2">
                                <p className="font-medium">Discord not connected</p>
                                <p className="text-sm">
                                    Connect your Discord account to access servers, channels, and real-time communication features.
                                </p>
                                <Button
                                    onClick={connectIntegration}
                                    style={{ backgroundColor: DISCORD_COLOR }}
                                    className="w-fit mt-2 hover:opacity-90"
                                >
                                    <Plug className="mr-2 h-4 w-4" />
                                    Connect Discord
                                </Button>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}
            </div>
        </div>
    );
};

export default DiscordIntegration;
