/**
 * ATOM Agent Enhanced Task UI with Trello & Asana Integration
 * Seamless task management integrated with main chat interface
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
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
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
  Select,
  Checkbox,
  Textarea,
  IconButton,
  Badge,
  useAccordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Switch,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverHeader,
  PopoverBody,
  PopoverArrow,
  PopoverCloseButton,
  Spinner,
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
  ChatIcon,
  TaskIcon,
  CalendarIcon,
  ChevronRightIcon,
  PlayIcon,
  SearchIcon,
  FilterIcon,
  CloseIcon,
  PlusIcon,
  DeleteIcon,
  EditIcon as EditTaskIcon,
  BellIcon,
  BellSlashIcon,
  ClockIcon,
  WarningTwoIcon,
  CheckCircleIcon as TaskCompleteIcon,
} from '@chakra-ui/icons';

// Import integration components
import { TrelloManager } from '../integrations/trello/components/TrelloManager';
import { AsanaManager } from '../integrations/asana/components/AsanaManager';
import { TrelloSkills } from '../integrations/trello/components/TrelloSkills';
import { AsanaSkills } from '../integrations/asana/components/AsanaSkills';

// Import ATOM components
import { ATOMDataSource, AtomIngestionPipeline, IngestionStatus, DataSourceHealth } from '@shared/ui-shared/data-sources/types';

interface ATOMAgentTaskUIProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onTaskComplete?: (task: any) => void;
  onTaskUpdate?: (task: any) => void;
  onIntegrationAction?: (action: string, data: any) => void;
  userId?: string;
  isConnected?: boolean;
  chatMessages?: any[];
  onSendMessage?: (message: string) => void;
  activeIntegrations?: string[];
  integrationHealth?: Record<string, any>;
}

interface Task {
  id: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'completed' | 'blocked';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assignee?: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  };
  project?: {
    id: string;
    name: string;
    color?: string;
  };
  dueDate?: string;
  createdAt: string;
  updatedAt: string;
  source: 'trello' | 'asana' | 'atom';
  sourceId?: string;
  url?: string;
  tags?: string[];
  customFields?: Record<string, any>;
  comments?: number;
  attachments?: number;
  completedAt?: string;
}

interface IntegrationTask {
  trello: Task[];
  asana: Task[];
  atom: Task[];
}

export const ATOMAgentTaskUI: React.FC<ATOMAgentTaskUIProps> = ({
  atomIngestionPipeline,
  onTaskComplete,
  onTaskUpdate,
  onIntegrationAction,
  userId = 'default-user',
  isConnected = true,
  chatMessages = [],
  onSendMessage,
  activeIntegrations = [],
  integrationHealth = {},
}) => {
  const [tasks, setTasks] = useState<IntegrationTask>({
    trello: [],
    asana: [],
    atom: []
  });
  const [loading, setLoading] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState<string>('all');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showTaskDetails, setShowTaskDetails] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showCreateTask, setShowCreateTask] = useState(false);
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    priority: 'medium',
    dueDate: '',
    assignee: '',
    project: '',
    source: 'atom'
  });
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const [colors] = useToken('colors', {
    trello: '#0079BF',
    asana: '#27334D',
    atom: '#0084FF'
  });

  // Load tasks from integrations
  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const loadedTasks: IntegrationTask = {
        trello: [],
        asana: [],
        atom: []
      };

      // Load Trello tasks if connected
      if (activeIntegrations.includes('trello') && integrationHealth?.trello?.connected) {
        try {
          const trelloResponse = await fetch('/api/integrations/trello/cards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, limit: 50 })
          });
          const trelloData = await trelloResponse.json();
          if (trelloData.ok) {
            loadedTasks.trello = trelloData.data.cards.map((card: any) => ({
              id: card.card_id,
              title: card.name,
              description: card.desc,
              status: card.closed ? 'completed' : (card.due ? 'in_progress' : 'todo'),
              priority: card.labels?.some((label: any) => label.color === 'red') ? 'urgent' :
                       card.labels?.some((label: any) => label.color === 'orange') ? 'high' :
                       card.labels?.some((label: any) => label.color === 'yellow') ? 'medium' : 'low',
              assignee: card.members?.[0],
              project: card.board ? {
                id: card.board.board_id,
                name: card.board.name,
                color: card.board.prefs?.backgroundColor || '#0079BF'
              } : undefined,
              dueDate: card.due,
              createdAt: card.created_at,
              updatedAt: card.updated_at,
              source: 'trello',
              sourceId: card.card_id,
              url: card.url,
              tags: card.labels?.map((label: any) => label.name) || [],
              comments: card.comment_count || 0,
              attachments: card.attachments_count || 0
            }));
          }
        } catch (error) {
          console.error('Error loading Trello tasks:', error);
        }
      }

      // Load Asana tasks if connected
      if (activeIntegrations.includes('asana') && integrationHealth?.asana?.connected) {
        try {
          const asanaResponse = await fetch('/api/integrations/asana/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              user_id: userId, 
              include_completed: true, 
              limit: 50 
            })
          });
          const asanaData = await asanaResponse.json();
          if (asanaData.ok) {
            loadedTasks.asana = asanaData.data.tasks.map((task: any) => ({
              id: task.task_id,
              title: task.name,
              description: task.notes,
              status: task.completed ? 'completed' : 
                      task.due_on && new Date(task.due_on) < new Date() ? 'blocked' : 'todo',
              priority: task.priority || 'medium',
              assignee: task.assignee,
              project: task.projects?.[0],
              dueDate: task.due_on,
              createdAt: task.created_at,
              updatedAt: task.modified_at,
              source: 'asana',
              sourceId: task.task_id,
              url: task.url,
              tags: task.tags?.map((tag: any) => tag.name) || [],
              comments: 0, // Would need additional API call
              attachments: 0 // Would need additional API call
            }));
          }
        } catch (error) {
          console.error('Error loading Asana tasks:', error);
        }
      }

      // Load ATOM internal tasks
      try {
        const atomResponse = await fetch('/api/agent/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });
        const atomData = await atomResponse.json();
        if (atomData.ok) {
          loadedTasks.atom = atomData.data.tasks.map((task: any) => ({
            id: task.id,
            title: task.title,
            description: task.description,
            status: task.status,
            priority: task.priority,
            assignee: task.assignee,
            project: task.project,
            dueDate: task.dueDate,
            createdAt: task.createdAt,
            updatedAt: task.updatedAt,
            source: 'atom',
            sourceId: task.id,
            url: task.url,
            tags: task.tags || [],
            comments: task.comments || 0,
            attachments: task.attachments || 0
          }));
        }
      } catch (error) {
        console.error('Error loading ATOM tasks:', error);
      }

      setTasks(loadedTasks);
    } catch (error) {
      console.error('Error loading tasks:', error);
      toast({
        title: 'Error Loading Tasks',
        description: 'Failed to load tasks from integrations',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [activeIntegrations, integrationHealth, userId, toast]);

  // Initialize tasks on mount
  useEffect(() => {
    if (activeIntegrations.length > 0) {
      loadTasks();
    }
  }, [loadTasks, activeIntegrations]);

  // Filter and sort tasks
  const getFilteredTasks = useCallback(() => {
    let allTasks: Task[] = [];
    
    if (selectedIntegration === 'all') {
      allTasks = [...tasks.trello, ...tasks.asana, ...tasks.atom];
    } else {
      allTasks = tasks[selectedIntegration as keyof IntegrationTask] || [];
    }

    // Apply search filter
    if (searchQuery.trim()) {
      allTasks = allTasks.filter(task =>
        task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    }

    // Apply status filter
    if (filterStatus !== 'all') {
      allTasks = allTasks.filter(task => task.status === filterStatus);
    }

    // Apply priority filter
    if (filterPriority !== 'all') {
      allTasks = allTasks.filter(task => task.priority === filterPriority);
    }

    // Apply sorting
    allTasks.sort((a, b) => {
      let aValue = a[sortBy as keyof Task] || '';
      let bValue = b[sortBy as keyof Task] || '';
      
      if (sortBy === 'priority') {
        const priorityOrder = { low: 1, medium: 2, high: 3, urgent: 4 };
        aValue = priorityOrder[a.priority];
        bValue = priorityOrder[b.priority];
      }
      
      if (sortBy === 'dueDate') {
        aValue = a.dueDate ? new Date(a.dueDate).getTime() : 0;
        bValue = b.dueDate ? new Date(b.dueDate).getTime() : 0;
      }

      if (sortBy === 'createdAt' || sortBy === 'updatedAt') {
        aValue = new Date(a[sortBy]).getTime();
        bValue = new Date(b[sortBy]).getTime();
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    return allTasks;
  }, [tasks, selectedIntegration, searchQuery, filterStatus, filterPriority, sortBy, sortOrder]);

  // Update task status
  const updateTaskStatus = useCallback(async (task: Task, newStatus: Task['status']) => {
    try {
      let response;
      
      if (task.source === 'trello') {
        response = await fetch('/api/integrations/trello/cards/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            card_id: task.sourceId,
            updates: { closed: newStatus === 'completed' }
          })
        });
      } else if (task.source === 'asana') {
        response = await fetch('/api/integrations/asana/tasks/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            task_id: task.sourceId,
            updates: { completed: newStatus === 'completed' }
          })
        });
      } else {
        response = await fetch('/api/agent/tasks/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            task_id: task.id,
            status: newStatus
          })
        });
      }

      const data = await response.json();
      if (data.ok) {
        // Update local state
        setTasks(prev => ({
          ...prev,
          [task.source]: prev[task.source].map(t =>
            t.id === task.id ? { ...t, status: newStatus, updatedAt: new Date().toISOString() } : t
          )
        }));

        // Notify parent components
        if (onTaskUpdate) {
          onTaskUpdate({ ...task, status: newStatus });
        }

        toast({
          title: 'Task Updated',
          description: `Task "${task.title}" marked as ${newStatus}`,
          status: 'success',
          duration: 3000,
        });

        // Send chat message
        if (onSendMessage) {
          onSendMessage(`Task "${task.title}" has been marked as ${newStatus}.`);
        }
      } else {
        throw new Error(data.error || 'Failed to update task');
      }
    } catch (error) {
      console.error('Error updating task:', error);
      toast({
        title: 'Update Failed',
        description: 'Failed to update task status',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, onTaskUpdate, onSendMessage, toast]);

  // Create new task
  const createTask = useCallback(async () => {
    if (!newTask.title.trim()) {
      toast({
        title: 'Title Required',
        description: 'Task title is required',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    try {
      const taskData = {
        title: newTask.title,
        description: newTask.description,
        priority: newTask.priority,
        due_date: newTask.dueDate,
        assignee: newTask.assignee,
        project: newTask.project,
        user_id: userId
      };

      let response;
      
      if (newTask.source === 'trello') {
        response = await fetch('/api/integrations/trello/cards', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });
      } else if (newTask.source === 'asana') {
        response = await fetch('/api/integrations/asana/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            operation: 'create',
            data: {
              name: newTask.title,
              description: newTask.description,
              priority: newTask.priority,
              due_date: newTask.dueDate,
              assignee: newTask.assignee,
              projects: newTask.project ? [{ gid: newTask.project }] : []
            }
          })
        });
      } else {
        response = await fetch('/api/agent/tasks/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });
      }

      const data = await response.json();
      if (data.ok) {
        toast({
          title: 'Task Created',
          description: `Task "${newTask.title}" created successfully`,
          status: 'success',
          duration: 3000,
        });

        // Send chat message
        if (onSendMessage) {
          onSendMessage(`Task "${newTask.title}" has been created in ${newTask.source}.`);
        }

        // Reset form and reload tasks
        setNewTask({
          title: '',
          description: '',
          priority: 'medium',
          dueDate: '',
          assignee: '',
          project: '',
          source: 'atom'
        });
        setShowCreateTask(false);
        loadTasks();
      } else {
        throw new Error(data.error || 'Failed to create task');
      }
    } catch (error) {
      console.error('Error creating task:', error);
      toast({
        title: 'Creation Failed',
        description: 'Failed to create task',
        status: 'error',
        duration: 5000,
      });
    }
  }, [newTask, userId, onSendMessage, toast, loadTasks]);

  // Get priority color
  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'urgent': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'gray';
      default: return 'gray';
    }
  };

  // Get status icon
  const getStatusIcon = (status: Task['status']) => {
    switch (status) {
      case 'todo': return <TimeIcon />;
      case 'in_progress': return <PlayIcon />;
      case 'completed': return <CheckCircleIcon />;
      case 'blocked': return <WarningIcon />;
      default: return <TimeIcon />;
    }
  };

  // Get status color
  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'todo': return 'gray';
      case 'in_progress': return 'blue';
      case 'completed': return 'green';
      case 'blocked': return 'red';
      default: return 'gray';
    }
  };

  const filteredTasks = getFilteredTasks();

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between" align="center">
          <HStack>
            <Icon as={TaskIcon} w={6} h={6} color="blue.500" />
            <Heading size="lg">ATOM Agent Task Management</Heading>
            <Badge colorScheme="blue">
              {filteredTasks.length} Tasks
            </Badge>
          </HStack>
          
          <HStack>
            {/* Search */}
            <Popover placement="bottom-end">
              <PopoverTrigger>
                <Button
                  leftIcon={<SearchIcon />}
                  variant="outline"
                  size="sm"
                >
                  Search
                </Button>
              </PopoverTrigger>
              <PopoverContent>
                <PopoverArrow />
                <PopoverHeader>Search Tasks</PopoverHeader>
                <PopoverCloseButton />
                <PopoverBody>
                  <Input
                    placeholder="Search by title, description, or tags..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    mb={3}
                  />
                  
                  <VStack align="start" spacing={2}>
                    <Text fontWeight="bold" fontSize="sm">Status</Text>
                    <Select
                      size="sm"
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                    >
                      <option value="all">All Status</option>
                      <option value="todo">To Do</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="blocked">Blocked</option>
                    </Select>
                    
                    <Text fontWeight="bold" fontSize="sm">Priority</Text>
                    <Select
                      size="sm"
                      value={filterPriority}
                      onChange={(e) => setFilterPriority(e.target.value)}
                    >
                      <option value="all">All Priority</option>
                      <option value="urgent">Urgent</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </Select>
                    
                    <Text fontWeight="bold" fontSize="sm">Sort By</Text>
                    <Select
                      size="sm"
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                    >
                      <option value="createdAt">Created Date</option>
                      <option value="updatedAt">Updated Date</option>
                      <option value="dueDate">Due Date</option>
                      <option value="priority">Priority</option>
                      <option value="title">Title</option>
                    </Select>
                    
                    <Text fontWeight="bold" fontSize="sm">Order</Text>
                    <Select
                      size="sm"
                      value={sortOrder}
                      onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
                    >
                      <option value="desc">Newest First</option>
                      <option value="asc">Oldest First</option>
                    </Select>
                  </VStack>
                </PopoverBody>
              </PopoverContent>
            </Popover>

            {/* Integration Filter */}
            <Select
              size="sm"
              value={selectedIntegration}
              onChange={(e) => setSelectedIntegration(e.target.value)}
              w="150px"
            >
              <option value="all">All Sources</option>
              {activeIntegrations.includes('trello') && (
                <option value="trello">Trello</option>
              )}
              {activeIntegrations.includes('asana') && (
                <option value="asana">Asana</option>
              )}
              <option value="atom">ATOM</option>
            </Select>

            {/* Refresh */}
            <IconButton
              aria-label="Refresh tasks"
              icon={<RepeatIcon />}
              variant="outline"
              size="sm"
              onClick={loadTasks}
              isLoading={loading}
            />

            {/* Create Task */}
            <Button
              leftIcon={<AddIcon />}
              colorScheme="blue"
              size="sm"
              onClick={() => setShowCreateTask(true)}
            >
              Create Task
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={4} align="stretch">
          {/* Integration Status */}
          <HStack spacing={4} wrap="wrap">
            {activeIntegrations.map(integration => (
              <HStack key={integration}>
                <Icon 
                  as={
                    integration === 'trello' ? ExternalLinkIcon :
                    integration === 'asana' ? TaskIcon :
                    SettingsIcon
                  } 
                  w={4} h={4} 
                  color={colors[integration as keyof typeof colors] || 'gray.500'}
                />
                <Text fontSize="sm" fontWeight="medium">
                  {integration.charAt(0).toUpperCase() + integration.slice(1)}
                </Text>
                <Badge 
                  size="sm" 
                  colorScheme={
                    integrationHealth[integration]?.connected ? 'green' : 'red'
                  }
                >
                  {integrationHealth[integration]?.connected ? 'Connected' : 'Disconnected'}
                </Badge>
              </HStack>
            ))}
          </HStack>

          {/* Tasks Grid */}
          {loading ? (
            <VStack spacing={4} py={10}>
              <Spinner size="xl" color="blue.500" />
              <Text>Loading tasks...</Text>
            </VStack>
          ) : filteredTasks.length > 0 ? (
            <SimpleGrid columns={responsiveGridCols} spacing={4}>
              {filteredTasks.map((task) => (
                <Card 
                  key={task.id} 
                  variant="outline" 
                  size="sm"
                  borderWidth={task.status === 'completed' ? '2px' : '1px'}
                  borderColor={task.status === 'completed' ? 'green.200' : borderColor}
                  cursor="pointer"
                  onClick={() => {
                    setSelectedTask(task);
                    setShowTaskDetails(true);
                  }}
                  _hover={{
                    shadow: 'md',
                    transform: 'translateY(-2px)'
                  }}
                  transition="all 0.2s"
                >
                  <CardBody p={4}>
                    <VStack align="start" spacing={3}>
                      {/* Header */}
                      <HStack justify="space-between" w="full">
                        <HStack>
                          <Icon 
                            as={getStatusIcon(task.status)} 
                            w={4} h={4} 
                            color={getStatusColor(task.status)}
                          />
                          <Text 
                            fontWeight="medium" 
                            fontSize="sm"
                            noOfLines={2}
                            flex={1}
                          >
                            {task.title}
                          </Text>
                        </HStack>
                        <HStack>
                          <Badge size="sm" colorScheme={colors[task.source as keyof typeof colors] as string}>
                            {task.source.toUpperCase()}
                          </Badge>
                          <Badge size="sm" colorScheme={getPriorityColor(task.priority)}>
                            {task.priority.toUpperCase()}
                          </Badge>
                        </HStack>
                      </HStack>

                      {/* Description */}
                      {task.description && (
                        <Text fontSize="xs" color="gray.600" noOfLines={2}>
                          {task.description}
                        </Text>
                      )}

                      {/* Meta Information */}
                      <VStack align="start" spacing={1}>
                        {task.project && (
                          <HStack>
                            <Icon as={ViewIcon} w={3} h={3} color="gray.500" />
                            <Text fontSize="xs" color="gray.600">
                              {task.project.name}
                            </Text>
                          </HStack>
                        )}

                        {task.assignee && (
                          <HStack>
                            <Icon as={UserIcon} w={3} h={3} color="gray.500" />
                            <Text fontSize="xs" color="gray.600">
                              {task.assignee.name}
                            </Text>
                          </HStack>
                        )}

                        {task.dueDate && (
                          <HStack>
                            <Icon as={CalendarIcon} w={3} h={3} color="gray.500" />
                            <Text 
                              fontSize="xs" 
                              color={
                                new Date(task.dueDate) < new Date() && task.status !== 'completed' 
                                  ? 'red.600' 
                                  : 'gray.600'
                              }
                            >
                              {new Date(task.dueDate).toLocaleDateString()}
                            </Text>
                          </HStack>
                        )}

                        {/* Tags */}
                        {task.tags && task.tags.length > 0 && (
                          <HStack wrap="wrap">
                            {task.tags.slice(0, 3).map((tag) => (
                              <Tag size="xs" key={tag} variant="outline">
                                {tag}
                              </Tag>
                            ))}
                            {task.tags.length > 3 && (
                              <Tag size="xs" variant="solid">
                                +{task.tags.length - 3}
                              </Tag>
                            )}
                          </HStack>
                        )}

                        {/* Activity indicators */}
                        <HStack justify="space-between" w="full">
                          <HStack spacing={2}>
                            {task.comments > 0 && (
                              <HStack>
                                <ChatIcon w={3} h={3} color="gray.500" />
                                <Text fontSize="xs" color="gray.600">
                                  {task.comments}
                                </Text>
                              </HStack>
                            )}
                            {task.attachments > 0 && (
                              <HStack>
                                <ViewListIcon w={3} h={3} color="gray.500" />
                                <Text fontSize="xs" color="gray.600">
                                  {task.attachments}
                                </Text>
                              </HStack>
                            )}
                          </HStack>
                          <Text fontSize="xs" color="gray.500">
                            {new Date(task.updatedAt).toLocaleDateString()}
                          </Text>
                        </HStack>
                      </VStack>

                      {/* Quick Actions */}
                      <HStack justify="space-between" w="full">
                        {task.status !== 'completed' && (
                          <Button
                            size="xs"
                            colorScheme="green"
                            leftIcon={<CheckCircleIcon />}
                            onClick={(e) => {
                              e.stopPropagation();
                              updateTaskStatus(task, 'completed');
                            }}
                          >
                            Complete
                          </Button>
                        )}
                        
                        <Menu>
                          <MenuButton
                            as={IconButton}
                            aria-label="Task options"
                            icon={<EditIcon />}
                            variant="ghost"
                            size="xs"
                            onClick={(e) => e.stopPropagation()}
                          />
                          <MenuList>
                            <MenuItem 
                              icon={<EditIcon />}
                              onClick={(e) => e.stopPropagation()}
                            >
                              Edit
                            </MenuItem>
                            {task.url && (
                              <MenuItem 
                                icon={<ExternalLinkIcon />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(task.url, '_blank');
                                }}
                              >
                                Open in {task.source}
                              </MenuItem>
                            )}
                            {task.status !== 'in_progress' && (
                              <MenuItem 
                                icon={<PlayIcon />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  updateTaskStatus(task, 'in_progress');
                                }}
                              >
                                Start Progress
                              </MenuItem>
                            )}
                            {task.status === 'completed' && (
                              <MenuItem 
                                icon={<TimeIcon />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  updateTaskStatus(task, 'todo');
                                }}
                              >
                                Reopen
                              </MenuItem>
                            )}
                          </MenuList>
                        </Menu>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </SimpleGrid>
          ) : (
            <VStack spacing={4} py={10}>
              <Icon as={TaskIcon} w={12} h={12} color="gray.400" />
              <Text fontSize="lg" fontWeight="medium" color="gray.600">
                No tasks found
              </Text>
              <Text fontSize="sm" color="gray.500" textAlign="center">
                {searchQuery.trim() 
                  ? 'No tasks match your search criteria. Try adjusting your filters.'
                  : 'No tasks available. Create your first task to get started.'
                }
              </Text>
              {!searchQuery.trim() && (
                <Button
                  leftIcon={<AddIcon />}
                  colorScheme="blue"
                  onClick={() => setShowCreateTask(true)}
                >
                  Create First Task
                </Button>
              )}
            </VStack>
          )}

          {/* Task Statistics */}
          {filteredTasks.length > 0 && (
            <Card bg={bgColor} border="1px" borderColor={borderColor}>
              <CardBody>
                <HStack justify="space-between" wrap="wrap" spacing={4}>
                  <VStack align="start" spacing={1}>
                    <Text fontSize="xs" color="gray.600">Total Tasks</Text>
                    <Text fontSize="2xl" fontWeight="bold">{filteredTasks.length}</Text>
                  </VStack>
                  
                  <VStack align="start" spacing={1}>
                    <Text fontSize="xs" color="gray.600">Completed</Text>
                    <Text fontSize="2xl" fontWeight="bold" color="green.600">
                      {filteredTasks.filter(t => t.status === 'completed').length}
                    </Text>
                  </VStack>
                  
                  <VStack align="start" spacing={1}>
                    <Text fontSize="xs" color="gray.600">In Progress</Text>
                    <Text fontSize="2xl" fontWeight="bold" color="blue.600">
                      {filteredTasks.filter(t => t.status === 'in_progress').length}
                    </Text>
                  </VStack>
                  
                  <VStack align="start" spacing={1}>
                    <Text fontSize="xs" color="gray.600">Overdue</Text>
                    <Text fontSize="2xl" fontWeight="bold" color="red.600">
                      {filteredTasks.filter(t => 
                        t.dueDate && 
                        new Date(t.dueDate) < new Date() && 
                        t.status !== 'completed'
                      ).length}
                    </Text>
                  </VStack>
                </HStack>
              </CardBody>
            </Card>
          )}
        </VStack>
      </CardBody>

      {/* Task Details Modal */}
      <Modal 
        isOpen={showTaskDetails} 
        onClose={() => setShowTaskDetails(false)}
        size="lg"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <Icon as={getStatusIcon(selectedTask?.status || 'todo')} w={5} h={5} />
              <Text>{selectedTask?.title}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedTask && (
              <VStack spacing={4} align="stretch">
                {/* Status and Priority */}
                <HStack justify="space-between">
                  <HStack>
                    <Text fontWeight="medium">Status:</Text>
                    <Badge colorScheme={getStatusColor(selectedTask.status)}>
                      {selectedTask.status.replace('_', ' ').toUpperCase()}
                    </Badge>
                  </HStack>
                  <HStack>
                    <Text fontWeight="medium">Priority:</Text>
                    <Badge colorScheme={getPriorityColor(selectedTask.priority)}>
                      {selectedTask.priority.toUpperCase()}
                    </Badge>
                  </HStack>
                </HStack>

                {/* Description */}
                {selectedTask.description && (
                  <Box>
                    <Text fontWeight="medium" mb={2}>Description:</Text>
                    <Text fontSize="sm" color="gray.600" whiteSpace="pre-wrap">
                      {selectedTask.description}
                    </Text>
                  </Box>
                )}

                {/* Project */}
                {selectedTask.project && (
                  <HStack>
                    <Text fontWeight="medium" w="100px">Project:</Text>
                    <HStack>
                      <Box 
                        w={3} 
                        h={3} 
                        borderRadius="sm" 
                        bg={selectedTask.project.color || 'gray.300'}
                      />
                      <Text>{selectedTask.project.name}</Text>
                    </HStack>
                  </HStack>
                )}

                {/* Assignee */}
                {selectedTask.assignee && (
                  <HStack>
                    <Text fontWeight="medium" w="100px">Assignee:</Text>
                    <HStack>
                      <Avatar 
                        size="xs" 
                        name={selectedTask.assignee.name} 
                        src={selectedTask.assignee.avatar}
                      />
                      <Text>{selectedTask.assignee.name}</Text>
                    </HStack>
                  </HStack>
                )}

                {/* Due Date */}
                {selectedTask.dueDate && (
                  <HStack>
                    <Text fontWeight="medium" w="100px">Due Date:</Text>
                    <Text 
                      color={
                        new Date(selectedTask.dueDate) < new Date() && selectedTask.status !== 'completed' 
                          ? 'red.600' 
                          : 'inherit'
                      }
                    >
                      {new Date(selectedTask.dueDate).toLocaleString()}
                    </Text>
                  </HStack>
                )}

                {/* Tags */}
                {selectedTask.tags && selectedTask.tags.length > 0 && (
                  <Box>
                    <Text fontWeight="medium" mb={2}>Tags:</Text>
                    <HStack wrap="wrap">
                      {selectedTask.tags.map((tag) => (
                        <Tag key={tag} size="sm" variant="outline">
                          {tag}
                        </Tag>
                      ))}
                    </HStack>
                  </Box>
                )}

                {/* Metadata */}
                <VStack align="start" spacing={2}>
                  <Text fontWeight="medium">Source:</Text>
                  <HStack>
                    <Icon 
                      as={
                        selectedTask.source === 'trello' ? ExternalLinkIcon :
                        selectedTask.source === 'asana' ? TaskIcon :
                        SettingsIcon
                      } 
                      w={4} h={4} 
                      color={colors[selectedTask.source as keyof typeof colors] || 'gray.500'}
                    />
                    <Text>{selectedTask.source.toUpperCase()}</Text>
                  </HStack>
                  <HStack>
                    <Text fontSize="xs" color="gray.500">
                      Created: {new Date(selectedTask.createdAt).toLocaleString()}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      Updated: {new Date(selectedTask.updatedAt).toLocaleString()}
                    </Text>
                  </HStack>
                </VStack>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <HStack justify="space-between" w="full">
              <HStack>
                {selectedTask?.url && (
                  <Button
                    leftIcon={<ExternalLinkIcon />}
                    variant="outline"
                    onClick={() => window.open(selectedTask.url, '_blank')}
                  >
                    Open in {selectedTask.source}
                  </Button>
                )}
              </HStack>
              <HStack>
                <Button variant="outline" onClick={() => setShowTaskDetails(false)}>
                  Close
                </Button>
                {selectedTask?.status !== 'completed' && (
                  <Button
                    colorScheme="green"
                    leftIcon={<CheckCircleIcon />}
                    onClick={() => {
                      if (selectedTask) {
                        updateTaskStatus(selectedTask, 'completed');
                        setShowTaskDetails(false);
                      }
                    }}
                  >
                    Complete Task
                  </Button>
                )}
              </HStack>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Task Modal */}
      <Modal 
        isOpen={showCreateTask} 
        onClose={() => setShowCreateTask(false)}
        size="md"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create New Task</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {/* Source Selection */}
              <FormControl>
                <FormLabel>Source</FormLabel>
                <Select
                  value={newTask.source}
                  onChange={(e) => setNewTask(prev => ({ ...prev, source: e.target.value }))}
                >
                  <option value="atom">ATOM</option>
                  {activeIntegrations.includes('trello') && (
                    <option value="trello">Trello</option>
                  )}
                  {activeIntegrations.includes('asana') && (
                    <option value="asana">Asana</option>
                  )}
                </Select>
              </FormControl>

              {/* Title */}
              <FormControl isRequired>
                <FormLabel>Title</FormLabel>
                <Input
                  placeholder="Enter task title"
                  value={newTask.title}
                  onChange={(e) => setNewTask(prev => ({ ...prev, title: e.target.value }))}
                />
              </FormControl>

              {/* Description */}
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  placeholder="Enter task description"
                  value={newTask.description}
                  onChange={(e) => setNewTask(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                />
              </FormControl>

              {/* Priority */}
              <FormControl>
                <FormLabel>Priority</FormLabel>
                <Select
                  value={newTask.priority}
                  onChange={(e) => setNewTask(prev => ({ ...prev, priority: e.target.value }))}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </Select>
              </FormControl>

              {/* Due Date */}
              <FormControl>
                <FormLabel>Due Date</FormLabel>
                <Input
                  type="date"
                  value={newTask.dueDate}
                  onChange={(e) => setNewTask(prev => ({ ...prev, dueDate: e.target.value }))}
                />
              </FormControl>

              {/* Assignee (simplified for demo) */}
              <FormControl>
                <FormLabel>Assignee Email</FormLabel>
                <Input
                  placeholder="user@example.com"
                  value={newTask.assignee}
                  onChange={(e) => setNewTask(prev => ({ ...prev, assignee: e.target.value }))}
                />
              </FormControl>

              {/* Project (simplified for demo) */}
              <FormControl>
                <FormLabel>Project</FormLabel>
                <Input
                  placeholder="Project name or ID"
                  value={newTask.project}
                  onChange={(e) => setNewTask(prev => ({ ...prev, project: e.target.value }))}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack justify="space-between" w="full">
              <Button variant="outline" onClick={() => setShowCreateTask(false)}>
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                leftIcon={<AddIcon />}
                onClick={createTask}
                isDisabled={!newTask.title.trim()}
              >
                Create Task
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Card>
  );
};

export default ATOMAgentTaskUI;