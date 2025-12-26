import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import {
    getDropboxConnectionStatus,
    disconnectDropbox,
    DropboxConnectionStatusInfo
} from '../../../src/skills/dropboxSkills';

const DropboxManager: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();

    const [connectionStatus, setConnectionStatus] = useState<DropboxConnectionStatusInfo | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchConnectionStatus = useCallback(async () => {
        if (!userId) return;
        setIsLoadingStatus(true);
        setError(null);
        try {
            const response = await getDropboxConnectionStatus(userId);
            if (response.ok && response.data) {
                setConnectionStatus(response.data);
            } else {
                setConnectionStatus({ isConnected: false, reason: response.error?.message || 'Failed to get status' });
                setError(response.error?.message || 'Failed to get status');
            }
        } catch (error: any) {
            setConnectionStatus({ isConnected: false, reason: 'Exception while fetching status' });
            setError(error.message || 'Exception while fetching status');
        } finally {
            setIsLoadingStatus(false);
        }
    }, [userId]);

    const handleConnectDropbox = () => {
        if (!userId) {
            setError("User ID is missing.");
            return;
        }
        window.location.href = `/api/auth/dropbox/initiate?user_id=${userId}`;
    };

    const handleDisconnectDropbox = useCallback(async () => {
        if (!userId) return;
        try {
            const response = await disconnectDropbox(userId);
            if (response.ok) {
                toast({ title: 'Dropbox disconnected successfully', variant: 'success' });
                await fetchConnectionStatus();
            } else {
                toast({ title: response.error?.message || 'Failed to disconnect', variant: 'error' });
            }
        } catch (error: any) {
            toast({ title: error.message || 'Exception during disconnect', variant: 'error' });
        }
    }, [userId, fetchConnectionStatus, toast]);

    useEffect(() => {
        if (userId) fetchConnectionStatus();
    }, [userId, fetchConnectionStatus]);

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <h4 className="font-medium">Connection Status</h4>
                    <Badge variant={connectionStatus?.isConnected ? 'default' : 'secondary'}>
                        {connectionStatus?.isConnected ? 'Connected' : 'Disconnected'}
                    </Badge>
                </div>
                {connectionStatus?.isConnected ? (
                    <Button onClick={handleDisconnectDropbox} variant="destructive" size="sm">Disconnect</Button>
                ) : (
                    <Button onClick={handleConnectDropbox} size="sm">Connect Dropbox</Button>
                )}
            </div>

            {isLoadingStatus ? (
                <p className="text-sm text-muted-foreground italic">Checking connection status...</p>
            ) : connectionStatus?.isConnected ? (
                <div className="p-3 bg-green-50 text-green-700 rounded-md border border-green-200 text-sm">
                    Connected to Dropbox account. All files set for synchronization are being analyzed.
                </div>
            ) : (
                <p className="text-sm text-muted-foreground">No Dropbox account connected. Connect to allow ATOM to access your files.</p>
            )}

            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm font-medium">
                    {error}
                </div>
            )}
        </div>
    );
};

export default DropboxManager;
