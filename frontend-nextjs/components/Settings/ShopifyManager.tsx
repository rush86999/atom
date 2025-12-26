import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import TextField from '@components/TextField';
import { useToast } from '@components/ui/use-toast';

// Placeholders for imports that might be missing in some environments
// or recovered with different paths
const PYTHON_API_SERVICE_BASE_URL = process.env.NEXT_PUBLIC_PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5000';

// Mocking or importing these from where they might be
// Given the previous session, these might need to be resolved
import {
    getShopifyConnectionStatus,
    disconnectShopify,
    ShopifyConnectionStatusInfo
} from '../../../../src/skills/shopifySkills';

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
            const response = await getShopifyConnectionStatus(userId);
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
                variant: 'destructive',
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
        <Box marginTop="m" padding="m" borderWidth={1} borderColor="hairline" borderRadius="m">
            <Text variant="subHeader" marginBottom="s">Shopify Management</Text>

            {errorMessages.general && <Text color="red.500" marginBottom="s">Error: {errorMessages.general}</Text>}

            <Box>
                <Text marginBottom="s">Connection Status</Text>
                {isLoadingStatus ? <Text>Loading status...</Text> : connectionStatus?.isConnected ? (
                    <Box>
                        <Text color="green.500" marginBottom="s">Connected to: {connectionStatus.shopUrl || 'N/A'}</Text>
                        <Button onPress={handleDisconnectShopify} title="Disconnect Shopify" variant="danger" />
                    </Box>
                ) : (
                    <Box>
                        <Text color="orange.500" marginBottom="s">Not Connected.</Text>
                        {errorMessages.status && <Text color="red.500" marginBottom="s">{errorMessages.status}</Text>}
                        <TextField
                            label="Shop Name"
                            placeholder="your-store-name"
                            value={shopName}
                            onChange={(e) => setShopName(e.target.value)}
                            marginBottom="s"
                        />
                        <Button onPress={handleConnectShopify} title="Connect Shopify" />
                    </Box>
                )}
            </Box>
        </Box>
    );
};

export default ShopifyManager;
