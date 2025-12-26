import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/components/ui/use-toast';
import { Separator } from '@/components/ui/separator';
import { useWakeWord } from '@/contexts/WakeWordContext';
import GDriveManager from './GDriveManager';
import DropboxManager from './DropboxManager';
import VoiceSettings from './VoiceSettings';
import LiveMeetingAttendanceSettings from './LiveMeetingAttendanceSettings';

const AtomAgentSettings: React.FC = () => {
    const { data: session, status } = useSession();
    const router = useRouter();
    const { toast } = useToast();
    const { isWakeWordEnabled, toggleWakeWord, isListening, wakeWordError } = useWakeWord();

    const [isCalendarConnected, setIsCalendarConnected] = useState(false);
    const [userEmail, setUserEmail] = useState<string | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState(true);
    const [zapierWebhookUrl, setZapierWebhookUrl] = useState('');

    useEffect(() => {
        const fetchStatus = async () => {
            if (status === "loading") return;
            if (!session?.user) {
                setIsLoadingStatus(false);
                return;
            }

            try {
                const response = await fetch('/api/integrations/calendar/status');
                const data = await response.json();
                setIsCalendarConnected(data.isConnected);
                setUserEmail(session.user.email ?? null);

                const zapResponse = await fetch('/api/integrations/credentials?service=zapier_webhook_url');
                const zapData = await zapResponse.json();
                if (zapData.isConnected) {
                    setZapierWebhookUrl(zapData.value || '');
                }
            } catch (error) {
                console.error('Error fetching status:', error);
            } finally {
                setIsLoadingStatus(false);
            }
        };

        fetchStatus();
    }, [session, status]);

    const handleConnectCalendar = () => {
        window.location.href = '/api/auth/google/initiate';
    };

    const handleSaveZapierUrl = async () => {
        try {
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: 'zapier_webhook_url', secret: zapierWebhookUrl }),
            });
            if (response.ok) {
                toast({ title: 'Zapier Webhook URL saved successfully.', variant: 'success' });
            } else {
                toast({ title: 'Failed to save Zapier Webhook URL.', variant: 'error' });
            }
        } catch (error) {
            toast({ title: 'Error connecting to the server.', variant: 'error' });
        }
    };

    if (status === "loading" || isLoadingStatus) {
        return <div className="p-8 text-center italic text-muted-foreground">Loading settings...</div>;
    }

    return (
        <div className="space-y-8 max-w-4xl mx-auto pb-12">
            <section className="space-y-4">
                <h2 className="text-2xl font-bold">Agent Settings</h2>
                <p className="text-muted-foreground">Configure how your ATOM agent interacts with your tools and environment.</p>
            </section>

            <Card>
                <CardHeader>
                    <CardTitle>Voice & Wake Word</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label htmlFor="wake-word">Wake Word Detection</Label>
                            <p className="text-sm text-muted-foreground">Allow ATOM to listen for "Hey Atom" to activate.</p>
                        </div>
                        <Switch
                            id="wake-word"
                            checked={isWakeWordEnabled}
                            onCheckedChange={() => toggleWakeWord()}
                        />
                    </div>
                    {isWakeWordEnabled && (
                        <div className="p-3 bg-muted rounded-md flex items-center gap-3">
                            <div className={`w-3 h-3 rounded-full ${isListening ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                            <span className="text-sm font-medium">
                                {isListening ? 'Listening for "Hey Atom"...' : 'Voice detection inactive'}
                            </span>
                        </div>
                    )}
                    {wakeWordError && (
                        <div className="text-destructive text-sm font-medium">{wakeWordError}</div>
                    )}
                    <Separator />
                    <VoiceSettings />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Google Workspace</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <p className="font-medium">{isCalendarConnected ? 'Connected to Google' : 'Integration Disconnected'}</p>
                            {userEmail && <p className="text-sm text-muted-foreground">{userEmail}</p>}
                        </div>
                        <Button onClick={handleConnectCalendar} variant={isCalendarConnected ? "outline" : "default"}>
                            {isCalendarConnected ? 'Reconnect Google' : 'Connect Google'}
                        </Button>
                    </div>
                    <Separator />
                    <GDriveManager />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Dropbox Integration</CardTitle>
                </CardHeader>
                <CardContent>
                    <DropboxManager />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Live Meeting Attendance</CardTitle>
                </CardHeader>
                <CardContent>
                    <LiveMeetingAttendanceSettings />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Automation Hooks</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="zapier-url">Zapier Webhook URL</Label>
                        <Input
                            id="zapier-url"
                            value={zapierWebhookUrl}
                            onChange={(e) => setZapierWebhookUrl(e.target.value)}
                            placeholder="https://hooks.zapier.com/hooks/catch/..."
                        />
                    </div>
                    <Button onClick={handleSaveZapierUrl}>Save Webhook URL</Button>
                </CardContent>
            </Card>
        </div>
    );
};

export default AtomAgentSettings;
