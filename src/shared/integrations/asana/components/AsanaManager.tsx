/**
 * Asana Integration Manager Component
 * Real-time task management and collaboration features
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
  CalendarIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
} from '@chakra-ui/icons';

import { 
  AsanaDataSource, 
  AsanaConnectionStatus, 
  AsanaIngestionProgress,
  AsanaTaskData,
  AsanaProjectData,
  AsanaTeamData,
  AsanaSectionData,
  AsanaUserData
} from '../../shared/types/asana';

interface AsanaManagerProps {
  dataSource: AsanaDataSource;
  connectionStatus: AsanaConnectionStatus;
  ingestionProgress: AsanaIngestionProgress;
  onConnect: () => void;
  onDisconnect: () => void;
  onRefresh: () => void;
  onSync: (type: 'tasks' | 'projects' | 'teams' | 'sections') => void;
  onUpdateSettings: (settings: any) => void;
}

export const AsanaManager: React.FC<AsanaManagerProps> = ({
  dataSource,
  connectionStatus,
  ingestionProgress,
  onConnect,
  onDisconnect,
  onRefresh,
  onSync,
  onUpdateSettings,
}) => {
  const [activeTab, setActiveTab] = useState('tasks');
  const [tasks, setTasks] = useState<AsanaTaskData[]>([]);
  const [projects, setProjects] = useState<AsanaProjectData[]>([]);
  const [teams, setTeams] = useState<AsanaTeamData[]>([]);
  const [sections, setSections] = useState<AsanaSectionData[]>([]);
  const [users, setUsers] = useState<AsanaUserData[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProject, setSelectedProject] = useState('all');
  const [selectedTeam, setSelectedTeam] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedPriority, setSelectedPriority] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<AsanaTaskData | null>(null);
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const [colors] = useToken('colors', {
    asana: '#27334D'
  });

  // Load data
  const loadData = useCallback(async () => {
    if (!connectionStatus.isConnected) return;
    
    setLoading(true);
    try {
      // Load tasks
      const tasksResponse = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          include_completed: true,
          limit: 100
        })
      });
      
      if (tasksResponse.ok) {
        const tasksData = await tasksResponse.json();
        if (tasksData.ok) {
          setTasks(tasksData.data.tasks);
        }
      }

      // Load projects
      const projectsResponse = await fetch('/api/integrations/asana/projects', {
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
      const teamsResponse = await fetch('/api/integrations/asana/teams', {
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
      const usersResponse = await fetch('/api/integrations/asana/users', {
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

    } catch (error) {
      console.error('Error loading Asana data:', error);
      toast({
        title: 'Error Loading Data',
        description: 'Failed to load Asana data',
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

  // Filter tasks
  const getFilteredTasks = () => {
    let filtered = [...tasks];
    
    if (searchQuery.trim()) {
      filtered = filtered.filter(task =>
        task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (task.notes && task.notes.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    }
    
    if (selectedProject !== 'all') {
      filtered = filtered.filter(task => 
        task.projects.some(project => project.id === selectedProject)
      );
    }
    
    if (selectedStatus !== 'all') {
      filtered = filtered.filter(task => {
        if (selectedStatus === 'completed') return task.completed;
        if (selectedStatus === 'active') return !task.completed;
        return true;
      });
    }
    
    if (selectedPriority !== 'all') {
      filtered = filtered.filter(task => task.priority === selectedPriority);
    }
    
    return filtered;
  };

  const filteredTasks = getFilteredTasks();

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'red';
      case 'medium': return 'yellow';
      case 'low': return 'gray';
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
              <Icon as={ViewListIcon} w={6} h={6} color="#27334D" />
              <Heading size="lg">Asana Integration</Heading>
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
                  Connect Asana
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
                  <Text fontWeight="bold">Asana Not Connected</Text>
                  <Text fontSize="sm">Connect to Asana to manage tasks, projects, and teams</Text>
                </Box>
              </Alert>
            )}

            {/* Progress */}
            {ingestionProgress.isActive && (
              <Card>
                <CardBody>
                  <VStack spacing={3}>
                    <HStack justify="space-between" w="full">
                      <Text>Syncing with Asana...</Text>
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

            {/* Content Tabs */}
            <Tabs onChange={setActiveTab} index={['tasks', 'projects', 'teams'].indexOf(activeTab)}>
              <TabList>
                <Tab>
                  <HStack>
                    <Text>Tasks</Text>
                    <Badge>{tasks.length}</Badge>
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
                {/* Tasks Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    {/* Filters */}
                    <HStack spacing={4} wrap="wrap">
                      <Input
                        placeholder="Search tasks..."
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
                        <option value="active">Active</option>
                        <option value="completed">Completed</option>
                      </Select>
                      
                      <Select
                        value={selectedPriority}
                        onChange={(e) => setSelectedPriority(e.target.value)}
                        w="150px"
                      >
                        <option value="all">All Priority</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </Select>
                      
                      <Button
                        leftIcon={<AddIcon />}
                        onClick={() => setShowCreateModal(true)}
                      >
                        Create Task
                      </Button>
                    </HStack>

                    {/* Tasks List */}
                    {loading ? (
                      <VStack py={10}>
                        <Spinner size="xl" color="#27334D" />
                        <Text>Loading tasks...</Text>
                      </VStack>
                    ) : filteredTasks.length > 0 ? (
                      <VStack spacing={3} align="stretch">
                        {filteredTasks.map((task) => (
                          <Card key={task.id} variant="outline" cursor="pointer">
                            <CardBody>
                              <HStack justify="space-between" align="start">
                                <VStack align="start" spacing={2} flex={1}>
                                  <HStack>
                                    <Text fontWeight="medium">{task.name}</Text>
                                    {task.completed && (
                                      <CheckCircleIcon color="green.500" />
                                    )}
                                  </HStack>
                                  
                                  {task.notes && (
                                    <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                      {task.notes}
                                    </Text>
                                  )}
                                  
                                  <HStack spacing={4} fontSize="xs" color="gray.500">
                                    {task.assignee && (
                                      <HStack>
                                        <UserIcon w={3} h={3} />
                                        <Text>{task.assignee.name}</Text>
                                      </HStack>
                                    )}
                                    
                                    {task.due_on && (
                                      <HStack>
                                        <CalendarIcon w={3} h={3} />
                                        <Text>{new Date(task.due_on).toLocaleDateString()}</Text>
                                      </HStack>
                                    )}
                                    
                                    {task.priority && (
                                      <Badge size="sm" colorScheme={getPriorityColor(task.priority)}>
                                        {task.priority}
                                      </Badge>
                                    )}
                                  </HStack>
                                </VStack>
                                
                                <Menu>
                                  <MenuButton
                                    as={IconButton}
                                    icon={<ChevronDownIcon />}
                                    variant="ghost"
                                    size="sm"
                                  />
                                  <MenuList>
                                    <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                    <MenuItem icon={<EditIcon />}>Edit Task</MenuItem>
                                    {task.url && (
                                      <MenuItem 
                                        icon={<ExternalLinkIcon />}
                                        onClick={() => window.open(task.url, '_blank')}
                                      >
                                        Open in Asana
                                      </MenuItem>
                                    )}
                                  </MenuList>
                                </Menu>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))}
                      </VStack>
                    ) : (
                      <VStack py={10}>
                        <Text color="gray.500">No tasks found</Text>
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
                                <HStack justify="space-between" w="full">
                                  <Text fontWeight="medium">{project.name}</Text>
                                  <Box w={4} h={4} bg={project.color} borderRadius="sm" />
                                </HStack>
                                
                                {project.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {project.description}
                                  </Text>
                                )}
                                
                                <HStack spacing={4} fontSize="xs" color="gray.500">
                                  <Text>Members: {project.members_count}</Text>
                                  <Text>Tasks: {project.tasks_count}</Text>
                                  {project.progress !== undefined && (
                                    <Text>Progress: {project.progress}%</Text>
                                  )}
                                </HStack>
                                
                                {project.progress !== undefined && (
                                  <Progress
                                    value={project.progress}
                                    size="sm"
                                    colorScheme="blue"
                                    w="full"
                                  />
                                )}
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
                                  <Text>Members: {team.members_count}</Text>
                                  <Text>Projects: {team.projects_count}</Text>
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

export default AsanaManager;