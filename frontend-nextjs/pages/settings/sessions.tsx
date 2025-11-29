import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Laptop, Smartphone, Globe, Clock, ShieldAlert } from 'lucide-react';
import UAParser from 'ua-parser-js';

interface Session {
    id: string;
    device_type: string;
    browser: string;
    os: string;
    ip_address: string;
    last_active_at: string;
    created_at: string;
    is_active: boolean;
    is_current: boolean;
}

export default function SessionSettings() {
    const { data: session, status } = useSession();
    const router = useRouter();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [revoking, setRevoking] = useState<string | null>(null);

    useEffect(() => {
        if (status === 'unauthenticated') {
            router.push('/auth/signin');
        } else if (status === 'authenticated') {
            fetchSessions();
            // Also record current session
            recordCurrentSession();
        }
    }, [status]);

    const recordCurrentSession = async () => {
        try {
            // In a real app, we'd send a token or identifier
            // For now, we just ping the endpoint to record activity
            await fetch('/api/auth/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: 'current-session-token' }), // Placeholder
            });
        } catch (e) {
            console.error('Failed to record session', e);
        }
    };

    const fetchSessions = async () => {
        try {
            const response = await fetch('/api/auth/sessions');
            if (!response.ok) {
                throw new Error('Failed to fetch sessions');
            }
            const data = await response.json();
            setSessions(data.sessions || []);
        } catch (err: any) {
            setError(err.message || 'Failed to load session information');
        } finally {
            setLoading(false);
        }
    };

    const handleRevokeSession = async (sessionId: string) => {
        if (!confirm('Are you sure you want to revoke this session? The device will be signed out.')) {
            return;
        }

        setRevoking(sessionId);
        setError('');

        try {
            const response = await fetch('/api/auth/sessions', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sessionId }),
            });

            if (!response.ok) {
                throw new Error('Failed to revoke session');
            }

            await fetchSessions();
        } catch (err: any) {
            setError(err.message || 'Failed to revoke session');
        } finally {
            setRevoking(null);
        }
    };

    const handleRevokeAll = async () => {
        if (!confirm('Are you sure you want to sign out of all devices? You will need to sign in again.')) {
            return;
        }

        setRevoking('all');
        setError('');

        try {
            const response = await fetch('/api/auth/sessions', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ revokeAll: true }),
            });

            if (!response.ok) {
                throw new Error('Failed to revoke all sessions');
            }

            // Sign out current user too
            router.push('/api/auth/signout');
        } catch (err: any) {
            setError(err.message || 'Failed to revoke sessions');
            setRevoking(null);
        }
    };

    const getDeviceIcon = (type: string) => {
        switch (type?.toLowerCase()) {
            case 'mobile':
                return <Smartphone className="h-6 w-6 text-gray-500" />;
            case 'tablet':
                return <Smartphone className="h-6 w-6 text-gray-500" />;
            default:
                return <Laptop className="h-6 w-6 text-gray-500" />;
        }
    };

    if (loading || status === 'loading') {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-4xl mx-auto space-y-6">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Active Sessions</h1>
                    <p className="mt-2 text-gray-600">Manage devices where you are currently signed in</p>
                </div>

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                <Card>
                    <CardHeader>
                        <div className="flex justify-between items-center">
                            <div>
                                <CardTitle>Your Devices</CardTitle>
                                <CardDescription>
                                    You are signed in on these devices
                                </CardDescription>
                            </div>
                            {sessions.length > 1 && (
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={handleRevokeAll}
                                    disabled={!!revoking}
                                >
                                    <ShieldAlert className="h-4 w-4 mr-2" />
                                    Sign Out Everywhere
                                </Button>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {sessions.length === 0 ? (
                                <p className="text-gray-500 text-center py-8">
                                    No active sessions found.
                                </p>
                            ) : (
                                sessions.map((session) => (
                                    <div
                                        key={session.id}
                                        className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                                    >
                                        <div className="flex items-center gap-4">
                                            {getDeviceIcon(session.device_type)}
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <p className="font-medium">
                                                        {session.browser || 'Unknown Browser'} on {session.os || 'Unknown OS'}
                                                    </p>
                                                    {session.is_current && (
                                                        <Badge variant="default" className="bg-green-500 hover:bg-green-600">
                                                            Current Device
                                                        </Badge>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                                                    <span className="flex items-center gap-1">
                                                        <Globe className="h-3 w-3" />
                                                        {session.ip_address}
                                                    </span>
                                                    <span className="flex items-center gap-1">
                                                        <Clock className="h-3 w-3" />
                                                        Active {new Date(session.last_active_at).toLocaleDateString()}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        {!session.is_current && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleRevokeSession(session.id)}
                                                disabled={revoking === session.id}
                                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                            >
                                                {revoking === session.id ? (
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                ) : (
                                                    'Revoke'
                                                )}
                                            </Button>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </CardContent>
                </Card>

                <div className="flex justify-between">
                    <Button variant="outline" onClick={() => router.push('/settings/account')}>
                        Back to Account Settings
                    </Button>
                </div>
            </div>
        </div>
    );
}
