import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { signOut } from 'next-auth/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Laptop, Smartphone, Globe, Clock, ShieldAlert } from 'lucide-react';

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
    /** WA-075: false when the backend cannot tie this entry to a revocable token. */
    revocable?: boolean;
}

async function failureMessage(response: Response, fallback: string): Promise<string> {
    try {
        const body = await response.json();
        if (body && typeof body.message === 'string' && body.message) return body.message;
        if (body && typeof body.error === 'string' && body.error) return body.error;
        if (body && typeof body.detail === 'string' && body.detail) return body.detail;
    } catch {
        // Non-JSON failure body; use the caller's fallback.
    }
    return fallback;
}

export default function SessionSettings() {
    const router = useRouter();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [revoking, setRevoking] = useState<string | null>(null);

    /**
     * WA-075: this is a no-body heartbeat. The backend identifies the session
     * from the credential the browser already presents; the page must never
     * send a token in the body (the old proxy stored it verbatim, and a client
     * supplied token is not proof of session ownership).
     */
    const recordCurrentSession = useCallback(async () => {
        try {
            const response = await fetch('/api/auth/sessions', { method: 'POST' });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            if (data?.tracked === false) {
                setNotice(
                    typeof data.message === 'string' && data.message
                        ? data.message
                        : 'This session is not in the device inventory, so it cannot be revoked from this page.'
                );
            }
        } catch (e) {
            // A heartbeat is advisory; never block the list on it.
            console.error('Failed to record session activity', e);
        }
    }, []);

    const fetchSessions = useCallback(async () => {
        try {
            const response = await fetch('/api/auth/sessions');
            if (!response.ok) {
                throw new Error(await failureMessage(response, 'Failed to fetch sessions'));
            }
            const data = await response.json();
            setSessions(data.sessions || []);
        } catch (err: any) {
            setError(err.message || 'Failed to load session information');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
            router.push('/login');
        } else {
            fetchSessions();
            recordCurrentSession();
        }
    }, [fetchSessions, recordCurrentSession, router]);

    const handleRevokeSession = async (sessionId: string) => {
        if (!confirm('Are you sure you want to revoke this session? The device will be signed out.')) {
            return;
        }

        setRevoking(sessionId);
        setError('');
        setNotice('');

        try {
            const response = await fetch('/api/auth/sessions', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sessionId }),
            });

            if (!response.ok) {
                throw new Error(await failureMessage(response, 'Failed to revoke session'));
            }

            await fetchSessions();
        } catch (err: any) {
            setError(err.message || 'Failed to revoke session');
        } finally {
            setRevoking(null);
        }
    };

    const handleRevokeAll = async () => {
        if (!confirm(
            'Are you sure you want to sign out of all devices? Recorded devices will be signed out; ' +
            'sessions created by other sign-in paths may remain valid until they expire.'
        )) {
            return;
        }

        setRevoking('all');
        setError('');
        setNotice('');

        try {
            const response = await fetch('/api/auth/sessions', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ revokeAll: true }),
            });

            if (!response.ok) {
                throw new Error(await failureMessage(response, 'Failed to revoke all sessions'));
            }

            // Signing out through NextAuth runs the signOut event, which calls
            // the backend /api/auth/logout and revokes this browser's token.
            // Navigating to the GET /api/auth/signout page never did that.
            await signOut({ callbackUrl: '/auth/signin' });
        } catch (err: any) {
            setError(err.message || 'Failed to revoke sessions');
            setRevoking(null);
        }
    };

    const getDeviceIcon = (type: string) => {
        switch (type?.toLowerCase()) {
            case 'mobile':
                return <Smartphone className="h-6 w-6 text-gray-500 dark:text-gray-400" />;
            case 'tablet':
                return <Smartphone className="h-6 w-6 text-gray-500 dark:text-gray-400" />;
            default:
                return <Laptop className="h-6 w-6 text-gray-500 dark:text-gray-400" />;
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-800 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-4xl mx-auto space-y-6">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Active Sessions</h1>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">Manage devices where you are currently signed in</p>
                </div>

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                {notice && (
                    <Alert>
                        <AlertDescription>{notice}</AlertDescription>
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
                                <p className="text-gray-500 dark:text-gray-400 text-center py-8">
                                    No active sessions found.
                                </p>
                            ) : (
                                sessions.map((session) => {
                                    const revocable = session.revocable !== false;
                                    return (
                                        <div
                                            key={session.id}
                                            className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 dark:bg-gray-800 transition-colors"
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
                                                        {!revocable && (
                                                            <Badge variant="secondary">
                                                                Cannot be revoked
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 mt-1">
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
                                                    disabled={!!revoking || !revocable}
                                                    title={revocable ? undefined : 'This entry has no token the server can revoke.'}
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
                                    );
                                })
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
