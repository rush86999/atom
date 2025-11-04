/**
 * Next.js Integration Manager Component
 * Complete Next.js/Vercel integration for project management and deployment tracking
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
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tag,
  Spinner,
} from '@chakra-ui/react';
import {
  ViewIcon,
  DeleteIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  CodeIcon,
  RocketIcon,
  AnalyticsIcon,
  BuildIcon,
  StarIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';
import {
  NextjsProject,
  NextjsBuild,
  NextjsDeployment,
  NextjsAnalytics,
  NextjsConfig,
  NextjsIntegrationProps,
  NextjsDataSourceConfig,
} from '../types';
import { detectPlatform } from '@shared/ui-shared/integrations/_template/baseIntegration';

export const NextjsManager: React.FC<NextjsIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<NextjsConfig>({
    platform: 'nextjs',
    projects: [],
    deployments: [],
    builds: [],
    includeAnalytics: true,
    includeBuildLogs: true,
    includeEnvironmentVariables: false,
    realTimeSync: true,
    webhookEvents: ['deployment.created', 'deployment.ready', 'deployment.error', 'build.ready'],
    syncFrequency: 'realtime',
    dateRange: {
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
      end: new Date(),
    },
    maxProjects: 50,
    maxBuilds: 100,
  });

  const [projects, setProjects] = useState<NextjsProject[]>([]);
  const [builds, setBuilds] = useState<NextjsBuild[]>([]);
  const [deployments, setDeployments] = useState<NextjsDeployment[]>([]);
  const [selectedProject, setSelectedProject] = useState<NextjsProject | null>(null);
  const [analytics, setAnalytics] = useState<NextjsAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showProjectDetails, setShowProjectDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    projectsProcessed: 0,
    buildsProcessed: 0,
    deploymentsProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const platform = detectPlatform();

  // Check Next.js service health
  const checkNextjsHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/nextjs/health');
      const data = await response.json();
      
      if (data.services?.nextjs) {
        setHealth({
          connected: data.services.nextjs.status === 'healthy',
          lastSync: new Date().toISOString(),
          errors: data.services.nextjs.error ? [data.services.nextjs.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Next.js service health']
      });
    }
  }, []);

  // Load Next.js projects
  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/nextjs/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: config.maxProjects,
          include_builds: true,
          include_deployments: true,
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setProjects(data.projects || []);
        if (data.builds) setBuilds(data.builds);
        if (data.deployments) setDeployments(data.deployments);
      } else {
        setError(data.error || 'Failed to load Next.js projects');
      }
    } catch (err) {
      setError('Network error loading Next.js projects');
    } finally {
      setLoading(false);
    }
  };

  // Load project analytics
  const loadProjectAnalytics = async (projectId: string) => {
    try {
      const response = await fetch('/api/integrations/nextjs/analytics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_id: projectId,
          date_range: config.dateRange,
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setAnalytics(data.analytics);
      } else {
        console.error('Failed to load analytics:', data.error);
      }
    } catch (err) {
      console.error('Error loading analytics:', err);
    }
  };

  // Start Next.js OAuth flow
  const startNextjsOAuth = async () => {
    try {
      const response = await fetch('/api/auth/nextjs/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: ['read', 'write', 'projects', 'deployments', 'builds'],
          platform,
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        if (platform === 'tauri') {
          // For Tauri desktop app, open system browser
          window.open(data.authorization_url, '_blank');
        } else {
          // For web, open popup
          const popup = window.open(
            data.authorization_url,
            'nextjs-oauth',
            'width=500,height=600,scrollbars=yes,resizable=yes'
          );
          
          // Listen for OAuth completion
          const checkOAuth = setInterval(() => {
            if (popup?.closed) {
              clearInterval(checkOAuth);
              checkNextjsAuthStatus();
            }
          }, 1000);
        }
        
        // Listen for OAuth success message
        const messageListener = (event: MessageEvent) => {
          if (event.data.type === 'nextjs_oauth_success') {
            window.removeEventListener('message', messageListener);
            checkNextjsAuthStatus();
          }
        };
        window.addEventListener('message', messageListener);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Next.js OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Next.js OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Next.js auth status
  const checkNextjsAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/nextjs/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Next.js Connected',
          description: 'Successfully authenticated with Next.js/Vercel',
          status: 'success',
          duration: 3000,
        });
        
        // Load projects
        loadProjects();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Next.js/Vercel first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Next.js connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Next.js data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      projectsProcessed: 0,
      buildsProcessed: 0,
      deploymentsProcessed: 0,
      errors: []
    }));

    try {
      // Configure data source in ATOM pipeline
      const dataSourceConfig: NextjsDataSourceConfig = {
        name: 'Next.js',
        platform: 'nextjs',
        enabled: true,
        settings: config,
        health: health || { connected: false, lastSync: '', errors: [] }
      };

      if (onConfigurationChange) {
        onConfigurationChange(dataSourceConfig);
      }

      // Start ingestion through ATOM pipeline
      const ingestionResult = await atomIngestionPipeline.startIngestion({
        sourceType: 'nextjs',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Next.js Ingestion Completed',
          description: `Successfully processed ${ingestionResult.projectsProcessed} projects`,
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
        title: 'Next.js Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle project selection
  const handleProjectToggle = (projectId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      projects: isChecked
        ? [...prev.projects, projectId]
        : prev.projects.filter(id => id !== projectId)
    }));
  };

  // Handle project details
  const handleProjectSelect = (project: NextjsProject) => {
    setSelectedProject(project);
    setShowProjectDetails(true);
    loadProjectAnalytics(project.id);
  };

  // Update configuration
  const updateConfig = (path: string, value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current: any = newConfig;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current[keys[i]] = current[keys[i]] || {};
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      
      if (onConfigurationChange) {
        onConfigurationChange({
          name: 'Next.js',
          platform: 'nextjs',
          enabled: true,
          settings: newConfig,
          health: health || { connected: false, lastSync: '', errors: [] }
        });
      }
      
      return newConfig;
    });
  };

  useEffect(() => {
    checkNextjsHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={CodeIcon} w={6} h={6} color="blue.500" />
            <Heading size="md">Next.js Integration</Heading>
            <Badge colorScheme="blue">Vercel</Badge>
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
                checkNextjsHealth();
                loadProjects();
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
                  Next.js service {health.connected ? 'healthy' : 'unhealthy'}
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
                colorScheme="blue"
                leftIcon={<CodeIcon />}
                onClick={startNextjsOAuth}
                width="full"
                size="lg"
              >
                Connect to Next.js/Vercel
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Connect your Vercel account to manage Next.js projects and deployments
              </Text>
            </VStack>
          )}

          {/* Projects Grid */}
          {projects.length > 0 && (
            <VStack align="stretch">
              <HStack justify="space-between">
                <Text fontWeight="bold" fontSize="lg">
                  Projects ({projects.length})
                </Text>
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() => window.open('https://vercel.com/dashboard', '_blank')}
                >
                  Open Vercel Dashboard
                </Button>
              </HStack>

              <SimpleGrid columns={responsiveGridCols} spacing={4}>
                {projects.map((project) => (
                  <Card key={project.id} cursor="pointer" onClick={() => handleProjectSelect(project)}>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <HStack justify="space-between" w="full">
                          <Checkbox
                            isChecked={config.projects.includes(project.id)}
                            onChange={(e) => {
                              e.stopPropagation();
                              handleProjectToggle(project.id, e.target.checked);
                            }}
                          />
                          <Badge
                            colorScheme={
                              project.status === 'active' ? 'green' :
                              project.status === 'archived' ? 'gray' : 'yellow'
                            }
                          >
                            {project.status}
                          </Badge>
                        </HStack>
                        
                        <HStack>
                          <Icon as={CodeIcon} color="blue.500" />
                          <Text fontWeight="bold" noOfLines={1}>
                            {project.name}
                          </Text>
                        </HStack>
                        
                        {project.description && (
                          <Text fontSize="sm" color="gray.600" noOfLines={2}>
                            {project.description}
                          </Text>
                        )}

                        <HStack wrap="wrap" gap={1}>
                          {project.deployment && (
                            <Badge size="sm" colorScheme="green">
                              {project.deployment.platform}
                            </Badge>
                          )}
                          <Badge size="sm" colorScheme="blue">
                            {project.framework}
                          </Badge>
                          <Badge size="sm" colorScheme="purple">
                            {project.runtime}
                          </Badge>
                        </HStack>

                        {project.domains.length > 0 && (
                          <Text fontSize="xs" color="gray.500" noOfLines={1}>
                            {project.domains[0]}
                          </Text>
                        )}

                        {project.metrics && (
                          <HStack fontSize="xs" color="gray.500">
                            <Text>👁 {project.metrics.pageViews}</Text>
                            <Text>⚡ {project.metrics.errors} errors</Text>
                          </HStack>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
            </VStack>
          )}

          <Divider />

          {/* Data Types */}
          <FormControl>
            <FormLabel>Data to Ingest</FormLabel>
            <Stack direction="row" spacing={4} wrap="wrap">
              {[
                { key: 'includeAnalytics', label: 'Analytics', icon: AnalyticsIcon },
                { key: 'includeBuildLogs', label: 'Build Logs', icon: BuildIcon },
                { key: 'includeEnvironmentVariables', label: 'Environment Variables', icon: SettingsIcon },
              ].map(({ key, label, icon }) => (
                <Checkbox
                  key={key}
                  isChecked={config[key as keyof NextjsConfig] as boolean}
                  onChange={(e) => updateConfig(key, e.target.checked)}
                >
                  <HStack spacing={1}>
                    <Icon as={icon} w={4} h={4} />
                    <Text>{label}</Text>
                  </HStack>
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
                value={config.dateRange.start.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.start', new Date(e.target.value))}
              />
              <Text>to</Text>
              <Input
                type="date"
                value={config.dateRange.end.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.end', new Date(e.target.value))}
              />
            </HStack>
          </FormControl>

          {/* Advanced Settings */}
          {showAdvanced && (
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Sync Frequency</FormLabel>
                <Select
                  value={config.syncFrequency}
                  onChange={(e) => updateConfig('syncFrequency', e.target.value)}
                >
                  <option value="realtime">Real-time</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </FormControl>

              <HStack>
                <FormControl>
                  <FormLabel>Max Projects</FormLabel>
                  <Input
                    type="number"
                    value={config.maxProjects}
                    onChange={(e) => updateConfig('maxProjects', parseInt(e.target.value))}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Max Builds</FormLabel>
                  <Input
                    type="number"
                    value={config.maxBuilds}
                    onChange={(e) => updateConfig('maxBuilds', parseInt(e.target.value))}
                  />
                </FormControl>
              </HStack>

              <Checkbox
                isChecked={config.realTimeSync}
                onChange={(e) => updateConfig('realTimeSync', e.target.checked)}
              >
                Enable Real-time Sync
              </Checkbox>
            </VStack>
          )}

          <Button
            variant="outline"
            leftIcon={<SettingsIcon />}
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
                    <Text>Ingesting Next.js data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Projects: {ingestionStatus.projectsProcessed} | 
                    Builds: {ingestionStatus.buildsProcessed} | 
                    Deployments: {ingestionStatus.deploymentsProcessed}
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
                window.open('https://vercel.com/dashboard', '_blank');
              }}
            >
              Open Vercel
            </Button>

            <Button
              colorScheme="green"
              leftIcon={<RocketIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                config.projects.length === 0 ||
                ingestionStatus.running
              }
              isLoading={ingestionStatus.running}
            >
              {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
            </Button>
          </HStack>
        </VStack>
      </CardBody>

      {/* Project Details Modal */}
      <Modal
        isOpen={showProjectDetails}
        onClose={() => setShowProjectDetails(false)}
        size="4xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <Icon as={CodeIcon} color="blue.500" />
              <Text>{selectedProject?.name}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody maxH="70vh" overflowY="auto">
            {selectedProject && (
              <VStack spacing={6} align="stretch">
                {/* Project Info */}
                <Card>
                  <CardBody>
                    <VStack align="start" spacing={3}>
                      <Text fontWeight="bold">Project Information</Text>
                      {selectedProject.description && (
                        <Text>{selectedProject.description}</Text>
                      )}
                      <HStack wrap="wrap">
                        <Badge>{selectedProject.framework}</Badge>
                        <Badge>{selectedProject.runtime}</Badge>
                        <Badge colorScheme={
                          selectedProject.status === 'active' ? 'green' :
                          selectedProject.status === 'archived' ? 'gray' : 'yellow'
                        }>
                          {selectedProject.status}
                        </Badge>
                      </HStack>
                      {selectedProject.domains.length > 0 && (
                        <VStack align="start">
                          <Text fontWeight="bold">Domains</Text>
                          {selectedProject.domains.map((domain, index) => (
                            <Text key={index} fontSize="sm" color="blue.600">
                              {domain}
                            </Text>
                          ))}
                        </VStack>
                      )}
                    </VStack>
                  </CardBody>
                </Card>

                {/* Analytics */}
                {analytics && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Text fontWeight="bold">Analytics</Text>
                        <SimpleGrid columns={2} spacing={4} w="full">
                          <Box>
                            <Text fontSize="sm" color="gray.600">Page Views</Text>
                            <Text fontSize="lg" fontWeight="bold">
                              {analytics.metrics.pageViews.toLocaleString()}
                            </Text>
                          </Box>
                          <Box>
                            <Text fontSize="sm" color="gray.600">Unique Visitors</Text>
                            <Text fontSize="lg" fontWeight="bold">
                              {analytics.metrics.uniqueVisitors.toLocaleString()}
                            </Text>
                          </Box>
                          <Box>
                            <Text fontSize="sm" color="gray.600">Avg Session Duration</Text>
                            <Text fontSize="lg" fontWeight="bold">
                              {Math.round(analytics.metrics.avgSessionDuration / 60)}m
                            </Text>
                          </Box>
                          <Box>
                            <Text fontSize="sm" color="gray.600">Bounce Rate</Text>
                            <Text fontSize="lg" fontWeight="bold">
                              {Math.round(analytics.metrics.bounceRate * 100)}%
                            </Text>
                          </Box>
                        </SimpleGrid>
                      </VStack>
                    </CardBody>
                  </Card>
                )}

                {/* Recent Builds */}
                {builds.filter(b => b.projectId === selectedProject.id).length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Text fontWeight="bold">Recent Builds</Text>
                        <TableContainer>
                          <Table size="sm">
                            <Thead>
                              <Tr>
                                <Th>Status</Th>
                                <Th>Commit</Th>
                                <Th>Duration</Th>
                                <Th>Created</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {builds
                                .filter(b => b.projectId === selectedProject.id)
                                .slice(0, 5)
                                .map((build) => (
                                  <Tr key={build.id}>
                                    <Td>
                                      <Badge
                                        colorScheme={
                                          build.status === 'ready' ? 'green' :
                                          build.status === 'error' ? 'red' :
                                          build.status === 'building' ? 'blue' : 'gray'
                                        }
                                      >
                                        {build.status}
                                      </Badge>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm" noOfLines={1}>
                                        {build.commit?.message || 'N/A'}
                                      </Text>
                                    </Td>
                                    <Td>{build.duration ? `${Math.round(build.duration / 1000)}s` : 'N/A'}</Td>
                                    <Td>{new Date(build.createdAt).toLocaleDateString()}</Td>
                                  </Tr>
                                ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button
              colorScheme="blue"
              onClick={() => {
                if (selectedProject?.deployment?.url) {
                  window.open(selectedProject.deployment.url, '_blank');
                }
              }}
            >
              View Live Site
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Card>
  );
};

export default NextjsManager;