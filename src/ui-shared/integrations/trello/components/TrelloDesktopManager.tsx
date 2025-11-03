/**
 * Trello Desktop Integration Manager Component
 * Desktop app OAuth flow following GitLab pattern
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Stack,
  Badge,
  Progress,
  Alert,
  AlertIcon,
  Divider,
  Flex,
  Icon,
  Tooltip,
  useToast,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Checkbox,
  Select,
  Switch,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useColorModeValue,
  SimpleGrid,
  Avatar,
  useBreakpointValue,
  useTab,
  TabList,
  TabPanels,
  TabPanel,
  Tabs,
  Tag,
  TagLabel,
  TagLeftIcon,
  Code,
  useClipboard,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  InfoIcon,
  ViewListIcon,
  ArchiveIcon,
  UserIcon,
  CopyIcon,
  DesktopIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface TrelloDesktopIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
  isDesktop?: boolean;
}

interface OAuthTokenInfo {
  token: string;
  tokenSecret: string;
  expiration: string;
  verification_code?: string;
  app_id?: string;
  app_name?: string;
  app_type?: string;
  app_website?: string;
  domain?: string;
  memberId?: string;
  memberName?: string;
  memberEmail?: string;
  memberUsername?: string;
  memberAvatar?: string;
  enterpriseId?: string;
  enterpriseName?: string;
  created_at: string;
  expires_at: string;
}

export const TrelloDesktopManager: React.FC<TrelloDesktopIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
  isDesktop = true,
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Trello',
    platform: 'trello',
    enabled: true,
    settings: {
      boards: [],
      lists: [],
      cards: [],
      contentTypes: ['boards', 'lists', 'cards', 'checklists', 'members', 'comments', 'attachments'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeArchived: false,
      includeClosed: true,
      includeComments: true,
      includeAttachments: true,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['card_created', 'card_updated', 'card_deleted', 'list_created', 'board_updated'],
      workspaceId: '',
      workspaceName: '',
    }
  });

  const [oauthTokens, setOAuthTokens] = useState<OAuthTokenInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    boardsProcessed: 0,
    listsProcessed: 0,
    cardsProcessed: 0,
    membersProcessed: 0,
    commentsProcessed: 0,
    attachmentsProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(oauthTokens?.token || '');

  // Check Trello service health
  const checkTrelloHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/trello/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setHealth({
          connected: true,
          lastSync: new Date().toISOString(),
          errors: []
        });
      } else {
        setHealth({
          connected: false,
          lastSync: new Date().toISOString(),
          errors: [data.error || 'Trello service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Trello service health']
      });
    }
  }, []);

  // Load OAuth tokens from desktop storage
  const loadOAuthTokens = useCallback(async () => {
    try {
      if (!isDesktop) {
        // For web app, check server tokens
        return await checkOAuthStatus();
      }
      
      // Desktop app: Load from secure storage
      const storedTokens = await window.electronAPI?.getSecureItem('trello_tokens');
      
      if (storedTokens) {
        setOAuthTokens(storedTokens);
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: storedTokens.enterpriseId || 'personal',
            workspaceName: storedTokens.enterpriseName || 'Personal Workspace',
          }
        }));
        
        toast({
          title: 'Trello Connected',
          description: `Connected as ${storedTokens.memberName}`,
          status: 'success',
          duration: 3000,
        });
        
        return true;
      }
      
      return false;
    } catch (err) {
      console.error('Error loading OAuth tokens:', err);
      return false;
    }
  }, [isDesktop]);

  // Check OAuth status
  const checkOAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/trello/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        setOAuthTokens(data.tokens);
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: data.tokens.enterpriseId || 'personal',
            workspaceName: data.tokens.enterpriseName || 'Personal Workspace',
          }
        }));
        
        return true;
      }
      
      return false;
    } catch (err) {
      console.error('Error checking OAuth status:', err);
      return false;
    }
  };

  // Start Trello OAuth flow (Desktop App - GitLab pattern)
  const startTrelloOAuth = async () => {
    try {
      // Generate OAuth URL
      const response = await fetch('/api/auth/trello/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'read',
            'write',
            'account'
          ],
          expiration: 'never',
          name: 'ATOM Platform Integration',
          redirect_uri: isDesktop ? 'http://localhost:3000/callback/trello' : undefined
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        if (isDesktop) {
          // Desktop app: Open system browser and listen for callback
          await window.electronAPI?.openExternal(data.authorization_url);
          
          // Listen for OAuth callback
          const oauthCallback = (event: any, callbackData: any) => {
            if (callbackData.type === 'trello_oauth_success') {
              window.electronAPI?.removeListener('oauth-callback', oauthCallback);
              handleOAuthCallback(callbackData.data);
            }
          };
          
          window.electronAPI?.on('oauth-callback', oauthCallback);
          
          toast({
            title: 'OAuth Started',
            description: 'Opening browser for Trello authentication...',
            status: 'info',
            duration: 5000,
          });
        } else {
          // Web app: Use popup (existing pattern)
          const popup = window.open(
            data.authorization_url,
            'trello-oauth',
            'width=500,height=600,scrollbars=yes,resizable=yes'
          );
          
          // Listen for OAuth completion
          const checkOAuth = setInterval(() => {
            if (popup?.closed) {
              clearInterval(checkOAuth);
              checkOAuthStatus();
            }
          }, 1000);
        }
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Trello OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Trello OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Handle OAuth callback
  const handleOAuthCallback = async (callbackData: any) => {
    try {
      setLoading(true);
      
      // Process OAuth callback
      const response = await fetch('/api/auth/trello/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: callbackData.token,
          verifier: callbackData.verifier,
          app_id: callbackData.app_id,
          app_name: callbackData.app_name,
          app_type: callbackData.app_type,
          app_website: callbackData.app_website,
          domain: callbackData.domain,
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setOAuthTokens(data.tokens);
        
        if (isDesktop) {
          // Store tokens securely in desktop app
          await window.electronAPI?.setSecureItem('trello_tokens', data.tokens);
        }
        
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: data.tokens.enterpriseId || 'personal',
            workspaceName: data.tokens.enterpriseName || 'Personal Workspace',
          }
        }));
        
        toast({
          title: 'Trello Connected Successfully!',
          description: `Connected as ${data.tokens.memberName}`,
          status: 'success',
          duration: 5000,
        });
      } else {
        throw new Error(data.error || 'OAuth callback failed');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('OAuth callback error');
      
      toast({
        title: 'OAuth Callback Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Disconnect Trello
  const disconnectTrello = async () => {
    try {
      setLoading(true);
      
      if (isDesktop) {
        // Remove tokens from desktop storage
        await window.electronAPI?.removeSecureItem('trello_tokens');
      } else {
        // Remove tokens from server
        await fetch('/api/auth/trello/disconnect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });
      }
      
      setOAuthTokens(null);
      
      toast({
        title: 'Trello Disconnected',
        description: 'Successfully disconnected from Trello',
        status: 'info',
        duration: 3000,
      });
    } catch (err) {
      toast({
        title: 'Disconnect Failed',
        description: 'Failed to disconnect from Trello',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Start Trello data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      boardsProcessed: 0,
      listsProcessed: 0,
      cardsProcessed: 0,
      membersProcessed: 0,
      commentsProcessed: 0,
      attachmentsProcessed: 0,
      errors: []
    }));

    try {
      // Configure data source in ATOM pipeline
      const dataSourceConfig = {
        ...config,
        health: health || { connected: false, lastSync: '', errors: [] }
      };

      if (onConfigurationChange) {
        onConfigurationChange(dataSourceConfig);
      }

      // Start ingestion through ATOM pipeline
      const ingestionResult = await atomIngestionPipeline.startIngestion({
        sourceType: 'trello',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Trello Ingestion Completed',
          description: `Successfully processed ${ingestionResult.cardsProcessed} cards`,
          status: 'success',
          duration: 5000,
        });

        if (onIngestionComplete) {
          onIngestionComplete(ingestionResult);
        }
      } else {
        throw new Error(ingestionResult.error || 'Ingestion failed');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      
      setIngestionStatus(prev => ({
        ...prev,
        running: false,
        errors: [...prev.errors, error.message]
      }));

      toast({
        title: 'Trello Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Update configuration
  const updateConfig = (path: string, value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current: any = newConfig.settings;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current[keys[i]] = current[keys[i]] || {};
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      
      if (onConfigurationChange) {
        onConfigurationChange(newConfig);
      }
      
      return newConfig;
    });
  };

  useEffect(() => {
    checkTrelloHealth();
    loadOAuthTokens();
  }, [checkTrelloHealth, loadOAuthTokens]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ViewListIcon} w={6} h={6} color="#0079BF" />
            <Heading size="md">Trello Integration {isDesktop && <Tag size="sm" ml={2} colorScheme="blue"><TagLeftIcon as={DesktopIcon} />Desktop</Tag>}</Heading>
          </HStack>
          <HStack>
            <Badge
              colorScheme={health?.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={health?.connected ? CheckCircleIcon : WarningIcon} mr={1} />
              {health?.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={() => {
                checkTrelloHealth();
                loadOAuthTokens();
              }}
              isLoading={loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* OAuth Token Display (Desktop App Pattern) */}
          {oauthTokens && (
            <Card bg={bgColor} border="1px" borderColor={borderColor}>
              <CardBody>
                <VStack spacing={4} align="start">
                  <HStack w="full" justify="space-between">
                    <Heading size="sm">OAuth Connection</Heading>
                    <HStack>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<CopyIcon />}
                        onClick={onCopy}
                      >
                        {hasCopied ? 'Copied!' : 'Copy Token'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<InfoIcon />}
                        onClick={() => setShowTokenDetails(!showTokenDetails)}
                      >
                        Details
                      </Button>
                    </HStack>
                  </HStack>
                  
                  <HStack>
                    <Icon as={CheckCircleIcon} w={5} h={5} color="green.500" />
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Connected to Trello</Text>
                      <Text fontSize="sm" color="gray.600">
                        User: {oauthTokens.memberName}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Enterprise: {oauthTokens.enterpriseName || 'Personal'}
                      </Text>
                    </VStack>
                  </HStack>

                  <Collapse in={showTokenDetails} animateOpacity>
                    <VStack spacing={2} align="start" w="full">
                      <Divider />
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Access Token:</Text>
                        <Code fontSize="sm" p={1} borderRadius="md" w="full" noOfLines={1}>
                          {oauthTokens.token}
                        </Code>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Token Secret:</Text>
                        <Code fontSize="sm" p={1} borderRadius="md" w="full" noOfLines={1}>
                          {oauthTokens.tokenSecret}
                        </Code>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Member ID:</Text>
                        <Text fontSize="sm" color="gray.600" fontFamily="mono">
                          {oauthTokens.memberId}
                        </Text>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Expires:</Text>
                        <Text fontSize="sm" color="gray.600">
                          {oauthTokens.expires_at ? 
                            new Date(oauthTokens.expires_at).toLocaleString() :
                            'Never'
                          }
                        </Text>
                      </HStack>
                    </VStack>
                  </Collapse>
                </VStack>
              </CardBody>
            </Card>
          )}

          {/* Health Status */}
          {health && (
            <Alert status={health.connected ? 'success' : 'warning'}>
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">
                  Trello service {health.connected ? 'healthy' : 'unhealthy'}
                </Text>
                {health.errors.length > 0 && (
                  <Text fontSize="sm" color="red.500">
                    {health.errors.join(', ')}
                  </Text>
                )}
              </Box>
            </Alert>
          )}

          {/* Error Display */}
          {error && (
            <Alert status="error">
              <AlertIcon />
              <Text>{error}</Text>
            </Alert>
          )}

          {/* Authentication (Desktop App Pattern) */}
          {!oauthTokens && (
            <VStack>
              <Text fontSize="lg" fontWeight="bold" color="gray.700">
                {isDesktop ? 'Desktop App Authentication' : 'Web App Authentication'}
              </Text>
              <Text fontSize="sm" color="gray.600" textAlign="center" maxW="400px">
                {isDesktop 
                  ? 'Click below to start OAuth flow. Your system browser will open for authentication.'
                  : 'Click below to start OAuth flow. A popup will open for authentication.'
                }
              </Text>
              
              <Button
                colorScheme="blue"
                leftIcon={<ViewListIcon />}
                onClick={startTrelloOAuth}
                width="full"
                size="lg"
                isLoading={loading}
              >
                {isDesktop ? 'Connect to Trello (Desktop)' : 'Connect to Trello (Web)'}
              </Button>
              
              {isDesktop && (
                <Alert status="info" borderRadius="md">
                  <InfoIcon />
                  <Box>
                    <Text fontWeight="bold" mb={1}>Desktop App OAuth Flow</Text>
                    <Text fontSize="sm" color="gray.600">
                      This will open your default browser for authentication. 
                      After completing the flow, the tokens will be stored securely on your desktop.
                    </Text>
                  </Box>
                </Alert>
              )}
            </VStack>
          )}

          {/* Disconnect Button */}
          {oauthTokens && (
            <Button
              colorScheme="red"
              variant="outline"
              leftIcon={<WarningIcon />}
              onClick={disconnectTrello}
              width="full"
            >
              Disconnect from Trello
            </Button>
          )}

          <Divider />

          {/* Content Types */}
          <FormControl>
            <FormLabel>Content Types</FormLabel>
            <Stack direction="row" spacing={4} wrap="wrap">
              {['boards', 'lists', 'cards', 'checklists', 'members', 'comments', 'attachments', 'actions'].map((type) => (
                <Checkbox
                  key={type}
                  isChecked={config.settings.contentTypes.includes(type)}
                  onChange={(e) => {
                    const newTypes = e.target.checked
                      ? [...config.settings.contentTypes, type]
                      : config.settings.contentTypes.filter(t => t !== type);
                    updateConfig('contentTypes', newTypes);
                  }}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </Checkbox>
              ))}
            </Stack>
          </FormControl>

          {/* Date Range */}
          <FormControl>
            <FormLabel>Date Range</FormLabel>
            <HStack>
              <Input
                type="date"
                value={config.settings.dateRange.start.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.start', new Date(e.target.value))}
              />
              <Text>to</Text>
              <Input
                type="date"
                value={config.settings.dateRange.end.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.end', new Date(e.target.value))}
              />
            </HStack>
          </FormControl>

          <Divider />

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting Trello data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Boards: {ingestionStatus.boardsProcessed} | 
                    Lists: {ingestionStatus.listsProcessed} | 
                    Cards: {ingestionStatus.cardsProcessed} | 
                    Members: {ingestionStatus.membersProcessed}
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          )}

          {/* Action Buttons */}
          <HStack justify="space-between" w="full">
            <Button
              variant="outline"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => {
                window.open('https://trello.com', '_blank');
              }}
            >
              Open Trello
            </Button>

            <Button
              colorScheme="blue"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !oauthTokens ||
                (config.settings.boards.length === 0 && config.settings.lists.length === 0) ||
                ingestionStatus.running
              }
              isLoading={ingestionStatus.running}
            >
              {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default TrelloDesktopManager;