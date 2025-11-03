/**
 * Notion Desktop Integration Manager Component
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
  BookIcon,
  LinkIcon,
  StarIcon,
  DesktopIcon,
  CopyIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface NotionDesktopIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
  isDesktop?: boolean;
}

interface NotionDatabase {
  id: string;
  title: string;
  description?: string;
  is_inline: boolean;
  icon?: string;
  cover?: string;
  url: string;
  created_time: string;
  last_edited_time: string;
  type: 'database' | 'page';
  parent_type: string;
  archived: boolean;
  properties: Record<string, any>;
}

interface NotionPage {
  id: string;
  title: string;
  icon?: string;
  cover?: string;
  url: string;
  created_time: string;
  last_edited_time: string;
  parent_id: string;
  parent_type: string;
  archived: boolean;
  content?: string;
  properties: Record<string, any>;
}

interface NotionUser {
  id: string;
  name: string;
  email?: string;
  avatar_url?: string;
  type: 'person' | 'bot';
  person?: {
    email: string;
  };
  bot?: {
    owner?: {
      type: string;
    };
  };
}

interface OAuthTokenInfo {
  access_token: string;
  token_type: string;
  scope: string;
  workspace_id: string;
  workspace_name: string;
  workspace_icon: string;
  user_id: string;
  user_name: string;
  user_email: string;
  user_avatar: string;
  expires_at: string;
  created_at: string;
}

export const NotionDesktopManager: React.FC<NotionDesktopIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
  isDesktop = true,
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Notion',
    platform: 'notion',
    enabled: true,
    settings: {
      databases: [],
      pages: [],
      contentTypes: ['pages', 'databases', 'blocks', 'comments', 'users'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeArchived: false,
      includePrivate: true,
      includeComments: true,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['page_created', 'page_updated', 'page_deleted', 'database_updated'],
      workspaceId: '',
      workspaceName: '',
    }
  });

  const [databases, setDatabases] = useState<NotionDatabase[]>([]);
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [users, setUsers] = useState<NotionUser[]>([]);
  const [oauthTokens, setOAuthTokens] = useState<OAuthTokenInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    databasesProcessed: 0,
    pagesProcessed: 0,
    blocksProcessed: 0,
    usersProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard(oauthTokens?.access_token || '');

  // Check Notion service health
  const checkNotionHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/notion/health');
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
          errors: [data.error || 'Notion service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Notion service health']
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
      const storedTokens = await window.electronAPI?.getSecureItem('notion_tokens');
      
      if (storedTokens) {
        setOAuthTokens(storedTokens);
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: storedTokens.workspace_id,
            workspaceName: storedTokens.workspace_name,
          }
        }));
        
        toast({
          title: 'Notion Connected',
          description: `Connected to ${storedTokens.workspace_name}`,
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
      const response = await fetch('/api/auth/notion/status', {
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
            workspaceId: data.tokens.workspace_id,
            workspaceName: data.tokens.workspace_name,
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

  // Start Notion OAuth flow (Desktop App - GitLab pattern)
  const startNotionOAuth = async () => {
    try {
      // Generate OAuth URL
      const response = await fetch('/api/auth/notion/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'read_content',
            'write_content',
            'read_user',
            'write_user',
            'read_workspace',
            'write_workspace'
          ],
          redirect_uri: isDesktop ? 'http://localhost:3000/callback/notion' : undefined
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        if (isDesktop) {
          // Desktop app: Open system browser and listen for callback
          await window.electronAPI?.openExternal(data.authorization_url);
          
          // Listen for OAuth callback
          const oauthCallback = (event: any, callbackData: any) => {
            if (callbackData.type === 'notion_oauth_success') {
              window.electronAPI?.removeListener('oauth-callback', oauthCallback);
              handleOAuthCallback(callbackData.data);
            }
          };
          
          window.electronAPI?.on('oauth-callback', oauthCallback);
          
          toast({
            title: 'OAuth Started',
            description: 'Opening browser for Notion authentication...',
            status: 'info',
            duration: 5000,
          });
        } else {
          // Web app: Use popup (existing pattern)
          const popup = window.open(
            data.authorization_url,
            'notion-oauth',
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
          description: data.error || 'Failed to start Notion OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Notion OAuth',
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
      const response = await fetch('/api/auth/notion/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: callbackData.code,
          state: callbackData.state,
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setOAuthTokens(data.tokens);
        
        if (isDesktop) {
          // Store tokens securely in desktop app
          await window.electronAPI?.setSecureItem('notion_tokens', data.tokens);
        }
        
        setConfig(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            workspaceId: data.tokens.workspace_id,
            workspaceName: data.tokens.workspace_name,
          }
        }));
        
        toast({
          title: 'Notion Connected Successfully!',
          description: `Connected to ${data.tokens.workspace_name}`,
          status: 'success',
          duration: 5000,
        });
        
        // Load data
        loadDatabases();
        loadPages();
        loadUsers();
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

  // Load available databases
  const loadDatabases = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/notion/databases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          include_archived: config.settings.includeArchived,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setDatabases(data.databases);
      } else {
        setError(data.error || 'Failed to load databases');
      }
    } catch (err) {
      setError('Network error loading databases');
    } finally {
      setLoading(false);
    }
  };

  // Load pages
  const loadPages = async (databaseId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/notion/pages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          database_id: databaseId,
          include_archived: config.settings.includeArchived,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setPages(data.pages);
      } else {
        setError(data.error || 'Failed to load pages');
      }
    } catch (err) {
      setError('Network error loading pages');
    } finally {
      setLoading(false);
    }
  };

  // Load users
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/notion/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUsers(data.users);
      } else {
        setError(data.error || 'Failed to load users');
      }
    } catch (err) {
      setError('Network error loading users');
    } finally {
      setLoading(false);
    }
  };

  // Disconnect Notion
  const disconnectNotion = async () => {
    try {
      setLoading(true);
      
      if (isDesktop) {
        // Remove tokens from desktop storage
        await window.electronAPI?.removeSecureItem('notion_tokens');
      } else {
        // Remove tokens from server
        await fetch('/api/auth/notion/disconnect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });
      }
      
      setOAuthTokens(null);
      setDatabases([]);
      setPages([]);
      setUsers([]);
      
      toast({
        title: 'Notion Disconnected',
        description: 'Successfully disconnected from Notion',
        status: 'info',
        duration: 3000,
      });
    } catch (err) {
      toast({
        title: 'Disconnect Failed',
        description: 'Failed to disconnect from Notion',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Start Notion data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      databasesProcessed: 0,
      pagesProcessed: 0,
      blocksProcessed: 0,
      usersProcessed: 0,
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
        sourceType: 'notion',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Notion Ingestion Completed',
          description: `Successfully processed ${ingestionResult.pagesProcessed} pages`,
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
        title: 'Notion Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle database selection
  const handleDatabaseToggle = (databaseId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        databases: isChecked
          ? [...prev.settings.databases, databaseId]
          : prev.settings.databases.filter(id => id !== databaseId)
      }
    }));
  };

  // Handle page selection
  const handlePageToggle = (pageId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        pages: isChecked
          ? [...prev.settings.pages, pageId]
          : prev.settings.pages.filter(id => id !== pageId)
      }
    }));
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
    checkNotionHealth();
    loadOAuthTokens();
  }, [checkNotionHealth, loadOAuthTokens]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={BookIcon} w={6} h={6} color="black" />
            <Heading size="md">Notion Integration {isDesktop && <Tag size="sm" ml={2} colorScheme="blue"><TagLeftIcon as={DesktopIcon} />Desktop</Tag>}</Heading>
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
                checkNotionHealth();
                loadOAuthTokens();
                loadDatabases();
                loadPages();
                loadUsers();
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
                      <Text fontWeight="bold">Connected to Notion</Text>
                      <Text fontSize="sm" color="gray.600">
                        Workspace: {oauthTokens.workspace_name}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        User: {oauthTokens.user_name} ({oauthTokens.user_email})
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
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Scope:</Text>
                        <Text fontSize="sm">{oauthTokens.scope}</Text>
                      </HStack>
                      <HStack w="full">
                        <Text fontWeight="bold" minW="120px">Expires:</Text>
                        <Text fontSize="sm">
                          {new Date(oauthTokens.expires_at).toLocaleString()}
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
                  Notion service {health.connected ? 'healthy' : 'unhealthy'}
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
                colorScheme="black"
                leftIcon={<BookIcon />}
                onClick={startNotionOAuth}
                width="full"
                size="lg"
                isLoading={loading}
              >
                {isDesktop ? 'Connect to Notion (Desktop)' : 'Connect to Notion (Web)'}
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
              onClick={disconnectNotion}
              width="full"
            >
              Disconnect from Notion
            </Button>
          )}

          <Divider />

          {/* Data Loading for Desktop App */}
          {oauthTokens && (
            <Tabs isFitted variant="enclosed" w="full">
              <TabList mb={4}>
                {['databases', 'pages', 'users'].map((tab) => (
                  <Tab key={tab} textTransform="capitalize">
                    {tab}
                  </Tab>
                ))}
              </TabList>

              <TabPanels>
                {/* Databases Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <HStack justify="space-between" w="full">
                      <Text fontWeight="bold">Databases</Text>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<RepeatIcon />}
                        onClick={loadDatabases}
                        isLoading={loading}
                      >
                        Refresh
                      </Button>
                    </HStack>
                    
                    <VStack align="start" spacing={3} maxH="400px" overflowY="auto">
                      {databases.map((database) => (
                        <HStack key={database.id} justify="space-between" w="full">
                          <Checkbox
                            isChecked={config.settings.databases.includes(database.id)}
                            onChange={(e) => handleDatabaseToggle(database.id, e.target.checked)}
                          >
                            <VStack align="start" spacing={1}>
                              <HStack>
                                <Text fontWeight="medium">{database.title}</Text>
                                <Badge size="sm" colorScheme="blue">
                                  {database.type}
                                </Badge>
                                {database.archived && (
                                  <Badge size="sm" colorScheme="red">Archived</Badge>
                                )}
                              </HStack>
                              {database.description && (
                                <Text fontSize="sm" color="gray.600" noOfLines={1}>
                                  {database.description}
                                </Text>
                              )}
                              <Text fontSize="sm" color="gray.500">
                                Created: {new Date(database.created_time).toLocaleDateString()}
                              </Text>
                            </VStack>
                          </Checkbox>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => loadPages(database.id)}
                            leftIcon={<ViewIcon />}
                          >
                            View Pages
                          </Button>
                        </HStack>
                      ))}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Pages Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <HStack justify="space-between" w="full">
                      <Text fontWeight="bold">Pages</Text>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<RepeatIcon />}
                        onClick={loadPages}
                        isLoading={loading}
                      >
                        Refresh
                      </Button>
                    </HStack>
                    
                    <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                      {pages.map((page) => (
                        <Checkbox
                          key={page.id}
                          isChecked={config.settings.pages.includes(page.id)}
                          onChange={(e) => handlePageToggle(page.id, e.target.checked)}
                        >
                          <VStack align="start" spacing={1}>
                            <HStack>
                              <Text fontWeight="medium">{page.title}</Text>
                              {page.archived && (
                                <Badge size="sm" colorScheme="red">Archived</Badge>
                              )}
                            </HStack>
                            <Text fontSize="sm" color="gray.500">
                              Last edited: {new Date(page.last_edited_time).toLocaleDateString()}
                            </Text>
                          </VStack>
                        </Checkbox>
                      ))}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <HStack justify="space-between" w="full">
                      <Text fontWeight="bold">Users</Text>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<RepeatIcon />}
                        onClick={loadUsers}
                        isLoading={loading}
                      >
                        Refresh
                      </Button>
                    </HStack>
                    
                    <SimpleGrid columns={responsiveGridCols} spacing={3} maxH="400px" overflowY="auto">
                      {users.map((user) => (
                        <Card key={user.id} variant="outline" size="sm">
                          <CardBody p={3}>
                            <VStack spacing={2} align="center">
                              <Avatar
                                name={user.name}
                                src={user.avatar_url}
                                size="sm"
                              />
                              <VStack spacing={1} align="center">
                                <Text fontWeight="medium" fontSize="sm">
                                  {user.name}
                                </Text>
                                <Text fontSize="xs" color="gray.600">
                                  {user.email}
                                </Text>
                                <Badge size="sm" colorScheme={
                                  user.type === 'bot' ? 'orange' : 'green'
                                }>
                                  {user.type}
                                </Badge>
                              </VStack>
                            </VStack>
                          </CardBody>
                        </Card>
                      ))}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          )}

          {/* Remaining components (Advanced Settings, Ingestion, etc.) would be similar to web version */}
          <Divider />
          
          {/* Content Types */}
          <FormControl>
            <FormLabel>Content Types</FormLabel>
            <Stack direction="row" spacing={4}>
              {['pages', 'databases', 'blocks', 'comments', 'users', 'workspaces'].map((type) => (
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

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting Notion data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="black"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Databases: {ingestionStatus.databasesProcessed} | 
                    Pages: {ingestionStatus.pagesProcessed} | 
                    Blocks: {ingestionStatus.blocksProcessed} | 
                    Users: {ingestionStatus.usersProcessed}
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
                window.open('https://notion.so', '_blank');
              }}
            >
              Open Notion
            </Button>

            <Button
              colorScheme="black"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !oauthTokens ||
                (config.settings.databases.length === 0 && config.settings.pages.length === 0) ||
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

export default NotionDesktopManager;