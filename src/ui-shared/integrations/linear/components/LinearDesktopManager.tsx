/**
 * Linear Desktop Integration Manager Component
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
  Code,
  useClipboard,
  Collapse,
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
  CalendarIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface LinearDesktopIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
  isDesktop?: boolean;
}

interface OAuthTokenInfo {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
  scope: string;
  state?: string;
  user_info?: {
    id: string;
    name: string;
    displayName: string;
    email: string;
    avatarUrl: string;
    url: string;
    role: string;
    organization: {
      id: string;
      name: string;
      urlKey: string;
    };
    active: boolean;
    lastSeen: string;
  };
  created_at: string;
  expires_at: string;
}

export const LinearDesktopManager: React.FC<LinearDesktopIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
  isDesktop = true,
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Linear',
    platform: 'linear',
    enabled: true,
    settings: {
      issues: [],
      projects: [],
      teams: [],
      cycles: [],
      contentTypes: ['issues', 'projects', 'teams', 'comments', 'cycles'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeCompleted: true,
      includeCanceled: false,
      includeBacklog: true,
      includeComments: true,
      includeCycleHistory: true,
      maxItems: 500,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['Issue:Created', 'Issue:Updated', 'Issue:StatusChanged', 'Comment:Created'],
      workspaceId: '',
      workspaceName: '',
      teamId: '',
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
    issuesProcessed: 0,
    projectsProcessed: 0,
    teamsProcessed: 0,
    commentsProcessed: 0,
    cyclesProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(oauthTokens?.access_token || '');

  // Check Linear service health
  const checkLinearHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/linear/health');
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
          errors: [data.error || 'Linear service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Linear service health']
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
      const storedTokens = await window.electronAPI?.getSecureItem('linear_tokens');
      
      if (storedTokens) {
        setOAuthTokens(storedTokens);
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: storedTokens.user_info?.organization?.id || 'personal',
            workspaceName: storedTokens.user_info?.organization?.name || 'Personal Workspace',
          }
        }));
        
        toast({
          title: 'Linear Connected',
          description: `Connected as ${storedTokens.user_info?.displayName}`,
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
      const response = await fetch('/api/auth/linear/status', {
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
            workspaceId: data.tokens.user_info?.organization?.id || 'personal',
            workspaceName: data.tokens.user_info?.organization?.name || 'Personal Workspace',
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

  // Start Linear OAuth flow (Desktop App - GitLab pattern)
  const startLinearOAuth = async () => {
    try {
      // Generate OAuth URL
      const response = await fetch('/api/auth/linear/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'read',
            'write',
            'issues:read',
            'issues:write',
            'teams:read',
            'projects:read',
            'comments:read',
            'comments:write'
          ],
          redirect_uri: isDesktop ? 'http://localhost:3000/oauth/linear/callback' : 'http://localhost:3000/oauth/linear/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        if (isDesktop) {
          // Desktop app: Open system browser and listen for callback
          await window.electronAPI?.openExternal(data.authorization_url);
          
          // Listen for OAuth callback
          const oauthCallback = (event: any, callbackData: any) => {
            if (callbackData.type === 'linear_oauth_success') {
              window.electronAPI?.removeListener('oauth-callback', oauthCallback);
              handleOAuthCallback(callbackData.data);
            }
          };
          
          window.electronAPI?.on('oauth-callback', oauthCallback);
          
          toast({
            title: 'OAuth Started',
            description: 'Opening browser for Linear authentication...',
            status: 'info',
            duration: 5000,
          });
        } else {
          // Web app: Use popup (existing pattern)
          const popup = window.open(
            data.authorization_url,
            'linear-oauth',
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
          description: data.error || 'Failed to start Linear OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Linear OAuth',
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
      const response = await fetch('/api/auth/linear/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: callbackData.code,
          state: callbackData.state,
          grant_type: 'authorization_code',
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setOAuthTokens(data.tokens);
        
        if (isDesktop) {
          // Store tokens securely in desktop app
          await window.electronAPI?.setSecureItem('linear_tokens', data.tokens);
        }
        
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: data.tokens.user_info?.organization?.id || 'personal',
            workspaceName: data.tokens.user_info?.organization?.name || 'Personal Workspace',
          }
        }));
        
        toast({
          title: 'Linear Connected Successfully!',
          description: `Connected as ${data.tokens.user_info?.displayName}`,
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

  // Disconnect Linear
  const disconnectLinear = async () => {
    try {
      setLoading(true);
      
      if (isDesktop) {
        // Remove tokens from desktop storage
        await window.electronAPI?.removeSecureItem('linear_tokens');
      } else {
        // Remove tokens from server
        await fetch('/api/auth/linear/disconnect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });
      }
      
      setOAuthTokens(null);
      
      toast({
        title: 'Linear Disconnected',
        description: 'Successfully disconnected from Linear',
        status: 'info',
        duration: 3000,
      });
    } catch (err) {
      toast({
        title: 'Disconnect Failed',
        description: 'Failed to disconnect from Linear',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Start Linear data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      issuesProcessed: 0,
      projectsProcessed: 0,
      teamsProcessed: 0,
      commentsProcessed: 0,
      cyclesProcessed: 0,
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
        sourceType: 'linear',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Linear Ingestion Completed',
          description: `Successfully processed ${ingestionResult.issuesProcessed} issues`,
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
        title: 'Linear Ingestion Failed',
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
    checkLinearHealth();
    loadOAuthTokens();
  }, [checkLinearHealth, loadOAuthTokens]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ViewListIcon} w={6} h={6} color="#5E6AD2" />
            <Heading size="md">Linear Integration {isDesktop && <Tag size="sm" ml={2} colorScheme="blue"><TagLeftIcon as={DesktopIcon} />Desktop</Tag>}</Heading>
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
                checkLinearHealth();
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
                      <Text fontWeight="bold">Connected to Linear</Text>
                      <Text fontSize="sm" color="gray.600">
                        User: {oauthTokens.user_info?.displayName}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Email: {oauthTokens.user_info?.email}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Organization: {oauthTokens.user_info?.organization?.name}
                      </Text>
                    </VStack>
                  </HStack>

                  <Collapse in={showTokenDetails} animateOpacity>
                    <VStack spacing={2} align="start" w="full">
                      <Divider />
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Access Token:</Text>
                        <Code fontSize="sm" p={1} borderRadius="md" w="full" noOfLines={1}>
                          {oauthTokens.access_token}
                        </Code>
                      </HStack>
                      {oauthTokens.refresh_token && (
                        <HStack w="full">
                          <Text fontWeight="bold" minW="120px">Refresh Token:</Text>
                          <Code fontSize="sm" p={1} borderRadius="md" w="full" noOfLines={1}>
                            {oauthTokens.refresh_token}
                          </Code>
                        </HStack>
                      )}
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Expires In:</Text>
                        <Text fontSize="sm" color="gray.600">
                          {oauthTokens.expires_in} seconds
                        </Text>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Scope:</Text>
                        <Text fontSize="sm" color="gray.600" fontFamily="mono">
                          {oauthTokens.scope}
                        </Text>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">User ID:</Text>
                        <Text fontSize="sm" color="gray.600" fontFamily="mono">
                          {oauthTokens.user_info?.id}
                        </Text>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Expires:</Text>
                        <Text fontSize="sm" color="gray.600">
                          {oauthTokens.expires_at ? 
                            new Date(oauthTokens.expires_at).toLocaleString() :
                            'Unknown'
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
                  Linear service {health.connected ? 'healthy' : 'unhealthy'}
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
                onClick={startLinearOAuth}
                width="full"
                size="lg"
                isLoading={loading}
              >
                {isDesktop ? 'Connect to Linear (Desktop)' : 'Connect to Linear (Web)'}
              </Button>
              
              {isDesktop && (
                <Alert status="info" borderRadius="md">
                  <DesktopIcon />
                  <Box>
                    <Text fontWeight="bold" mb={1}>Desktop App OAuth Flow</Text>
                    <Text fontSize="sm" color="gray.600">
                      This will open your default browser for authentication. 
                      After completing the flow, tokens will be stored securely on your desktop.
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
              onClick={disconnectLinear}
              width="full"
            >
              Disconnect from Linear
            </Button>
          )}

          <Divider />

          {/* Content Types */}
          <FormControl>
            <FormLabel>Content Types</FormLabel>
            <Stack direction="row" spacing={4} wrap="wrap">
              {['issues', 'projects', 'teams', 'comments', 'cycles'].map((type) => (
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
                    <Text>Ingesting Linear data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Issues: {ingestionStatus.issuesProcessed} | 
                    Projects: {ingestionStatus.projectsProcessed} | 
                    Teams: {ingestionStatus.teamsProcessed} | 
                    Comments: {ingestionStatus.commentsProcessed} | 
                    Cycles: {ingestionStatus.cyclesProcessed}
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
                window.open('https://linear.app', '_blank');
              }}
            >
              Open Linear
            </Button>

            <Button
              colorScheme="blue"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !oauthTokens ||
                (config.settings.issues.length === 0 && config.settings.teams.length === 0) ||
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

export default LinearDesktopManager;