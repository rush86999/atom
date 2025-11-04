/**
 * Trello Integration Manager Component
 * Complete Trello OAuth and API integration following established patterns
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
interface TrelloConfig {
  enabled: boolean;
  apiKey?: string;
  redirectUri?: string;
  scopes?: string[];
}

interface TrelloConnectionStatus {
  connected: boolean;
  username?: string;
  fullName?: string;
  avatarUrl?: string;
  lastSync?: string;
  boardsCount?: number;
  cardsCount?: number;
}

interface TrelloManagerProps {
  userId?: string;
  config?: TrelloConfig;
  onConnectionChange?: (status: TrelloConnectionStatus) => void;
  onError?: (error: Error) => void;
}

interface TrelloBoard {
  id: string;
  name: string;
  desc?: string;
  url: string;
  closed: boolean;
  starred: boolean;
  lastActivity: string;
  cardsCount: number;
  listsCount: number;
}

const TrelloManager: React.FC<TrelloManagerProps> = ({
  userId = 'default-user',
  config = {
    enabled: true,
    redirectUri: 'http://localhost:3000/oauth/trello/callback',
    scopes: ['read', 'write', 'account'],
  },
  onConnectionChange,
  onError,
}) => {
  const [loading, setLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<TrelloConnectionStatus>({
    connected: false,
  });
  const [boards, setBoards] = useState<TrelloBoard[]>([]);
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'unhealthy' | 'checking'>('checking');
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Check Trello connection status
  const checkTrelloStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/auth/trello/status', {
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
          username: data.username,
          fullName: data.full_name,
          avatarUrl: data.avatar_url,
          lastSync: data.last_sync,
          boardsCount: data.boards_count,
          cardsCount: data.cards_count,
        });

        onConnectionChange?.({
          connected: data.connected || false,
          username: data.username,
          fullName: data.full_name,
          avatarUrl: data.avatar_url,
          lastSync: data.last_sync,
          boardsCount: data.boards_count,
          cardsCount: data.cards_count,
        });
      }
    } catch (error) {
      console.error('Failed to check Trello status:', error);
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, onConnectionChange, onError]);

  // Check Trello service health
  const checkTrelloHealth = useCallback(async () => {
    try {
      setHealthStatus('checking');
      const response = await fetch('/api/integrations/trello/health');

      if (response.ok) {
        const data = await response.json();
        setHealthStatus(data.status === 'healthy' ? 'healthy' : 'unhealthy');
      } else {
        setHealthStatus('unhealthy');
      }
    } catch (error) {
      console.error('Failed to check Trello health:', error);
      setHealthStatus('unhealthy');
    }
  }, []);

  // Start Trello OAuth flow
  const startTrelloOAuth = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/auth/trello/authorize?user_id=${userId}`);

      if (response.ok) {
        const data = await response.json();

        if (data.auth_url) {
          // Redirect to Trello OAuth
          window.location.href = data.auth_url;
        } else {
          throw new Error('No authorization URL received');
        }
      } else {
        throw new Error('Failed to initiate OAuth flow');
      }
    } catch (error) {
      console.error('Failed to start Trello OAuth:', error);
      toast({
        title: 'OAuth Failed',
        description: 'Failed to start Trello authentication',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, onError]);

  // Disconnect Trello integration
  const disconnectTrello = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/auth/trello/disconnect', {
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
          description: 'Trello integration has been disconnected',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error('Failed to disconnect Trello');
      }
    } catch (error) {
      console.error('Failed to disconnect Trello:', error);
      toast({
        title: 'Disconnect Failed',
        description: 'Failed to disconnect Trello integration',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, onConnectionChange, onError]);

  // Sync Trello data
  const syncTrelloData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/integrations/trello/sync', {
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
          description: `Synced ${data.boards_synced || 0} boards and ${data.cards_synced || 0} cards`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });

        // Refresh status after sync
        await checkTrelloStatus();
      } else {
        throw new Error('Failed to sync Trello data');
      }
    } catch (error) {
      console.error('Failed to sync Trello data:', error);
      toast({
        title: 'Sync Failed',
        description: 'Failed to sync Trello data',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, toast, checkTrelloStatus, onError]);

  // Load boards
  const loadBoards = useCallback(async () => {
    if (!connectionStatus.connected) return;

    try {
      const response = await fetch('/api/integrations/trello/boards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      if (response.ok) {
        const data = await response.json();
        setBoards(data.boards || []);
      }
    } catch (error) {
      console.error('Failed to load boards:', error);
    }
  }, [userId, connectionStatus.connected]);

  // Initial load
  useEffect(() => {
    checkTrelloStatus();
    checkTrelloHealth();
  }, [checkTrelloStatus, checkTrelloHealth]);

  // Load boards when connected
  useEffect(() => {
    if (connectionStatus.connected) {
      loadBoards();
    }
  }, [connectionStatus.connected, loadBoards]);

  if (!config.enabled) {
    return (
      <Card bg={bgColor} border="1px" borderColor={borderColor}>
        <CardBody>
          <Alert status="warning">
            <AlertIcon />
            <AlertTitle>Trello Integration Disabled</AlertTitle>
            <AlertDescription>
              Trello integration is currently disabled in the configuration.
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
          <Heading size="md">Trello Integration</Heading>
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
                <AlertTitle>Connect to Trello</AlertTitle>
                <AlertDescription>
                  Connect your Trello account to sync boards, cards, and manage your projects seamlessly.
                </AlertDescription>
              </Box>
            </Alert>

            <Button
              colorScheme="blue"
              onClick={startTrelloOAuth}
              isLoading={loading}
              loadingText="Connecting..."
              leftIcon={<ExternalLinkIcon />}
              size="lg"
            >
              Connect Trello Account
            </Button>

            <Text fontSize="sm" color="gray.500" textAlign="center">
              You'll be redirected to Trello to authorize access to your account
            </Text>
          </VStack>
        ) : (
          <VStack spacing={6} align="stretch">
            {/* Connection Status */}
            <Alert status="success">
              <AlertIcon />
              <Box>
                <AlertTitle>Connected to Trello</AlertTitle>
                <AlertDescription>
                  {connectionStatus.fullName && `Account: ${connectionStatus.fullName}`}
                  {connectionStatus.username && ` (@${connectionStatus.username})`}
                  {connectionStatus.lastSync && ` • Last sync: ${new Date(connectionStatus.lastSync).toLocaleString()}`}
                </AlertDescription>
              </Box>
            </Alert>

            {/* Stats */}
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
              <Stat>
                <StatLabel>Boards</StatLabel>
                <StatNumber>{connectionStatus.boardsCount || 0}</StatNumber>
                <StatHelpText>Synced boards</StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Cards</StatLabel>
                <StatNumber>{connectionStatus.cardsCount || 0}</StatNumber>
                <StatHelpText>Synced cards</StatHelpText>
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
                onClick={syncTrelloData}
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
                onClick={disconnectTrello}
                isLoading={loading}
                loadingText="Disconnecting..."
                flex={1}
              >
                Disconnect
              </Button>
            </HStack>

            {/* Boards */}
            {boards.length > 0 && (
              <Box>
                <Heading size="sm" mb={3}>
                  Recent Boards
                </Heading>
                <VStack spacing={2} align="stretch">
                  {boards.slice(0, 5).map((board) => (
                    <Card key={board.id} variant="outline" size="sm">
                      <CardBody>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={1}>
                            <Text fontWeight="medium">{board.name}</Text>
                            <HStack spacing={4}>
                              <Text fontSize="sm" color="gray.500">
                                {board.listsCount} lists
                              </Text>
                              <Text fontSize="sm" color="gray.500">
                                {board.cardsCount} cards
                              </Text>
                            </HStack>
                          </VStack>
                          <Text fontSize="sm" color="gray.500">
                            {board.starred && '⭐ '}
                            Last activity: {new Date(board.lastActivity).toLocaleDateString()}
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

export default TrelloManager;
