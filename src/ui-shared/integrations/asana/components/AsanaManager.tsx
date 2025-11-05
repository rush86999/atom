import React, { useState, useEffect } from 'react';
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
  Tabs,
  TabList,
  TabPanels,
  TabPanel,
  Tag,
  TagLabel,
  useClipboard,
  Textarea,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Spinner,
  Checkbox,
  RadioGroup,
  Radio,
  CheckboxGroup,
  Stack as CheckboxStack,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
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
  CheckIcon,
  CloseIcon,
  CommentIcon,
  CalendarIcon,
  ClockIcon,
  UserGroupIcon,
  TeamIcon,
  FolderIcon,
  FilterIcon,
  SearchIcon,
  EditIcon as EditTaskIcon,
  DeleteIcon,
  PlusIcon,
  StarIcon,
  RepeatIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface AsanaIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface AsanaTask {
  gid: string;
  name: string;
  assignee: {
    gid: string;
    name: string;
    email: string;
  };
  projects: Array<{
    gid: string;
    name: string;
  }>;
  completed: boolean;
  completed_at: string | null;
  due_at: string | null;
  due_on: string | null;
  created_at: string;
  modified_at: string;
  tags: Array<{
    gid: string;
    name: string;
  }>;
  notes: string;
  html_notes: string;
  url: string;
  permalink_url: string;
  parent: any;
  subtasks: Array<{
    gid: string;
    name: string;
    completed: boolean;
  }>;
  dependencies: Array<any>;
  dependents: Array<any>;
}

interface AsanaProject {
  gid: string;
  name: string;
  notes: string;
  html_notes: string;
  archived: boolean;
  public: boolean;
  color: string;
  created_at: string;
  modified_at: string;
  team: {
    gid: string;
    name: string;
  };
  members: Array<{
    gid: string;
    name: string;
  }>;
  followers: Array<{
    gid: string;
    name: string;
  }>;
  workspace: {
    gid: string;
    name: string;
  };
  due_date: string;
  start_on: string;
  url: string;
  permalink_url: string;
  custom_fields: Array<any>;
  task_count: number;
}

interface AsanaTeam {
  gid: string;
  name: string;
  description: string;
  html_description: string;
  organization: {
    gid: string;
    name: string;
  };
  workspace: {
    gid: string;
    name: string;
  };
  members: Array<{
    gid: string;
    name: string;
  }>;
  url: string;
  permalink_url: string;
}

interface AsanaUser {
  gid: string;
  name: string;
  email: string;
  photo: string;
}

// Asana scopes constant
const ASANA_SCOPES = [
  'default',
  'tasks:read',
  'tasks:write',
  'projects:read',
  'projects:write',
  'teams:read',
  'stories:read',
  'stories:write',
  'comments:read',
  'comments:write'
];

/**
 * Enhanced Asana Integration Manager
 * Complete Asana task management and project coordination system
 */
export const AsanaIntegrationManager: React.FC<AsanaIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Asana',
    platform: 'asana',
    enabled: true,
    settings: {
      workspace_id: process.env.ASANA_WORKSPACE_ID || '',
      contentTypes: ['tasks', 'projects', 'teams'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeCompleted: true,
      includeArchived: false,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['task_assigned', 'task_completed', 'project_created', 'comment_added'],
      projectIds: [],
      teamIds: [],
      assigneeIds: ['me'],
      searchQueries: {
        tasks: '',
        projects: '',
        teams: ''
      },
      filters: {
        tasks: {
          completedOnly: false,
          uncompletedOnly: false,
          dueSoon: false,
          overdue: false,
          priority: '',
          assignee: ''
        },
        projects: {
          archivedOnly: false,
          activeOnly: true,
          team: ''
        }
      }
    }
  });

  // Data states
  const [tasks, setTasks] = useState<AsanaTask[]>([]);
  const [projects, setProjects] = useState<AsanaProject[]>([]);
  const [teams, setTeams] = useState<AsanaTeam[]>([]);
  const [currentUser, setCurrentUser] = useState<AsanaUser | null>(null);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    tasksProcessed: 0,
    projectsProcessed: 0,
    teamsProcessed: 0,
    errors: []
  });

  // Modal states
  const [createTaskModalOpen, setCreateTaskModalOpen] = useState(false);
  const [createProjectModalOpen, setCreateProjectModalOpen] = useState(false);
  const [commentModalOpen, setCommentModalOpen] = useState(false);
  
  // Form states
  const [taskForm, setTaskForm] = useState({
    name: '',
    notes: '',
    assignee: 'me',
    projects: [],
    due_date: '',
    priority: 'medium',
    tags: []
  });
  
  const [projectForm, setProjectForm] = useState({
    name: '',
    notes: '',
    team: '',
    public: true,
    color: 'light-blue',
    start_date: '',
    due_date: ''
  });
  
  const [commentForm, setCommentForm] = useState({
    task_id: '',
    comment: '',
    task_name: ''
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('asana_access_token_placeholder');

  useEffect(() => {
    checkAsanaHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadAsanaData();
    }
  }, [health]);

  const checkAsanaHealth = async () => {
    try {
      const response = await fetch('/api/integrations/asana/health');
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
          errors: [data.error || 'Asana service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Asana service health']
      });
    }
  };

  const loadAsanaData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadTasks(),
        loadProjects(),
        loadTeams(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Asana data');
      toast({
        title: 'Error',
        description: 'Failed to load Asana data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadTasks = async () => {
    try {
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          assignee: config.settings.filters.tasks.assignee || 'me',
          completed: config.settings.filters.tasks.completedOnly ? 'true' : 
                     config.settings.filters.tasks.uncompletedOnly ? 'false' : 
                     config.settings.includeCompleted ? 'all' : 'not_completed',
          priority: config.settings.filters.tasks.priority,
          due_on: config.settings.filters.tasks.dueSoon ? 'today' : 
                  config.settings.filters.tasks.overdue ? 'before_today' : '',
          limit: 50
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setTasks(data.data.tasks || []);
      }
    } catch (err) {
      console.error('Error loading tasks:', err);
    }
  };

  const loadProjects = async () => {
    try {
      const response = await fetch('/api/integrations/asana/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          archived: config.settings.filters.projects.archivedOnly ? 'true' : 
                     config.settings.filters.projects.activeOnly ? 'false' : 
                     config.settings.includeArchived ? 'all' : 'false',
          limit: 50
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setProjects(data.data.projects || []);
      }
    } catch (err) {
      console.error('Error loading projects:', err);
    }
  };

  const loadTeams = async () => {
    try {
      const response = await fetch('/api/integrations/asana/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 50
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setTeams(data.data.teams || []);
      }
    } catch (err) {
      console.error('Error loading teams:', err);
    }
  };

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/asana/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCurrentUser(data.data.user);
      }
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  };

  const createTask = async () => {
    if (!taskForm.name.trim()) {
      toast({
        title: 'Error',
        description: 'Task name is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            name: taskForm.name,
            notes: taskForm.notes,
            assignee: taskForm.assignee,
            projects: taskForm.projects.map((p: any) => ({ name: p })),
            due_at: taskForm.due_date ? new Date(taskForm.due_date).toISOString() : undefined,
            priority: taskForm.priority,
            tags: taskForm.tags.map((tag: any) => ({ name: tag }))
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Task created successfully',
          status: 'success',
          duration: 3000
        });
        
        setTaskForm({ name: '', notes: '', assignee: 'me', projects: [], due_date: '', priority: 'medium', tags: [] });
        setCreateTaskModalOpen(false);
        await loadTasks();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create task',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create task',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const completeTask = async (taskId: string, taskName: string) => {
    setLoading(true);
    try {
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'complete',
          task_id: taskId
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: `Task "${taskName}" completed successfully`,
          status: 'success',
          duration: 3000
        });
        
        await loadTasks();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to complete task',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to complete task',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const addComment = async () => {
    if (!commentForm.task_id.trim() || !commentForm.comment.trim()) {
      toast({
        title: 'Error',
        description: 'Task and comment are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'add_comment',
          task_id: commentForm.task_id,
          comment: commentForm.comment
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Comment added successfully',
          status: 'success',
          duration: 3000
        });
        
        setCommentForm({ task_id: '', comment: '', task_name: '' });
        setCommentModalOpen(false);
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to add comment',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to add comment',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const searchAsana = async () => {
    if (!searchQuery.trim()) {
      await Promise.all([
        loadTasks(),
        loadProjects(),
        loadTeams()
      ]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/asana/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          type: 'all',
          limit: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        const searchResults = result.data.results || [];
        
        // Update data based on search results
        const taskResults = searchResults.filter((r: any) => r.type === 'task');
        const projectResults = searchResults.filter((r: any) => r.type === 'project');
        const teamResults = searchResults.filter((r: any) => r.type === 'team');
        
        if (taskResults.length > 0) {
          const searchTasks = taskResults.map((r: any) => ({
            gid: r.gid,
            name: r.name,
            assignee: { gid: 'user_me', name: 'Me', email: 'me@example.com' },
            projects: [],
            completed: r.completed || false,
            completed_at: r.completed_at || null,
            due_at: r.due_at || null,
            due_on: r.due_on || null,
            created_at: r.created_at || new Date().toISOString(),
            modified_at: r.created_at || new Date().toISOString(),
            tags: [],
            notes: r.notes || '',
            html_notes: `<p>${r.notes || ''}</p>`,
            url: r.url,
            permalink_url: r.url,
            parent: null,
            subtasks: [],
            dependencies: [],
            dependents: []
          }));
          setTasks(searchTasks);
        }
        
        if (projectResults.length > 0) {
          const searchProjects = projectResults.map((r: any) => ({
            gid: r.gid,
            name: r.name,
            notes: r.notes || '',
            html_notes: `<p>${r.notes || ''}</p>`,
            archived: r.archived || false,
            public: true,
            color: 'light-blue',
            created_at: r.created_at || new Date().toISOString(),
            modified_at: r.created_at || new Date().toISOString(),
            team: { gid: 'team_search', name: 'Search Team' },
            members: [],
            followers: [],
            workspace: { gid: 'workspace_search', name: 'Search Workspace' },
            due_date: '',
            start_on: '',
            url: r.url,
            permalink_url: r.url,
            custom_fields: [],
            task_count: 0
          }));
          setProjects(searchProjects);
        }
        
        if (teamResults.length > 0) {
          const searchTeams = teamResults.map((r: any) => ({
            gid: r.gid,
            name: r.name,
            description: r.description || '',
            html_description: `<p>${r.description || ''}</p>`,
            organization: { gid: 'org_search', name: 'Search Organization' },
            workspace: { gid: 'workspace_search', name: 'Search Workspace' },
            members: [],
            url: r.url,
            permalink_url: r.url
          }));
          setTeams(searchTeams);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Asana',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startAsanaOAuth = async () => {
    try {
      const response = await fetch('/api/auth/asana/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: ASANA_SCOPES,
          redirect_uri: 'http://localhost:3000/oauth/asana/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        const popup = window.open(
          data.authorization_url,
          'asana-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkAsanaHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Asana OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Asana OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderTaskCard = (task: AsanaTask) => (
    <Card key={task.gid} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Checkbox
                isChecked={task.completed}
                onChange={() => completeTask(task.gid, task.name)}
                isDisabled={loading}
              />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={2} textDecoration={task.completed ? 'line-through' : 'none'}>
                  {task.name}
                </Heading>
                {task.assignee && (
                  <Text fontSize="xs" color="gray.500">
                    Assigned to {task.assignee.name}
                  </Text>
                )}
              </VStack>
            </HStack>
            <HStack>
              {task.completed && <Badge colorScheme="green">Completed</Badge>}
              {task.due_at && (
                <Text fontSize="xs" color={new Date(task.due_at) < new Date() ? 'red.500' : 'gray.500'}>
                  Due {new Date(task.due_at).toLocaleDateString()}
                </Text>
              )}
              {task.tags && task.tags.length > 0 && (
                <Badge colorScheme="blue">{task.tags.length} tag{task.tags.length !== 1 ? 's' : ''}</Badge>
              )}
            </HStack>
          </HStack>
          
          {task.notes && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {task.notes}
            </Text>
          )}
          
          {task.projects && task.projects.length > 0 && (
            <HStack spacing={2} fontSize="xs" color="gray.500">
              <Tag size="sm" colorScheme="gray">
                <TagLabel>{task.projects.map(p => p.name).join(', ')}</TagLabel>
              </Tag>
            </HStack>
          )}
          
          {task.subtasks && task.subtasks.length > 0 && (
            <HStack spacing={2} fontSize="xs" color="gray.500">
              <Text>{task.subtasks.filter(st => st.completed).length}/{task.subtasks.length} subtasks completed</Text>
              <Progress value={(task.subtasks.filter(st => st.completed).length / task.subtasks.length) * 100} size="xs" w="100px" />
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Created {new Date(task.created_at).toLocaleDateString()}
            </Text>
            
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<CommentIcon />}
                onClick={() => {
                  setCommentForm({
                    task_id: task.gid,
                    comment: '',
                    task_name: task.name
                  });
                  setCommentModalOpen(true);
                }}
              >
                Comment
              </Button>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ViewIcon />}
                onClick={() => window.open(task.url, '_blank')}
              >
                View
              </Button>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderProjectCard = (project: AsanaProject) => (
    <Card key={project.gid} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <VStack align="start" spacing={1}>
              <Heading size="sm" noOfLines={2}>
                {project.name}
              </Heading>
              {project.team && (
                <Text fontSize="sm" color="gray.600">
                  Team: {project.team.name}
                </Text>
              )}
            </VStack>
            <HStack>
              {project.archived && <Badge colorScheme="red">Archived</Badge>}
              {project.public && <Badge colorScheme="green">Public</Badge>}
              {project.task_count > 0 && (
                <Badge colorScheme="blue">{project.task_count} tasks</Badge>
              )}
            </HStack>
          </HStack>
          
          {project.notes && (
            <Text fontSize="sm" color="gray.600" noOfLines={3}>
              {project.notes}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            {project.due_date && (
              <Text>Due: {new Date(project.due_date).toLocaleDateString()}</Text>
            )}
            {project.start_on && (
              <Text>Started: {new Date(project.start_on).toLocaleDateString()}</Text>
            )}
            {project.members && project.members.length > 0 && (
              <Text>{project.members.length} members</Text>
            )}
          </HStack>
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Created {new Date(project.created_at).toLocaleDateString()}
            </Text>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ViewIcon />}
              onClick={() => window.open(project.url, '_blank')}
            >
              View Project
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderTeamCard = (team: AsanaTeam) => (
    <Card key={team.gid} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <VStack align="start" spacing={1}>
              <Heading size="sm" noOfLines={2}>
                {team.name}
              </Heading>
              {team.organization && (
                <Text fontSize="sm" color="gray.600">
                  Organization: {team.organization.name}
                </Text>
              )}
            </VStack>
            <Icon as={TeamIcon} color="blue.500" />
          </HStack>
          
          {team.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={3}>
              {team.description}
            </Text>
          )}
          
          {team.members && team.members.length > 0 && (
            <HStack spacing={2} fontSize="xs" color="gray.500">
              <Tag size="sm" colorScheme="gray">
                <TagLabel>{team.members.length} member{team.members.length !== 1 ? 's' : ''}</TagLabel>
              </Tag>
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Workspace: {team.workspace.name}
            </Text>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ViewIcon />}
              onClick={() => window.open(team.url, '_blank')}
            >
              View Team
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  if (!health?.connected) {
    return (
      <Box p={6}>
        <Alert status="warning">
          <AlertIcon />
          <Box>
            <AlertTitle>Asana Not Connected</AlertTitle>
            <AlertDescription>
              Please connect your Asana account to access tasks, projects, and teams.
            </AlertDescription>
          </Box>
        </Alert>
        <Button
          mt={4}
          colorScheme="blue"
          onClick={startAsanaOAuth}
        >
          Connect Asana Account
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Asana Integration</Heading>
          <Text color="gray.600">Manage tasks, projects, and teams</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search tasks, projects, teams..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchAsana()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="blue"
            onClick={searchAsana}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<PlusIcon />}
            colorScheme="green"
            onClick={() => setCreateTaskModalOpen(true)}
          >
            New Task
          </Button>
          
          <Button
            leftIcon={<FolderIcon />}
            colorScheme="purple"
            onClick={() => setCreateProjectModalOpen(true)}
          >
            New Project
          </Button>
        </HStack>

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <ViewListIcon />
                <Text>Tasks ({tasks.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <FolderIcon />
                <Text>Projects ({projects.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <TeamIcon />
                <Text>Teams ({teams.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <UserIcon />
                <Text>Profile</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Tasks Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : tasks.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <ViewListIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No tasks found</Text>
                  <Button
                    mt={4}
                    colorScheme="green"
                    onClick={() => setCreateTaskModalOpen(true)}
                  >
                    Create Your First Task
                  </Button>
                </Box>
              ) : (
                <VStack spacing={4} align="stretch">
                  {tasks.map(renderTaskCard)}
                </VStack>
              )}
            </TabPanel>

            {/* Projects Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : projects.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <FolderIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No projects found</Text>
                  <Button
                    mt={4}
                    colorScheme="purple"
                    onClick={() => setCreateProjectModalOpen(true)}
                  >
                    Create Your First Project
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {projects.map(renderProjectCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Teams Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : teams.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <TeamIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No teams found</Text>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {teams.map(renderTeamCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Profile Tab */}
            <TabPanel>
              <Card>
                <CardBody p={6}>
                  <VStack spacing={4} align="center">
                    <Avatar
                      name={currentUser?.name}
                      src={currentUser?.photo}
                      size="2xl"
                      bg="blue.500"
                      color="white"
                    />
                    <VStack align="center" spacing={2}>
                      <Heading size="lg">{currentUser?.name}</Heading>
                      <Text color="gray.600">{currentUser?.email}</Text>
                      <Text fontSize="sm" color="gray.500">
                        User ID: {currentUser?.gid}
                      </Text>
                    </VStack>
                    
                    <Divider />
                    
                    <VStack align="start" spacing={2} w="full">
                      <HStack justify="space-between" w="full">
                        <Text>Services</Text>
                        <HStack>
                          <Badge colorScheme="green">Tasks</Badge>
                          <Badge colorScheme="purple">Projects</Badge>
                          <Badge colorScheme="blue">Teams</Badge>
                          <Badge colorScheme="orange">Search</Badge>
                        </HStack>
                      </HStack>
                      
                      <HStack justify="space-between" w="full">
                        <Text>Workspace ID</Text>
                        <Text>{config.settings.workspace_id}</Text>
                      </HStack>
                      
                      <Button
                        colorScheme="blue"
                        onClick={() => window.open('https://app.asana.com', '_blank')}
                      >
                        Open Asana
                      </Button>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Task Modal */}
        <Modal isOpen={createTaskModalOpen} onClose={() => setCreateTaskModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Task</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Task Name</FormLabel>
                  <Input
                    value={taskForm.name}
                    onChange={(e) => setTaskForm({...taskForm, name: e.target.value})}
                    placeholder="Enter task name"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={taskForm.notes}
                    onChange={(e) => setTaskForm({...taskForm, notes: e.target.value})}
                    placeholder="Enter task description"
                    rows={4}
                  />
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Assignee</FormLabel>
                    <Select
                      value={taskForm.assignee}
                      onChange={(e) => setTaskForm({...taskForm, assignee: e.target.value})}
                    >
                      <option value="me">Me</option>
                      <option value="unassigned">Unassigned</option>
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Priority</FormLabel>
                    <Select
                      value={taskForm.priority}
                      onChange={(e) => setTaskForm({...taskForm, priority: e.target.value})}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </Select>
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Project</FormLabel>
                    <Select
                      value={taskForm.projects[0] || ''}
                      onChange={(e) => setTaskForm({...taskForm, projects: [e.target.value]})}
                    >
                      <option value="">Select project</option>
                      {projects.map((project) => (
                        <option key={project.gid} value={project.name}>
                          {project.name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Due Date</FormLabel>
                    <Input
                      type="date"
                      value={taskForm.due_date}
                      onChange={(e) => setTaskForm({...taskForm, due_date: e.target.value})}
                    />
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Tags</FormLabel>
                  <Input
                    value={taskForm.tags.join(', ')}
                    onChange={(e) => setTaskForm({...taskForm, tags: e.target.value.split(',').map(tag => tag.trim()).filter(tag => tag)})}
                    placeholder="Enter tags separated by commas"
                  />
                  <FormHelperText>
                    Separate multiple tags with commas
                  </FormHelperText>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateTaskModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="green"
                onClick={createTask}
                isLoading={loading}
              >
                Create Task
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Project Modal */}
        <Modal isOpen={createProjectModalOpen} onClose={() => setCreateProjectModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Project</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Project Name</FormLabel>
                  <Input
                    value={projectForm.name}
                    onChange={(e) => setProjectForm({...projectForm, name: e.target.value})}
                    placeholder="Enter project name"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={projectForm.notes}
                    onChange={(e) => setProjectForm({...projectForm, notes: e.target.value})}
                    placeholder="Enter project description"
                    rows={4}
                  />
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Team</FormLabel>
                    <Select
                      value={projectForm.team}
                      onChange={(e) => setProjectForm({...projectForm, team: e.target.value})}
                    >
                      <option value="">Select team</option>
                      {teams.map((team) => (
                        <option key={team.gid} value={team.gid}>
                          {team.name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Color</FormLabel>
                    <Select
                      value={projectForm.color}
                      onChange={(e) => setProjectForm({...projectForm, color: e.target.value})}
                    >
                      <option value="light-blue">Light Blue</option>
                      <option value="light-green">Light Green</option>
                      <option value="light-orange">Light Orange</option>
                      <option value="light-red">Light Red</option>
                      <option value="light-purple">Light Purple</option>
                    </Select>
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Start Date</FormLabel>
                    <Input
                      type="date"
                      value={projectForm.start_date}
                      onChange={(e) => setProjectForm({...projectForm, start_date: e.target.value})}
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Due Date</FormLabel>
                    <Input
                      type="date"
                      value={projectForm.due_date}
                      onChange={(e) => setProjectForm({...projectForm, due_date: e.target.value})}
                    />
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Visibility</FormLabel>
                  <Switch
                    isChecked={projectForm.public}
                    onChange={(e) => setProjectForm({...projectForm, public: e.target.checked})}
                  >
                    Public project
                  </Switch>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateProjectModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={() => {/* Create project logic */}}
                isLoading={loading}
              >
                Create Project
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Add Comment Modal */}
        <Modal isOpen={commentModalOpen} onClose={() => setCommentModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add Comment</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Task</FormLabel>
                  <Input
                    value={commentForm.task_name}
                    isDisabled
                    placeholder="Task name"
                  />
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Comment</FormLabel>
                  <Textarea
                    value={commentForm.comment}
                    onChange={(e) => setCommentForm({...commentForm, comment: e.target.value})}
                    placeholder="Enter your comment"
                    rows={6}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCommentModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={addComment}
                isLoading={loading}
              >
                Add Comment
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default AsanaIntegrationManager;