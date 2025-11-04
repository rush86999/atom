/**
 * GitHub Integration Manager Component
 * Complete GitHub OAuth and API integration following Jira pattern
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
} from '@chakra-ui/react';
import {
  GitHubLogoIcon,
  AddIcon,
  ViewIcon,
  DeleteIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface GitHubIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

export const GitHubManager: React.FC<GitHubIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'GitHub',
    platform: 'github',
    enabled: true,
    settings: {
      repositories: [],
      organizations: [],
      workflows: ['issues', 'pull_requests', 'commits', 'releases'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeForks: false,
      includeArchived: false,
      maxRepos: 100,
      realTimeSync: false,
      syncFrequency: 'hourly',
      webhookEvents: ['push', 'pull_request', 'issues', 'release'],
    }
  });

  const [repositories, setRepositories] = useState<any[]>([]);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedOrg, setSelectedOrg] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    repositoriesProcessed: 0,
    issuesProcessed: 0,
    pullRequestsProcessed: 0,
    commitsProcessed: 0,
    errors: []
  });

  const toast = useToast();

  // Check GitHub service health
  const checkGitHubHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/communication/health');
      const data = await response.json();
      
      if (data.services?.github) {
        setHealth({
          connected: data.services.github.status === 'healthy',
          lastSync: new Date().toISOString(),
          errors: data.services.github.error ? [data.services.github.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check GitHub service health']
      });
    }
  }, []);

  // Load available repositories
  const loadRepositories = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/github/repositories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          organizations: selectedOrg ? [selectedOrg] : [],
          include_forks: config.settings.includeForks,
          include_archived: config.settings.includeArchived,
          limit: config.settings.maxRepos
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setRepositories(data.repositories);
      } else {
        setError(data.error || 'Failed to load repositories');
      }
    } catch (err) {
      setError('Network error loading repositories');
    } finally {
      setLoading(false);
    }
  };

  // Load available organizations
  const loadOrganizations = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/github/organizations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setOrganizations(data.organizations);
      } else {
        setError(data.error || 'Failed to load organizations');
      }
    } catch (err) {
      setError('Network error loading organizations');
    } finally {
      setLoading(false);
    }
  };

  // Start GitHub OAuth flow
  const startGitHubOAuth = async () => {
    try {
      const response = await fetch('/api/auth/github/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: ['repo', 'user:email', 'read:org', 'admin:repo_hook', 'admin:org_hook']
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'github-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkGitHubAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start GitHub OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to GitHub OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check GitHub auth status
  const checkGitHubAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/github/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'GitHub Connected',
          description: 'Successfully authenticated with GitHub',
          status: 'success',
          duration: 3000,
        });
        
        // Load repositories and organizations
        loadRepositories();
        loadOrganizations();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to GitHub first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify GitHub connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start GitHub data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      repositoriesProcessed: 0,
      issuesProcessed: 0,
      pullRequestsProcessed: 0,
      commitsProcessed: 0,
      errors: []
    }));

    try {
      // Configure the data source in ATOM pipeline
      const dataSourceConfig = {
        ...config,
        health: health || { connected: false, lastSync: '', errors: [] }
      };

      if (onConfigurationChange) {
        onConfigurationChange(dataSourceConfig);
      }

      // Start ingestion through ATOM pipeline
      const ingestionResult = await atomIngestionPipeline.startIngestion({
        sourceType: 'github',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'GitHub Ingestion Completed',
          description: `Successfully processed ${ingestionResult.repositoriesProcessed} repositories`,
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
        title: 'GitHub Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle repository selection
  const handleRepoToggle = (repoId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        repositories: isChecked
          ? [...prev.settings.repositories, repoId]
          : prev.settings.repositories.filter(id => id !== repoId)
      }
    }));
  };

  // Handle organization selection
  const handleOrgSelect = (orgId: string) => {
    setSelectedOrg(orgId);
    loadRepositories();
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
    checkGitHubHealth();
  }, []);

  useEffect(() => {
    if (selectedOrg) {
      loadRepositories();
    }
  }, [selectedOrg]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <Heading size="md">GitHub Integration</Heading>
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
                checkGitHubHealth();
                loadRepositories();
                loadOrganizations();
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
          {/* Health Status */}
          {health && (
            <Alert status={health.connected ? 'success' : 'warning'}>
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">
                  GitHub service {health.connected ? 'healthy' : 'unhealthy'}
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

          {/* Authentication */}
          {!health?.connected && (
            <VStack>
              <Button
                colorScheme="gray"
                leftIcon={<GitHubLogoIcon />}
                onClick={startGitHubOAuth}
                width="full"
                size="lg"
              >
                Connect to GitHub
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with GitHub using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Organization Selection */}
          {organizations.length > 0 && (
            <FormControl>
              <FormLabel>Organizations</FormLabel>
              <Select
                placeholder="Select organization (optional)"
                value={selectedOrg}
                onChange={(e) => handleOrgSelect(e.target.value)}
                isDisabled={loading}
              >
                <option value="">All repositories</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.login}>
                    {org.login} ({org.public_repos} repos)
                  </option>
                ))}
              </Select>
              <FormHelperText>
                Filter repositories by organization
              </FormHelperText>
            </FormControl>
          )}

          {/* Repository Selection */}
          {repositories.length > 0 && (
            <FormControl>
              <FormLabel>Repositories</FormLabel>
              <VStack align="start" spacing={2} maxH="200px" overflowY="auto">
                {repositories.map((repo) => (
                  <Checkbox
                    key={repo.id}
                    isChecked={config.settings.repositories.includes(repo.id)}
                    onChange={(e) => handleRepoToggle(repo.id, e.target.checked)}
                  >
                    <HStack>
                      <Text>{repo.name}</Text>
                      {repo.private && (
                        <Badge size="sm" colorScheme="yellow">Private</Badge>
                      )}
                      {repo.fork && (
                        <Badge size="sm" colorScheme="gray">Fork</Badge>
                      )}
                    </HStack>
                  </Checkbox>
                ))}
              </VStack>
              <FormHelperText>
                Select repositories to ingest data from
              </FormHelperText>
            </FormControl>
          )}

          <Divider />

          {/* Data Types */}
          <FormControl>
            <FormLabel>Data Types</FormLabel>
            <Stack direction="row" spacing={4}>
              {['issues', 'pull_requests', 'commits', 'releases'].map((type) => (
                <Checkbox
                  key={type}
                  isChecked={config.settings.workflows.includes(type)}
                  onChange={(e) => {
                    const newTypes = e.target.checked
                      ? [...config.settings.workflows, type]
                      : config.settings.workflows.filter(t => t !== type);
                    updateConfig('workflows', newTypes);
                  }}
                >
                  {type.replace(/_/g, ' ').charAt(0).toUpperCase() + type.replace(/_/g, ' ').slice(1)}
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

          {/* Advanced Settings */}
          <Collapse in={showAdvanced} animateOpacity>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Max Repositories</FormLabel>
                <Input
                  type="number"
                  value={config.settings.maxRepos}
                  onChange={(e) => updateConfig('maxRepos', parseInt(e.target.value))}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Sync Frequency</FormLabel>
                <Select
                  value={config.settings.syncFrequency}
                  onChange={(e) => updateConfig('syncFrequency', e.target.value)}
                >
                  <option value="realtime">Real-time</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </FormControl>

              <HStack>
                <Checkbox
                  isChecked={config.settings.includeForks}
                  onChange={(e) => updateConfig('includeForks', e.target.checked)}
                >
                  Include Forks
                </Checkbox>
                <Checkbox
                  isChecked={config.settings.includeArchived}
                  onChange={(e) => updateConfig('includeArchived', e.target.checked)}
                >
                  Include Archived
                </Checkbox>
                <Checkbox
                  isChecked={config.settings.realTimeSync}
                  onChange={(e) => updateConfig('realTimeSync', e.target.checked)}
                >
                  Real-time Sync
                </Checkbox>
              </HStack>
            </VStack>
          </Collapse>

          <Button
            variant="outline"
            leftIcon={<ViewIcon />}
            onClick={() => setShowAdvanced(!showAdvanced)}
            alignSelf="flex-start"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
          </Button>

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting GitHub data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Repositories: {ingestionStatus.repositoriesProcessed} | 
                    Issues: {ingestionStatus.issuesProcessed} | 
                    PRs: {ingestionStatus.pullRequestsProcessed} | 
                    Commits: {ingestionStatus.commitsProcessed}
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
                window.open('https://github.com/settings/applications', '_blank');
              }}
            >
              GitHub Settings
            </Button>

            <Button
              colorScheme="green"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                config.settings.repositories.length === 0 ||
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

export default GitHubManager;