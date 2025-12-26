import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Badge } from '@/components/ui/badge';

// Mocking or importing these from where they might be
import {
    getShopifyConnectionStatus,
    disconnectShopify,
    ShopifyConnectionStatusInfo
} from '../../../src/skills/shopifySkills';

const PYTHON_API_SERVICE_BASE_URL = process.env.NEXT_PUBLIC_PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5000';

const ShopifyManager: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;

    const [connectionStatus, setConnectionStatus] = useState<ShopifyConnectionStatusInfo | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);
    const [shopName, setShopName] = useState<string>('');
    const [errorMessages, setErrorMessages] = useState<{ general?: string; status?: string }>({});
    const { toast } = useToast();

    const fetchConnectionStatus = useCallback(async () => {
        if (!userId) return;
        setIsLoadingStatus(true);
        setErrorMessages(prev => ({ ...prev, status: undefined }));
        try {
            const response = await getShopifyConnectionStatus(userId) as any;
            if (response.ok && response.data) {
                setConnectionStatus(response.data);
            } else {
                setConnectionStatus({ isConnected: false, reason: response.error?.message || 'Failed to get status' });
                setErrorMessages(prev => ({ ...prev, status: response.error?.message || 'Failed to get status' }));
            }
        } catch (error: any) {
            setConnectionStatus({ isConnected: false, reason: 'Exception while fetching status' });
            setErrorMessages(prev => ({ ...prev, status: error.message || 'Exception while fetching status' }));
        } finally {
            setIsLoadingStatus(false);
        }
    }, [userId]);

    const handleConnectShopify = () => {
        if (!userId) {
            setErrorMessages(prev => ({ ...prev, general: "User ID is missing." }));
            return;
        }
        if (!shopName.trim()) {
            toast({
                title: 'Shop Name Required',
                description: 'Please enter your Shopify shop name (e.g., my-great-store).',
                variant: 'error',
            });
            return;
        }
        window.location.href = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/auth?user_id=${userId}&shop_name=${shopName}`;
    };

    const handleDisconnectShopify = useCallback(async () => {
        if (!userId) return;
        setErrorMessages(prev => ({ ...prev, general: undefined }));
        try {
            const response = await disconnectShopify(userId);
            if (response.ok) {
                await fetchConnectionStatus();
            } else {
                setErrorMessages(prev => ({ ...prev, general: response.error?.message || 'Failed to disconnect' }));
            }
        } catch (error: any) {
            setErrorMessages(prev => ({ ...prev, general: error.message || 'Exception during disconnect' }));
        }
    }, [userId, fetchConnectionStatus]);

    useEffect(() => {
        if (userId) fetchConnectionStatus();
    }, [userId, fetchConnectionStatus]);

    return (
        <Card>
            <CardHeader>
                <div className="flex justify-between items-center">
                    <CardTitle>Shopify Management</CardTitle>
                    <Badge variant={connectionStatus?.isConnected ? 'default' : 'secondary'}>
                        {connectionStatus?.isConnected ? 'Connected' : 'Disconnected'}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {errorMessages.general && <div className="text-destructive text-sm font-medium">Error: {errorMessages.general}</div>}

                <div className="space-y-4">
                    <h4 className="font-medium">Connection Status</h4>
                    {isLoadingStatus ? (
                        <div className="flex items-center gap-2 text-muted-foreground italic">
                            <span>Loading status...</span>
                        </div>
                    ) : connectionStatus?.isConnected ? (
                        <div className="space-y-4">
                            <div className="p-3 bg-green-50 text-green-700 rounded-md border border-green-200">
                                Connected to: <span className="font-bold">{connectionStatus.shopUrl || 'N/A'}</span>
                            </div>
                            <Button onClick={handleDisconnectShopify} variant="destructive">Disconnect Shopify</Button>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="text-muted-foreground italic">Not Connected.</div>
                            {errorMessages.status && <div className="text-destructive text-sm">{errorMessages.status}</div>}
                            <div className="grid gap-2">
                                <Label htmlFor="shopName">Shop Name</Label>
                                <Input
                                    id="shopName"
                                    placeholder="your-store-name"
                                    value={shopName}
                                    onChange={(e) => setShopName(e.target.value)}
                                />
                            </div>
                            <Button onClick={handleConnectShopify}>Connect Shopify</Button>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default ShopifyManager;
