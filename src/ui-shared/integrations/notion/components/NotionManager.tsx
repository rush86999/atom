/**
 * Notion Integration Manager Component
 * Complete Notion OAuth and API integration following established patterns
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  HStack,
  VStack,
  Badge,
  Icon,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  useToast,
  useColorModeValue,
  Divider,
  Flex,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Progress,
} from '@chakra-ui/react';
import { CheckCircleIcon, WarningIcon, ExternalLinkIcon, RepeatIcon } from '@chakra-ui/icons';

// Types
interface NotionConfig {
  enabled: boolean;
  clientId?: string;
  redirectUri?: string;
  scopes?: string[];
}

interface NotionConnectionStatus {
  connected: boolean;
  workspaceName?: string;
  workspaceIcon?: string;
  lastSync?: string;
  pagesCount?: number;
  databasesCount?: number;
}

interface NotionManagerProps {
  userId?: string;
  config?: NotionConfig;
  onConnectionChange?: (status: NotionConnectionStatus) => void;
  onError?: (error: Error) => void;
}

interface NotionWorkspace {
  id: string;
  name: string;
  icon?: string;
  pages: number;
  databases: number;
  lastSynced: string;
}

const NotionManager: React.FC<NotionManagerProps> = ({
  userId = 'default-user',
  config = {
    enabled: true,
    redirectUri: 'http://localhost:3000/oauth/notion/callback',
    scopes: ['read:page', 'read:database', 'write:page', 'write:database'],
  },
  onConnectionChange,
  onError,
}) => {
  const [loading, setLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<NotionConnectionStatus>({
    connected: false,
  });
  const [workspaces, setWorkspaces] = useState<NotionWorkspace[]>([]);
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'unhealthy' | 'checking'>('checking');
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Check Notion connection status
  const checkNotionStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/auth/notion/status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        const data = await response.json();
        setConnectionStatus({
          connected: data.connected || false,
          workspaceName: data.workspace_name,
          workspaceIcon: data.workspace_icon,
          lastSync: data.last_sync,
          pagesCount: data.pages_count,
          databasesCount: data.databases_count,
        });

        onConnectionChange?.({
          connected: data.connected || false,
          workspaceName: data.workspace_name,
          workspaceIcon: data.workspace_icon,
          lastSync: data.last_sync,
          pagesCount: data.pages_count,
          databasesCount: data.databases_count,
        });
      }
    } catch (error) {
      console.error('Failed to check Notion status:', error);
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, onConnectionChange, onError]);

  // Check Notion service health
  const checkNotionHealth = useCallback(async () => {
    try {
      setHealthStatus('checking');
      const response = await fetch('/api/integrations/notion/health');

      if (response.ok) {
        const data = await response.json();
        setHealthStatus(data.status === 'healthy' ? 'healthy' : 'unhealthy');
      } else {
        setHealthStatus('unhealthy');
      }
    } catch (error) {
      console.error('Failed to check Notion health:', error);
      setHealthStatus('unhealthy');
    }
  }, []);

  // Start Notion OAuth flow
  const startNotionOAuth = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/auth/notion/authorize?user_id=${userId}`);

      if (response.ok) {
        const data = await response.json();

        if (data.auth_url) {
          // Redirect to Notion OAuth
          window.location.href = data.auth_url;
        } else {
          throw new Error('No authorization URL received');
        }
      } else {
        throw new Error('Failed to initiate OAuth flow');
      }
    } catch (error) {
      console.error('Failed to start Notion OAuth:', error);
      toast({
        title: 'OAuth Failed',
        description: 'Failed to start Notion authentication',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, onError]);

  // Disconnect Notion integration
  const disconnectNotion = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/auth/notion/disconnect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        setConnectionStatus({ connected: false });
        onConnectionChange?.({ connected: false });

        toast({
          title: 'Disconnected',
          description: 'Notion integration has been disconnected',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error('Failed to disconnect Notion');
      }
    } catch (error) {
      console.error('Failed to disconnect Notion:', error);
      toast({
        title: 'Disconnect Failed',
        description: 'Failed to disconnect Notion integration',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, onConnectionChange, onError]);

  // Sync Notion data
  const syncNotionData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/integrations/notion/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        const data = await response.json();

        toast({
          title: 'Sync Complete',
          description: `Synced ${data.pages_synced || 0} pages and ${data.databases_synced || 0} databases`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });

        // Refresh status after sync
        await checkNotionStatus();
      } else {
        throw new Error('Failed to sync Notion data');
      }
    } catch (error) {
      console.error('Failed to sync Notion data:', error);
      toast({
        title: 'Sync Failed',
        description: 'Failed to sync Notion data',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, checkNotionStatus, onError]);

  // Load workspaces
  const loadWorkspaces = useCallback(async () => {
    if (!connectionStatus.connected) return;

    try {
      const response = await fetch('/api/integrations/notion/workspaces', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        const data = await response.json();
        setWorkspaces(data.workspaces || []);
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error);
    }
  }, [userId, connectionStatus.connected]);

  // Initial load
  useEffect(() => {
    checkNotionStatus();
    checkNotionHealth();
  }, [checkNotionStatus, checkNotionHealth]);

  // Load workspaces when connected
  useEffect(() => {
    if (connectionStatus.connected) {
      loadWorkspaces();
    }
  }, [connectionStatus.connected, loadWorkspaces]);

  if (!config.enabled) {
    return (
      <Card bg={bgColor} border="1px" borderColor={borderColor}>
        <CardBody>
          <Alert status="warning">
            <AlertIcon />
            <AlertTitle>Notion Integration Disabled</AlertTitle>
            <AlertDescription>
              Notion integration is currently disabled in the configuration.
            </AlertDescription>
          </Alert>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card bg={bgColor} border="1px" borderColor={borderColor}>
      <CardHeader>
        <HStack justify="space-between">
          <Heading size="md">Notion Integration</Heading>
          <HStack>
            <Badge
              colorScheme={healthStatus === 'healthy' ? 'green' : healthStatus === 'checking' ? 'yellow' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon
                as={healthStatus === 'healthy' ? CheckCircleIcon : WarningIcon}
                mr={1}
              />
              {healthStatus === 'healthy' ? 'Healthy' : healthStatus === 'checking' ? 'Checking...' : 'Unhealthy'}
            </Badge>
            <Badge
              colorScheme={connectionStatus.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon
                as={connectionStatus.connected ? CheckCircleIcon : WarningIcon}
                mr={1}
              />
              {connectionStatus.connected ? 'Connected' : 'Disconnected'}
            </Badge>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        {loading && (
          <Flex justify="center" mb={4}>
            <Spinner size="lg" />
          </Flex>
        )}

        {!connectionStatus.connected ? (
          <VStack spacing={4} align="stretch">
            <Alert status="info">
              <AlertIcon />
              <Box>
                <AlertTitle>Connect to Notion</AlertTitle>
                <AlertDescription>
                  Connect your Notion workspace to sync pages, databases, and collaborate seamlessly.
                </AlertDescription>
              </Box>
            </Alert>

            <Button
              colorScheme="blue"
              onClick={startNotionOAuth}
              isLoading={loading}
              loadingText="Connecting..."
              leftIcon={<ExternalLinkIcon />}
              size="lg"
            >
              Connect Notion Workspace
            </Button>

            <Text fontSize="sm" color="gray.500" textAlign="center">
              You'll be redirected to Notion to authorize access to your workspace
            </Text>
          </VStack>
        ) : (
          <VStack spacing={6} align="stretch">
            {/* Connection Status */}
            <Alert status="success">
              <AlertIcon />
              <Box>
                <AlertTitle>Connected to Notion</AlertTitle>
                <AlertDescription>
                  {connectionStatus.workspaceName && `Workspace: ${connectionStatus.workspaceName}`}
                  {connectionStatus.lastSync && ` • Last sync: ${new Date(connectionStatus.lastSync).toLocaleString()}`}
                </AlertDescription>
              </Box>
            </Alert>

            {/* Stats */}
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
              <Stat>
                <StatLabel>Pages</StatLabel>
                <StatNumber>{connectionStatus.pagesCount || 0}</StatNumber>
                <StatHelpText>Synced pages</StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Databases</StatLabel>
                <StatNumber>{connectionStatus.databasesCount || 0}</StatNumber>
                <StatHelpText>Synced databases</StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Status</StatLabel>
                <StatNumber>
                  <Badge colorScheme="green">Active</Badge>
                </StatNumber>
                <StatHelpText>Connection</StatHelpText>
              </Stat>
            </SimpleGrid>

            <Divider />

            {/* Actions */}
            <HStack spacing={4}>
              <Button
                colorScheme="blue"
                onClick={syncNotionData}
                isLoading={loading}
                loadingText="Syncing..."
                leftIcon={<RepeatIcon />}
                flex={1}
              >
                Sync Data
              </Button>
              <Button
                colorScheme="red"
                variant="outline"
                onClick={disconnectNotion}
                isLoading={loading}
                loadingText="Disconnecting..."
                flex={1}
              >
                Disconnect
              </Button>
            </HStack>

            {/* Workspaces */}
            {workspaces.length > 0 && (
              <Box>
                <Heading size="sm" mb={3}>
                  Workspaces
                </Heading>
                <VStack spacing={2} align="stretch">
                  {workspaces.map((workspace) => (
                    <Card key={workspace.id} variant="outline" size="sm">
                      <CardBody>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={1}>
                            <Text fontWeight="medium">{workspace.name}</Text>
                            <HStack spacing={4}>
                              <Text fontSize="sm" color="gray.500">
                                {workspace.pages} pages
                              </Text>
                              <Text fontSize="sm" color="gray.500">
                                {workspace.databases} databases
                              </Text>
                            </HStack>
                          </VStack>
                          <Text fontSize="sm" color="gray.500">
                            Last synced: {new Date(workspace.lastSynced).toLocaleDateString()}
                          </Text>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </Box>
            )}
          </VStack>
        )}
      </CardBody>
    </Card>
  );
};

export default NotionManager;
