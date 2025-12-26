import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import {
    getGDriveConnectionStatus,
    disconnectGDrive,
    GDriveConnectionStatusInfo
} from '../../../src/skills/gdriveSkills';

const GDriveManager: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();

    const [connectionStatus, setConnectionStatus] = useState<GDriveConnectionStatusInfo | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchConnectionStatus = useCallback(async () => {
        if (!userId) return;
        setIsLoadingStatus(true);
        setError(null);
        try {
            const response = await getGDriveConnectionStatus(userId);
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

    const handleConnectGDrive = () => {
        if (!userId) {
            setError("User ID is missing.");
            return;
        }
        window.location.href = `/api/auth/google/initiate?user_id=${userId}&scope=drive`;
    };

    const handleDisconnectGDrive = useCallback(async () => {
        if (!userId) return;
        try {
            const response = await disconnectGDrive(userId);
            if (response.ok) {
                toast({ title: 'Google Drive disconnected successfully', variant: 'success' });
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
                    <h4 className="font-medium">Google Drive</h4>
                    <Badge variant={connectionStatus?.isConnected ? 'default' : 'secondary'}>
                        {connectionStatus?.isConnected ? 'Connected' : 'Disconnected'}
                    </Badge>
                </div>
                {connectionStatus?.isConnected ? (
                    <Button onClick={handleDisconnectGDrive} variant="destructive" size="sm">Disconnect</Button>
                ) : (
                    <Button onClick={handleConnectGDrive} size="sm">Connect Drive</Button>
                )}
            </div>

            {isLoadingStatus ? (
                <p className="text-sm text-muted-foreground italic">Checking Drive status...</p>
            ) : connectionStatus?.isConnected ? (
                <div className="p-3 bg-green-50 text-green-700 rounded-md border border-green-200 text-sm">
                    Connected to Google Drive. ATOM can now index and search your documents.
                </div>
            ) : (
                <p className="text-sm text-muted-foreground">Grant ATOM permission to access your Google Drive files.</p>
            )}

            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm font-medium">
                    {error}
                </div>
            )}
        </div>
    );
};

export default GDriveManager;
