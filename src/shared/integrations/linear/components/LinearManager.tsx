/**
 * Linear Integration Manager Component
 * Real-time issue management and workflow automation
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
  useColorModeValue,
  SimpleGrid,
  Avatar,
  useBreakpointValue,
  Code,
  useClipboard,
  useAccordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Tag,
  TagLeftIcon,
  TagLabel,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Spinner,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useToken,
  Select,
  Textarea,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
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
  CloseIcon,
  DeleteIcon,
  ChatIcon,
  SearchIcon,
  FilterIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  GitBranchIcon,
  TriangleUpIcon,
  TriangleDownIcon,
  WarningTwoIcon,
} from '@chakra-ui/icons';

import { 
  LinearDataSource, 
  LinearConnectionStatus, 
  LinearIngestionProgress,
  LinearIssueData,
  LinearProjectData,
  LinearTeamData,
  LinearUserData,
  LinearStatusData,
  LinearPriorityData
} from '../../shared/types/linear';

interface LinearManagerProps {
  dataSource: LinearDataSource;
  connectionStatus: LinearConnectionStatus;
  ingestionProgress: LinearIngestionProgress;
  onConnect: () => void;
  onDisconnect: () => void;
  onRefresh: () => void;
  onSync: (type: 'issues' | 'projects' | 'teams') => void;
  onUpdateSettings: (settings: any) => void;
}

export const LinearManager: React.FC<LinearManagerProps> = ({
  dataSource,
  connectionStatus,
  ingestionProgress,
  onConnect,
  onDisconnect,
  onRefresh,
  onSync,
  onUpdateSettings,
}) => {
  const [activeTab, setActiveTab] = useState('issues');
  const [issues, setIssues] = useState<LinearIssueData[]>([]);
  const [projects, setProjects] = useState<LinearProjectData[]>([]);
  const [teams, setTeams] = useState<LinearTeamData[]>([]);
  const [users, setUsers] = useState<LinearUserData[]>([]);
  const [statuses, setStatuses] = useState<LinearStatusData[]>([]);
  const [priorities, setPriorities] = useState<LinearPriorityData[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProject, setSelectedProject] = useState('all');
  const [selectedTeam, setSelectedTeam] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedPriority, setSelectedPriority] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<LinearIssueData | null>(null);
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const [colors] = useToken('colors', {
    linear: '#5E6CC2'
  });

  // Load data
  const loadData = useCallback(async () => {
    if (!connectionStatus.isConnected) return;
    
    setLoading(true);
    try {
      // Load issues
      const issuesResponse = await fetch('/api/integrations/linear/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          include_closed: true,
          limit: 100
        })
      });
      
      if (issuesResponse.ok) {
        const issuesData = await issuesResponse.json();
        if (issuesData.ok) {
          setIssues(issuesData.data.issues);
        }
      }

      // Load projects
      const projectsResponse = await fetch('/api/integrations/linear/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          limit: 50
        })
      });
      
      if (projectsResponse.ok) {
        const projectsData = await projectsResponse.json();
        if (projectsData.ok) {
          setProjects(projectsData.data.projects);
        }
      }

      // Load teams
      const teamsResponse = await fetch('/api/integrations/linear/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          limit: 20
        })
      });
      
      if (teamsResponse.ok) {
        const teamsData = await teamsResponse.json();
        if (teamsData.ok) {
          setTeams(teamsData.data.teams);
        }
      }

      // Load users
      const usersResponse = await fetch('/api/integrations/linear/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          limit: 50
        })
      });
      
      if (usersResponse.ok) {
        const usersData = await usersResponse.json();
        if (usersData.ok) {
          setUsers(usersData.data.users);
        }
      }

      // Load statuses
      try {
        const statusesResponse = await fetch('/api/integrations/linear/statuses', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: 'default-user'
          })
        });
        
        if (statusesResponse.ok) {
          const statusesData = await statusesResponse.json();
          if (statusesData.ok) {
            setStatuses(statusesData.data.statuses);
          }
        }
      } catch (error) {
        console.error('Error loading statuses:', error);
      }

      // Load priorities
      try {
        const prioritiesResponse = await fetch('/api/integrations/linear/priorities', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: 'default-user'
          })
        });
        
        if (prioritiesResponse.ok) {
          const prioritiesData = await prioritiesResponse.json();
          if (prioritiesData.ok) {
            setPriorities(prioritiesData.data.priorities);
          }
        }
      } catch (error) {
        console.error('Error loading priorities:', error);
      }

    } catch (error) {
      console.error('Error loading Linear data:', error);
      toast({
        title: 'Error Loading Data',
        description: 'Failed to load Linear data',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [connectionStatus.isConnected, toast]);

  // Initial data load
  useEffect(() => {
    if (connectionStatus.isConnected) {
      loadData();
    }
  }, [connectionStatus.isConnected, loadData]);

  // Filter issues
  const getFilteredIssues = () => {
    let filtered = [...issues];
    
    if (searchQuery.trim()) {
      filtered = filtered.filter(issue =>
        issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        issue.description.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    if (selectedProject !== 'all') {
      filtered = filtered.filter(issue => issue.project.id === selectedProject);
    }
    
    if (selectedStatus !== 'all') {
      filtered = filtered.filter(issue => issue.state.id === selectedStatus);
    }
    
    if (selectedPriority !== 'all') {
      filtered = filtered.filter(issue => issue.priority && issue.priority.id === selectedPriority);
    }
    
    return filtered;
  };

  const filteredIssues = getFilteredIssues();

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'gray';
      default: return 'gray';
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'backlog': return 'gray';
      case 'todo': return 'blue';
      case 'in progress': return 'yellow';
      case 'done': return 'green';
      case 'canceled': return 'red';
      default: return 'gray';
    }
  };

  return (
    <Box w="full">
      {/* Header */}
      <Card mb={6}>
        <CardHeader>
          <HStack justify="space-between">
            <HStack>
              <Icon as={GitBranchIcon} w={6} h={6} color="#5E6CC2" />
              <Heading size="lg">Linear Integration</Heading>
              <Badge colorScheme={connectionStatus.isConnected ? 'green' : 'red'}>
                {connectionStatus.isConnected ? 'Connected' : 'Disconnected'}
              </Badge>
            </HStack>
            
            <HStack>
              <Button
                leftIcon={<RepeatIcon />}
                variant="outline"
                onClick={loadData}
                isLoading={loading}
                isDisabled={!connectionStatus.isConnected}
              >
                Refresh
              </Button>
              
              {!connectionStatus.isConnected ? (
                <Button
                  colorScheme="blue"
                  leftIcon={<AddIcon />}
                  onClick={onConnect}
                >
                  Connect Linear
                </Button>
              ) : (
                <Button
                  colorScheme="red"
                  variant="outline"
                  onClick={onDisconnect}
                >
                  Disconnect
                </Button>
              )}
            </HStack>
          </HStack>
        </CardHeader>

        <CardBody>
          <VStack spacing={4} align="stretch">
            {/* Connection Status */}
            {!connectionStatus.isConnected && (
              <Alert status="warning">
                <AlertIcon />
                <Box>
                  <Text fontWeight="bold">Linear Not Connected</Text>
                  <Text fontSize="sm">Connect to Linear to manage issues, projects, and teams</Text>
                </Box>
              </Alert>
            )}

            {/* Progress */}
            {ingestionProgress.isActive && (
              <Card>
                <CardBody>
                  <VStack spacing={3}>
                    <HStack justify="space-between" w="full">
                      <Text>Syncing with Linear...</Text>
                      <Text>{Math.round(ingestionProgress.progress)}%</Text>
                    </HStack>
                    <Progress
                      value={ingestionProgress.progress}
                      size="md"
                      colorScheme="blue"
                      w="full"
                    />
                    <Text fontSize="sm" color="gray.600">
                      {ingestionProgress.stage}: {ingestionProgress.processedItems} / {ingestionProgress.totalItems} items
                    </Text>
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Statistics */}
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Issues</StatLabel>
                    <StatNumber>{issues.length}</StatNumber>
                    <StatHelpText>All time</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Open Issues</StatLabel>
                    <StatNumber>{issues.filter(i => i.state.type !== 'completed').length}</StatNumber>
                    <StatHelpText>Not resolved</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Projects</StatLabel>
                    <StatNumber>{projects.length}</StatNumber>
                    <StatHelpText>Active projects</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Teams</StatLabel>
                    <StatNumber>{teams.length}</StatNumber>
                    <StatHelpText>Team members</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Content Tabs */}
            <Tabs onChange={setActiveTab} index={['issues', 'projects', 'teams'].indexOf(activeTab)}>
              <TabList>
                <Tab>
                  <HStack>
                    <Text>Issues</Text>
                    <Badge>{issues.length}</Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <Text>Projects</Text>
                    <Badge>{projects.length}</Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <Text>Teams</Text>
                    <Badge>{teams.length}</Badge>
                  </HStack>
                </Tab>
              </TabList>

              <TabPanels>
                {/* Issues Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    {/* Filters */}
                    <HStack spacing={4} wrap="wrap">
                      <Input
                        placeholder="Search issues..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        maxW="300px"
                      />
                      
                      <Select
                        value={selectedProject}
                        onChange={(e) => setSelectedProject(e.target.value)}
                        w="200px"
                      >
                        <option value="all">All Projects</option>
                        {projects.map(project => (
                          <option key={project.id} value={project.id}>
                            {project.name}
                          </option>
                        ))}
                      </Select>
                      
                      <Select
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value)}
                        w="150px"
                      >
                        <option value="all">All Status</option>
                        {statuses.map(status => (
                          <option key={status.id} value={status.id}>
                            {status.name}
                          </option>
                        ))}
                      </Select>
                      
                      <Select
                        value={selectedPriority}
                        onChange={(e) => setSelectedPriority(e.target.value)}
                        w="150px"
                      >
                        <option value="all">All Priority</option>
                        {priorities.map(priority => (
                          <option key={priority.id} value={priority.id}>
                            {priority.label}
                          </option>
                        ))}
                      </Select>
                      
                      <Button
                        leftIcon={<AddIcon />}
                        onClick={() => setShowCreateModal(true)}
                      >
                        Create Issue
                      </Button>
                    </HStack>

                    {/* Issues List */}
                    {loading ? (
                      <VStack py={10}>
                        <Spinner size="xl" color="#5E6CC2" />
                        <Text>Loading issues...</Text>
                      </VStack>
                    ) : filteredIssues.length > 0 ? (
                      <VStack spacing={3} align="stretch">
                        {filteredIssues.map((issue) => (
                          <Card key={issue.id} variant="outline" cursor="pointer">
                            <CardBody>
                              <HStack justify="space-between" align="start">
                                <VStack align="start" spacing={2} flex={1}>
                                  <HStack>
                                    <Text fontWeight="medium">{issue.identifier}</Text>
                                    <Text>{issue.title}</Text>
                                    {issue.state.type === 'completed' && (
                                      <CheckCircleIcon color="green.500" />
                                    )}
                                  </HStack>
                                  
                                  {issue.description && (
                                    <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                      {issue.description}
                                    </Text>
                                  )}

                                  <HStack spacing={4} fontSize="xs" color="gray.500">
                                    <HStack>
                                      <Icon as={GitBranchIcon} w={3} h={3} />
                                      <Text>{issue.project.name}</Text>
                                    </HStack>
                                    
                                    {issue.assignee && (
                                      <HStack>
                                        <Icon as={UserIcon} w={3} h={3} />
                                        <Text>{issue.assignee.name}</Text>
                                      </HStack>
                                    )}
                                    
                                    {issue.priority && (
                                      <Badge size="sm" colorScheme={getPriorityColor(issue.priority.label)}>
                                        {issue.priority.label}
                                      </Badge>
                                    )}
                                  </HStack>
                                </VStack>
                                
                                <Menu>
                                  <MenuButton
                                    as={IconButton}
                                    aria-label="Issue options"
                                    icon={<ChevronDownIcon />}
                                    variant="ghost"
                                    size="sm"
                                  />
                                  <MenuList>
                                    <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                    <MenuItem icon={<EditIcon />}>Edit Issue</MenuItem>
                                    <MenuItem 
                                      icon={<ExternalLinkIcon />}
                                      onClick={() => window.open(issue.url, '_blank')}
                                    >
                                      Open in Linear
                                    </MenuItem>
                                  </MenuList>
                                </Menu>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))}
                      </VStack>
                    ) : (
                      <VStack py={10}>
                        <Text color="gray.500">No issues found</Text>
                      </VStack>
                    )}
                  </VStack>
                </TabPanel>

                {/* Projects Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <HStack justify="space-between">
                      <Text fontWeight="medium">Projects ({projects.length})</Text>
                      <Button
                        leftIcon={<AddIcon />}
                        colorScheme="blue"
                        onClick={() => {/* Create project */}}
                      >
                        Create Project
                      </Button>
                    </HStack>
                    
                    {projects.length > 0 ? (
                      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                        {projects.map((project) => (
                          <Card key={project.id} variant="outline">
                            <CardBody>
                              <VStack align="start" spacing={3}>
                                <Text fontWeight="medium" fontSize="lg">
                                  {project.name}
                                </Text>
                                
                                {project.description && (
                                  <Text fontSize="sm" color="gray.600">
                                    {project.description}
                                  </Text>
                                )}
                                
                                <HStack spacing={4} fontSize="xs" color="gray.500">
                                  <Text>Issues: {project.issueCount || 0}</Text>
                                  {project.progress !== undefined && (
                                    <Text>Progress: {project.progress}%</Text>
                                  )}
                                </HStack>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))}
                      </SimpleGrid>
                    ) : (
                      <VStack py={10}>
                        <Text color="gray.500">No projects found</Text>
                      </VStack>
                    )}
                  </VStack>
                </TabPanel>

                {/* Teams Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <HStack justify="space-between">
                      <Text fontWeight="medium">Teams ({teams.length})</Text>
                      <Button
                        leftIcon={<AddIcon />}
                        colorScheme="blue"
                        onClick={() => {/* Create team */}}
                      >
                        Create Team
                      </Button>
                    </HStack>
                    
                    {teams.length > 0 ? (
                      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                        {teams.map((team) => (
                          <Card key={team.id} variant="outline">
                            <CardBody>
                              <VStack align="start" spacing={3}>
                                <Text fontWeight="medium" fontSize="lg">
                                  {team.name}
                                </Text>
                                
                                {team.description && (
                                  <Text fontSize="sm" color="gray.600">
                                    {team.description}
                                  </Text>
                                )}
                                
                                <HStack spacing={4} fontSize="xs" color="gray.500">
                                  <Text>Members: {team.memberCount || 0}</Text>
                                  <Text>Issues: {team.issueCount || 0}</Text>
                                </HStack>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))}
                      </SimpleGrid>
                    ) : (
                      <VStack py={10}>
                        <Text color="gray.500">No teams found</Text>
                      </VStack>
                    )}
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </VStack>
        </CardBody>
      </Card>
    </Box>
  );
};

export default LinearManager;