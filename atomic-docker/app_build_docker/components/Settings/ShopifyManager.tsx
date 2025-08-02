import React, { useState, useEffect, useCallback } from 'react';
import {
  getShopifyConnectionStatus,
  disconnectShopify,
  ShopifyConnectionStatusInfo
} from '../../../../src/skills/shopifySkills'; // Adjust path as needed
import { PYTHON_API_SERVICE_BASE_URL } from '../../../functions/atom-agent/_libs/constants';
import { logger } from '../../../functions/_utils/logger';
import { useToast } from '@chakra-ui/react';
import { Box, Button, Input, Text, ActivityIndicator } from '@chakra-ui/react';

const ShopifyManager: React.FC = () => {
  const [userId] = useState<string | null>("test-user-123"); // Placeholder
  const [connectionStatus, setConnectionStatus] = useState<ShopifyConnectionStatusInfo | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);
  const [shopName, setShopName] = useState<string>('');
  const [errorMessages, setErrorMessages] = useState<{ general?: string; status?: string }>({});
  const toast = useToast();

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
      setErrorMessages(prev => ({ ...prev, general: "User ID is missing."}));
      return;
    }
    if (!shopName.trim()) {
      toast({
        title: 'Shop Name Required',
        description: 'Please enter your Shopify shop name (e.g., my-great-store).',
        status: 'warning',
        duration: 5000,
        isClosable: true,
      });
      return;
    }
    // Redirect to the backend OAuth initiation URL for Shopify
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
    <div style={{ fontFamily: 'Arial, sans-serif', padding: '20px', maxWidth: '800px', margin: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', marginTop: '20px' }}>
      <h2 style={{ borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px' }}>Shopify Management</h2>

      {errorMessages.general && <p style={{ color: 'red' }}>Error: {errorMessages.general}</p>}

      <div style={{ marginBottom: '20px' }}>
        <h3>Connection Status</h3>
        {isLoadingStatus ? <p>Loading status...</p> : connectionStatus?.isConnected ? (
          <div>
            <p style={{ color: 'green' }}>Connected to: {connectionStatus.shopUrl || 'N/A'}</p>
            <button onClick={handleDisconnectShopify}>Disconnect Shopify</button>
          </div>
        ) : (
          <div>
            <p style={{ color: 'orange' }}>Not Connected.</p>
            {errorMessages.status && <p style={{ color: 'red' }}>{errorMessages.status}</p>}
            <Input
              placeholder="your-store-name"
              value={shopName}
              onChange={(e) => setShopName(e.target.value)}
              style={{ marginBottom: '10px' }}
            />
            <button onClick={handleConnectShopify}>Connect Shopify</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ShopifyManager;
