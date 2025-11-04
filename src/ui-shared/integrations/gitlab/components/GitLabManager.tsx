/**
 * GitLab Integration Manager
 * Main integration manager component for GitLab
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Progress,
  Divider,
  useColorModeValue,
  Alert,
  AlertIcon,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
  FormControl,
  FormLabel,
  Input,
  Switch,
  Checkbox,
  Select,
  NumberInput,
  NumberInputField,
  Stack,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tag,
  Spinner,
  useDisclosure,
  List,
  ListItem,
  ListIcon,
  Avatar,
  AvatarGroup,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText
} from '@chakra-ui/react';
import {
  GitlabIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  SettingsIcon,
  ExternalLinkIcon,
  AddIcon,
  ViewIcon,
  RepeatIcon,
  BellIcon,
  RocketIcon,
  CodeIcon,
  BugIcon,
  MergeIcon,
  HistoryIcon,
  UserIcon,
  GroupIcon,
  ServerIcon,
  ClockIcon,
  CheckIcon,
  CrossIcon,
  DocumentIcon,
  FolderIcon,
  LinkIcon,
  RefreshIcon
} from '@chakra-ui/icons';
import {
  GitLabProject,
  GitLabConfig,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest,
  GitLabUser
} from '../types';
import { useGitLabProjects, useGitLabPipelines, useGitLabIssues, useGitLabConfig } from '../hooks';
import { GitLabUtils } from '../utils';

interface GitLabManagerProps {
  atomIngestionPipeline?: any;
  onConfigurationChange?: (config: GitLabConfig) => void;
  onIngestionComplete?: (result: any) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

const GitLabManager: React.FC<GitLabManagerProps> = ({
  atomIngestionPipeline,
  onConfigurationChange,
  onIngestionComplete,
  onError,
  userId = 'default-user'
}) => {
  const [config, setConfig] = useState<GitLabConfig>({
    platform: 'gitlab',
    projects: [],
    groups: [],
    include_private_projects: true,
    include_internal_projects: true,
    include_public_projects: false,
    sync_frequency: 'realtime',
    include_pipelines: true,
    include_jobs: true,
    include_issues: true,
    include_merge_requests: true,
    include_releases: true,
    include_webhooks: true,
    max_projects: 50,
    max_pipelines: 100,
    max_jobs: 200,
    max_issues: 100,
    max_merge_requests: 100,
    date_range: {
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      end: new Date()
    },
    webhook_events: [
      'push',
      'merge_request',
      'issue',
      'pipeline',
      'job'
    ],
    enable_notifications: true,
    background_sync: true
  });

  const [isConnected, setIsConnected] = useState(false);
  const [health, setHealth] = useState({ connected: false, error: null });
  const [ingestionStatus, setIngestionStatus] = useState({
    running: false,
    progress: 0,
    message: ''
  });
  const [selectedProject, setSelectedProject] = useState<GitLabProject | null>(null);
  const [selectedTab, setSelectedTab] = useState('overview');
  
  const toast = useToast();
  const { isOpen: isConfigOpen, onOpen: onConfigOpen, onClose: onConfigClose } = useDisclosure();
  const { isOpen: isProjectOpen, onOpen: onProjectOpen, onClose: onProjectClose } = useDisclosure();
  
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Custom hooks for data management
  const {
    projects,
    pipelines,
    issues,
    mergeRequests,
    loading,
    error,
    refreshProjects,
    filterProjects,
    sortProjects,
    projectStats
  } = useGitLabProjects(userId, {
    limit: config.max_projects,
    includePipelines: config.include_pipelines,
    includeIssues: config.include_issues,
    includeMergeRequests: config.include_merge_requests,
    autoRefresh: config.background_sync,
    refreshInterval: config.sync_frequency === 'realtime' ? 30000 : 300000
  });

  const { pipelines: allPipelines } = useGitLabPipelines(userId, {
    limit: config.max_pipelines,
    projectId: selectedProject?.id
  });

  const { issues: allIssues } = useGitLabIssues(userId, {
    limit: config.max_issues,
    projectId: selectedProject?.id
  });

  // Check connection status on mount
  useEffect(() => {
    checkGitLabHealth();
  }, []);

  const checkGitLabHealth = async () => {
    try {
      const response = await fetch('/api/integrations/gitlab/health');
      const data = await response.json();
      
      if (response.ok) {
        setHealth({ connected: data.status === 'healthy', error: null });
        setIsConnected(data.status === 'healthy');
      } else {
        setHealth({ connected: false, error: data.error });
        setIsConnected(false);
      }
    } catch (err) {
      setHealth({ connected: false, error: 'Failed to connect to GitLab' });
      setIsConnected(false);
    }
  };

  const startOAuth = async () => {
    try {
      const response = await fetch('/api/integrations/gitlab/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: ['read_repository', 'api', 'read_user']
        })
      });

      const data = await response.json();
      
      if (response.ok && data.authorization_url) {
        // Open OAuth popup for web platform
        if (typeof window !== 'undefined') {
          const popup = window.open(
            data.authorization_url,
            'gitlab-oauth',
            'width=800,height=600,scrollbars=yes,resizable=yes'
          );
          
          // Poll for OAuth completion
          const checkOAuth = setInterval(async () => {
            if (popup?.closed) {
              clearInterval(checkOAuth);
              await checkGitLabHealth();
              return;
            }
            
            try {
              const statusResponse = await fetch('/api/integrations/gitlab/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
              });
              
              const statusData = await statusResponse.json();
              
              if (statusData.connected) {
                clearInterval(checkOAuth);
                popup?.close();
                await checkGitLabHealth();
                refreshProjects();
                
                toast({
                  title: 'GitLab Connected',
                  description: 'Successfully connected to your GitLab account',
                  status: 'success',
                  duration: 3000
                });
              }
            } catch (error) {
              // Continue checking
            }
          }, 2000);
          
          // Clear interval after 5 minutes
          setTimeout(() => clearInterval(checkOAuth), 300000);
        }
      } else {
        throw new Error(data.error || 'Failed to initiate OAuth');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('OAuth failed');
      onError?.(error);
      
      toast({
        title: 'GitLab OAuth Failed',
        description: error.message,
        status: 'error',
        duration: 5000
      });
    }
  };

  const startIngestion = async () => {
    if (!isConnected || !atomIngestionPipeline) {
      toast({
        title: 'Cannot Start Ingestion',
        description: 'Please connect to GitLab first',
        status: 'warning',
        duration: 3000
      });
      return;
    }

    setIngestionStatus({ running: true, progress: 0, message: 'Starting data ingestion...' });
    
    try {
      // Register integration with ATOM pipeline
      await atomIngestionPipeline.registerIntegration({
        platform: 'gitlab',
        config,
        userId
      });

      setIngestionStatus({ running: true, progress: 25, message: 'Registering integration...' });
      
      // Start data ingestion
      const result = await atomIngestionPipeline.executeSkill('gitlab-start-ingestion', {
        user_id: userId,
        config
      });

      setIngestionStatus({ running: true, progress: 75, message: 'Processing GitLab data...' });
      
      // Update progress and complete
      setIngestionStatus({ running: true, progress: 100, message: 'Ingestion complete!' });
      
      onIngestionComplete?.(result);
      
      toast({
        title: 'GitLab Ingestion Complete',
        description: 'Successfully ingested GitLab data into ATOM',
        status: 'success',
        duration: 3000
      });
      
      setTimeout(() => {
        setIngestionStatus({ running: false, progress: 0, message: '' });
      }, 2000);
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Ingestion failed');
      onError?.(error);
      
      setIngestionStatus({ running: false, progress: 0, message: '' });
      
      toast({
        title: 'Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000
      });
    }
  };

  const updateConfig = (newConfig: Partial<GitLabConfig>) => {
    const updatedConfig = { ...config, ...newConfig };
    setConfig(updatedConfig);
    onConfigurationChange?.(updatedConfig);
  };

  const handleProjectClick = (project: GitLabProject) => {
    setSelectedProject(project);
    onProjectOpen();
  };

  const getProjectVisibility = (visibility: string) => {
    const colors = {
      public: 'green',
      internal: 'yellow',
      private: 'red'
    };
    return colors[visibility as keyof typeof colors] || 'gray';
  };

  const getPipelineStatus = (status: string) => {
    const colors = {
      success: 'green',
      running: 'blue',
      failed: 'red',
      pending: 'yellow',
      created: 'gray',
      skipped: 'gray',
      canceled: 'gray',
      manual: 'purple'
    };
    return colors[status as keyof typeof colors] || 'gray';
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <HStack spacing={4}>
            <Icon as={GitlabIcon} w={10} h={10} color="orange.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl" color="orange.500">
                GitLab Integration
              </Heading>
              <Text color="gray.600" fontSize="md">
                Manage your GitLab repositories and workflows
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={4}>
            <Button
              variant="outline"
              leftIcon={<SettingsIcon />}
              onClick={onConfigOpen}
            >
              Configure
            </Button>
            <Button
              variant="outline"
              leftIcon={<RefreshIcon />}
              onClick={refreshProjects}
              isLoading={loading}
            >
              Refresh
            </Button>
            {!isConnected ? (
              <Button
                colorScheme="orange"
                leftIcon={<GitlabIcon />}
                onClick={startOAuth}
              >
                Connect GitLab
              </Button>
            ) : (
              <Button
                colorScheme="green"
                leftIcon={<RocketIcon />}
                onClick={startIngestion}
                isDisabled={ingestionStatus.running}
              >
                {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
              </Button>
            )}
          </HStack>
        </HStack>

        {/* Connection Status */}
        <Card>
          <CardBody>
            <HStack justify="space-between" align="center">
              <HStack spacing={4}>
                <Icon
                  as={health.connected ? CheckCircleIcon : WarningIcon}
                  w={6} h={6}
                  color={health.connected ? 'green.500' : 'red.500'}
                />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold" fontSize="lg">
                    GitLab Connection
                  </Text>
                  <Text color="gray.600">
                    {health.connected 
                      ? 'Successfully connected to GitLab API' 
                      : health.error || 'Not connected to GitLab'
                    }
                  </Text>
                </VStack>
              </HStack>
              
              <Badge
                colorScheme={health.connected ? 'green' : 'red'}
                variant="solid"
                px={4}
                py={2}
                fontSize="md"
              >
                {health.connected ? 'Connected' : 'Disconnected'}
              </Badge>
            </HStack>
          </CardBody>
        </Card>

        {/* Ingestion Progress */}
        {ingestionStatus.running && (
          <Card>
            <CardBody>
              <VStack spacing={4}>
                <HStack justify="space-between" w="full">
                  <Text fontWeight="bold">Data Ingestion Progress</Text>
                  <Text>{Math.round(ingestionStatus.progress)}%</Text>
                </HStack>
                <Progress
                  value={ingestionStatus.progress}
                  colorScheme="orange"
                  size="lg"
                  w="full"
                />
                <Text color="gray.600" fontSize="sm">
                  {ingestionStatus.message}
                </Text>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Main Content */}
        <Tabs value={selectedTab} onChange={(v) => setSelectedTab(v as string)}>
          <TabList>
            <Tab>Overview</Tab>
            <Tab>Projects</Tab>
            <Tab>Pipelines</Tab>
            <Tab>Issues</Tab>
            <Tab>Merge Requests</Tab>
            <Tab>Activity</Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Projects</StatLabel>
                      <StatNumber color="orange.500">{projectStats.total}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={FolderIcon} color="green.500" />
                          <Text>{projectStats.active} active</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Pipelines</StatLabel>
                      <StatNumber color="blue.500">{allPipelines.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={CheckIcon} color="green.500" />
                          <Text>{allPipelines.filter(p => p.status === 'success').length} successful</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Issues</StatLabel>
                      <StatNumber color="purple.500">{allIssues.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={BugIcon} color="red.500" />
                          <Text>{allIssues.filter(i => i.state === 'opened').length} open</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Merge Requests</StatLabel>
                      <StatNumber color="teal.500">{mergeRequests.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={MergeIcon} color="orange.500" />
                          <Text>{mergeRequests.filter(mr => mr.state === 'opened').length} open</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>
              </SimpleGrid>

              <VStack spacing={4} mt={6}>
                <Text fontWeight="bold" fontSize="lg">Recent Activity</Text>
                <Card>
                  <CardBody>
                    <List spacing={3}>
                      {projects.slice(0, 5).map((project, index) => (
                        <ListItem key={index}>
                          <HStack justify="space-between" w="full">
                            <HStack>
                              <Icon as={CodeIcon} color="orange.500" />
                              <Text fontWeight="medium">{project.name}</Text>
                              <Badge colorScheme={getProjectVisibility(project.visibility)} size="sm">
                                {project.visibility}
                              </Badge>
                            </HStack>
                            <Text fontSize="sm" color="gray.500">
                              Updated {GitLabUtils.getRelativeTime(project.updated_at)}
                            </Text>
                          </HStack>
                        </ListItem>
                      ))}
                    </List>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Projects Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="bold" fontSize="lg">
                    GitLab Projects ({projects.length})
                  </Text>
                  <HStack spacing={2}>
                    <Input
                      placeholder="Search projects..."
                      size="sm"
                      w="200px"
                      onChange={(e) => filterProjects(e.target.value)}
                    />
                    <Select
                      size="sm"
                      w="120px"
                      onChange={(e) => sortProjects(e.target.value, 'desc')}
                    >
                      <option value="updated_at">Last Updated</option>
                      <option value="name">Name</option>
                      <option value="star_count">Stars</option>
                      <option value="forks_count">Forks</option>
                    </Select>
                  </HStack>
                </HStack>

                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {projects.map((project, index) => (
                    <Card
                      key={index}
                      cursor="pointer"
                      onClick={() => handleProjectClick(project)}
                      _hover={{ shadow: 'md' }}
                      bg={bgColor}
                      border="1px"
                      borderColor={borderColor}
                    >
                      <CardBody>
                        <VStack spacing={3} align="start">
                          <HStack justify="space-between" w="full">
                            <HStack>
                              <Icon as={CodeIcon} color="orange.500" />
                              <Text fontWeight="bold" noOfLines={1}>
                                {project.name}
                              </Text>
                            </HStack>
                            <Badge colorScheme={getProjectVisibility(project.visibility)} size="sm">
                              {project.visibility}
                            </Badge>
                          </HStack>
                          
                          {project.description && (
                            <Text color="gray.600" fontSize="sm" noOfLines={2}>
                              {project.description}
                            </Text>
                          )}
                          
                          <HStack justify="space-between" w="full">
                            <HStack spacing={4}>
                              <HStack>
                                <Icon as={StarIcon} w={4} h={4} color="yellow.500" />
                                <Text fontSize="sm">{project.star_count}</Text>
                              </HStack>
                              <HStack>
                                <Icon as={GitlabIcon} w={4} h={4" color="blue.500" />
                                <Text fontSize="sm">{project.forks_count}</Text>
                              </HStack>
                            </HStack>
                            
                            <Badge 
                              colorScheme={project.archived ? 'red' : 'green'} 
                              size="sm"
                            >
                              {project.archived ? 'Archived' : 'Active'}
                            </Badge>
                          </HStack>
                          
                          <Text fontSize="xs" color="gray.500">
                            Updated {GitLabUtils.getRelativeTime(project.updated_at)}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>

                {projects.length === 0 && !loading && (
                  <Card>
                    <CardBody>
                      <VStack spacing={4} py={8}>
                        <Icon as={CodeIcon} w={12} h={12} color="gray.400" />
                        <Text color="gray.600" textAlign="center">
                          No GitLab projects found
                        </Text>
                        <Button
                          colorScheme="orange"
                          onClick={refreshProjects}
                          leftIcon={<RefreshIcon />}
                        >
                          Refresh Projects
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Pipelines Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Recent Pipelines ({allPipelines.length})
                </Text>
                
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Pipeline</Th>
                        <Th>Project</Th>
                        <Th>Ref</Th>
                        <Th>Status</Th>
                        <Th>Duration</Th>
                        <Th>Created</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {allPipelines.slice(0, 20).map((pipeline, index) => (
                        <Tr key={index}>
                          <Td>
                            <HStack>
                              <Icon as={ClockIcon} color="orange.500" />
                              <Text fontWeight="medium">#{pipeline.iid}</Text>
                            </HStack>
                          </Td>
                          <Td>{pipeline.project_id}</Td>
                          <Td>
                            <Badge colorScheme="gray" size="sm">
                              {pipeline.ref}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={getPipelineStatus(pipeline.status)} size="sm">
                              {pipeline.status}
                            </Badge>
                          </Td>
                          <Td>
                            {pipeline.duration 
                              ? `${Math.round(pipeline.duration / 60)}m ${pipeline.duration % 60}s`
                              : '-'
                            }
                          </Td>
                          <Td>{GitLabUtils.getRelativeTime(pipeline.created_at)}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Issues Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Issues ({allIssues.length})
                </Text>
                
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                  {allIssues.slice(0, 20).map((issue, index) => (
                    <Card key={index}>
                      <CardBody>
                        <VStack spacing={3} align="start">
                          <HStack justify="space-between" w="full">
                            <Text fontWeight="bold" noOfLines={1}>
                              #{issue.iid} {issue.title}
                            </Text>
                            <Badge 
                              colorScheme={issue.state === 'opened' ? 'orange' : 'gray'} 
                              size="sm"
                            >
                              {issue.state}
                            </Badge>
                          </HStack>
                          
                          <Text color="gray.600" fontSize="sm" noOfLines={2}>
                            {issue.description}
                          </Text>
                          
                          <HStack justify="space-between" w="full">
                            <HStack>
                              {issue.assignees && issue.assignees.length > 0 && (
                                <AvatarGroup size="xs" max={3}>
                                  {issue.assignees.slice(0, 3).map((assignee, idx) => (
                                    <Avatar
                                      key={idx}
                                      name={assignee.name}
                                      src={assignee.avatar_url}
                                      size="xs"
                                    />
                                  ))}
                                </AvatarGroup>
                              )}
                              {issue.labels && issue.labels.length > 0 && (
                                <HStack spacing={1}>
                                  {issue.labels.slice(0, 3).map((label, idx) => (
                                    <Tag key={idx} size="sm" bgColor={`#${label.color}`}>
                                      {label.title}
                                    </Tag>
                                  ))}
                                </HStack>
                              )}
                            </HStack>
                            <Text fontSize="xs" color="gray.500">
                              Created {GitLabUtils.getRelativeTime(issue.created_at)}
                            </Text>
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Merge Requests Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Merge Requests ({mergeRequests.length})
                </Text>
                
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>MR</Th>
                        <Th>Title</Th>
                        <Th>Author</Th>
                        <Th>Source → Target</Th>
                        <Th>Status</Th>
                        <Th>Created</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {mergeRequests.slice(0, 20).map((mr, index) => (
                        <Tr key={index}>
                          <Td>
                            <HStack>
                              <Icon as={MergeIcon} color="teal.500" />
                              <Text fontWeight="medium">!{mr.iid}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <Text noOfLines={1} maxW="300px">
                              {mr.title}
                            </Text>
                          </Td>
                          <Td>
                            <HStack>
                              <Avatar
                                name={mr.author.name}
                                src={mr.author.avatar_url}
                                size="xs"
                              />
                              <Text fontSize="sm">{mr.author.username}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <HStack>
                              <Text fontSize="sm">{mr.source_branch}</Text>
                              <Text fontSize="xs">→</Text>
                              <Text fontSize="sm">{mr.target_branch}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <Badge 
                              colorScheme={
                                mr.state === 'opened' ? 'blue' :
                                mr.state === 'merged' ? 'green' :
                                mr.state === 'closed' ? 'gray' : 'yellow'
                              } 
                              size="sm"
                            >
                              {mr.state}
                            </Badge>
                          </Td>
                          <Td>{GitLabUtils.getRelativeTime(mr.created_at)}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Activity Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Recent Activity
                </Text>
                
                <Card>
                  <CardBody>
                    <List spacing={4}>
                      {allPipelines.slice(0, 10).map((pipeline, index) => (
                        <ListItem key={index}>
                          <HStack justify="space-between" w="full">
                            <HStack>
                              <Icon 
                                as={ClockIcon} 
                                color={getPipelineStatus(pipeline.status)} 
                              />
                              <VStack align="start" spacing={1}>
                                <Text>Pipeline #{pipeline.iid}</Text>
                                <Text fontSize="sm" color="gray.600">
                                  on branch {pipeline.ref}
                                </Text>
                              </VStack>
                              <Badge colorScheme={getPipelineStatus(pipeline.status)} size="sm">
                                {pipeline.status}
                              </Badge>
                            </HStack>
                            <Text fontSize="sm" color="gray.500">
                              {GitLabUtils.getRelativeTime(pipeline.created_at)}
                            </Text>
                          </HStack>
                        </ListItem>
                      ))}
                    </List>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Configuration Modal */}
        <Modal isOpen={isConfigOpen} onClose={onConfigClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              <HStack>
                <Icon as={GitlabIcon} color="orange.500" />
                <Text>GitLab Configuration</Text>
              </HStack>
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={6} align="stretch">
                <FormControl>
                  <FormLabel>Sync Frequency</FormLabel>
                  <Select
                    value={config.sync_frequency}
                    onChange={(e) => updateConfig({ sync_frequency: e.target.value as any })}
                  >
                    <option value="realtime">Real-time</option>
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                  </Select>
                </FormControl>

                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="include-pipelines" mb="0">
                    Include Pipelines
                  </FormLabel>
                  <Switch
                    id="include-pipelines"
                    isChecked={config.include_pipelines}
                    onChange={(e) => updateConfig({ include_pipelines: e.target.checked })}
                  />
                </FormControl>

                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="include-issues" mb="0">
                    Include Issues
                  </FormLabel>
                  <Switch
                    id="include-issues"
                    isChecked={config.include_issues}
                    onChange={(e) => updateConfig({ include_issues: e.target.checked })}
                  />
                </FormControl>

                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="include-merge-requests" mb="0">
                    Include Merge Requests
                  </FormLabel>
                  <Switch
                    id="include-merge-requests"
                    isChecked={config.include_merge_requests}
                    onChange={(e) => updateConfig({ include_merge_requests: e.target.checked })}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Max Projects</FormLabel>
                  <NumberInput
                    value={config.max_projects}
                    min={1}
                    max={1000}
                    onChange={(value) => updateConfig({ max_projects: parseInt(value) || 50 })}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Webhook Events</FormLabel>
                  <VStack align="start" spacing={2}>
                    {['push', 'merge_request', 'issue', 'pipeline', 'job'].map((event) => (
                      <Checkbox
                        key={event}
                        isChecked={config.webhook_events.includes(event)}
                        onChange={(e) => {
                          const events = e.target.checked
                            ? [...config.webhook_events, event]
                            : config.webhook_events.filter(ev => ev !== event);
                          updateConfig({ webhook_events: events });
                        }}
                      >
                        {event}
                      </Checkbox>
                    ))}
                  </VStack>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={onConfigClose}>
                Cancel
              </Button>
              <Button colorScheme="orange" onClick={onConfigClose}>
                Save Configuration
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Project Details Modal */}
        <Modal isOpen={isProjectOpen} onClose={onProjectClose} size="4xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              <HStack>
                <Icon as={GitlabIcon} color="orange.500" />
                <Text>{selectedProject?.name}</Text>
              </HStack>
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              {selectedProject && (
                <VStack spacing={6} align="stretch">
                  <HStack justify="space-between">
                    <VStack align="start">
                      <Text fontWeight="bold">Visibility</Text>
                      <Badge colorScheme={getProjectVisibility(selectedProject.visibility)}>
                        {selectedProject.visibility}
                      </Badge>
                    </VStack>
                    <VStack align="start">
                      <Text fontWeight="bold">Status</Text>
                      <Badge colorScheme={selectedProject.archived ? 'red' : 'green'}>
                        {selectedProject.archived ? 'Archived' : 'Active'}
                      </Badge>
                    </VStack>
                    <VStack align="start">
                      <Text fontWeight="bold">Stars</Text>
                      <Text>{selectedProject.star_count}</Text>
                    </VStack>
                    <VStack align="start">
                      <Text fontWeight="bold">Forks</Text>
                      <Text>{selectedProject.forks_count}</Text>
                    </VStack>
                  </HStack>
                  
                  {selectedProject.description && (
                    <VStack align="start">
                      <Text fontWeight="bold">Description</Text>
                      <Text>{selectedProject.description}</Text>
                    </VStack>
                  )}
                  
                  <VStack align="start">
                    <Text fontWeight="bold">Repository URL</Text>
                    <Button
                      variant="outline"
                      leftIcon={<ExternalLinkIcon />}
                      onClick={() => window.open(selectedProject.namespace.web_url, '_blank')}
                    >
                      Open Repository
                    </Button>
                  </VStack>
                </VStack>
              )}
            </ModalBody>
            <ModalFooter>
              <Button onClick={onProjectClose}>Close</Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default GitLabManager;