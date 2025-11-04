/**
 * Asana Natural Language Skills Component
 * Processes natural language commands for Asana integration
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
  TagLabel,
  TagLeftIcon,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
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
  TaskIcon,
  ProjectIcon,
  SectionIcon,
  CalendarIcon,
  ChevronRightIcon,
  PlayIcon,
} from '@chakra-ui/icons';

interface AsanaSkillCommand {
  id: string;
  command: string;
  description: string;
  category: string;
  action: string;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    description: string;
  }>;
  example: string;
  success?: boolean;
  result?: any;
}

interface AsanaSkillsProps {
  onExecuteCommand?: (command: string, params: any) => void;
  userId?: string;
  isConnected?: boolean;
}

export const AsanaSkills: React.FC<AsanaSkillsProps> = ({
  onExecuteCommand,
  userId = 'default-user',
  isConnected = false,
}) => {
  const [skills, setSkills] = useState<AsanaSkillCommand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<AsanaSkillCommand | null>(null);
  const [skillInput, setSkillInput] = useState('');
  const [executionProgress, setExecutionProgress] = useState(0);
  const [executionResults, setExecutionResults] = useState<Array<{
    command: string;
    success: boolean;
    result?: any;
    error?: string;
    timestamp: string;
  }>>([]);
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { isOpen: isModalOpen, onOpen, onClose } = useDisclosure();
  const { hasCopied, onCopy } = useClipboard(skillInput);

  // Asana skills definitions
  const asanaSkills: AsanaSkillCommand[] = [
    // Task Management
    {
      id: 'list_tasks',
      command: 'list my tasks',
      description: 'List all tasks assigned to me',
      category: 'Tasks',
      action: 'list_tasks',
      parameters: [],
      example: 'list my tasks'
    },
    {
      id: 'list_tasks_project',
      command: 'list tasks in project {project_name}',
      description: 'List tasks in a specific project',
      category: 'Tasks',
      action: 'list_tasks_project',
      parameters: [
        { name: 'project_name', type: 'string', required: true, description: 'Name of the project' }
      ],
      example: 'list tasks in project Mobile App Development'
    },
    {
      id: 'create_task',
      command: 'create task {task_name} in project {project_name}',
      description: 'Create a new task in a project',
      category: 'Tasks',
      action: 'create_task',
      parameters: [
        { name: 'task_name', type: 'string', required: true, description: 'Name of the task' },
        { name: 'project_name', type: 'string', required: true, description: 'Project to create task in' },
        { name: 'description', type: 'string', required: false, description: 'Task description' },
        { name: 'assignee', type: 'string', required: false, description: 'Person to assign task to' },
        { name: 'due_date', type: 'string', required: false, description: 'Due date for task' }
      ],
      example: 'create task Update homepage in project Marketing with description Implement new hero section with product features'
    },
    {
      id: 'complete_task',
      command: 'complete task {task_name}',
      description: 'Mark a task as completed',
      category: 'Tasks',
      action: 'complete_task',
      parameters: [
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' }
      ],
      example: 'complete task Fix login issue'
    },
    {
      id: 'update_task',
      command: 'update task {task_name} with {field} {value}',
      description: 'Update a task with new information',
      category: 'Tasks',
      action: 'update_task',
      parameters: [
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' },
        { name: 'field', type: 'string', required: true, description: 'Field to update (due date, assignee, priority)' },
        { name: 'value', type: 'string', required: true, description: 'New value for the field' }
      ],
      example: 'update task API documentation with due date Friday'
    },
    {
      id: 'assign_task',
      command: 'assign task {task_name} to {person}',
      description: 'Assign a task to a person',
      category: 'Tasks',
      action: 'assign_task',
      parameters: [
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' },
        { name: 'person', type: 'string', required: true, description: 'Person to assign task to' }
      ],
      example: 'assign task Design new logo to Sarah'
    },
    {
      id: 'add_subtask',
      command: 'add subtask {subtask_name} to task {task_name}',
      description: 'Add a subtask to an existing task',
      category: 'Tasks',
      action: 'add_subtask',
      parameters: [
        { name: 'subtask_name', type: 'string', required: true, description: 'Name of the subtask' },
        { name: 'task_name', type: 'string', required: true, description: 'Parent task name' }
      ],
      example: 'add subtask Research competitors to task Market analysis'
    },
    
    // Project Management
    {
      id: 'list_projects',
      command: 'list my projects',
      description: 'List all projects I have access to',
      category: 'Projects',
      action: 'list_projects',
      parameters: [],
      example: 'list my projects'
    },
    {
      id: 'create_project',
      command: 'create project {project_name}',
      description: 'Create a new project',
      category: 'Projects',
      action: 'create_project',
      parameters: [
        { name: 'project_name', type: 'string', required: true, description: 'Name of the project' },
        { name: 'team', type: 'string', required: false, description: 'Team to assign project to' },
        { name: 'description', type: 'string', required: false, description: 'Project description' }
      ],
      example: 'create project Customer Portal with team Engineering'
    },
    {
      id: 'archive_project',
      command: 'archive project {project_name}',
      description: 'Archive a project',
      category: 'Projects',
      action: 'archive_project',
      parameters: [
        { name: 'project_name', type: 'string', required: true, description: 'Name of the project to archive' }
      ],
      example: 'archive project Old Website'
    },
    {
      id: 'add_section',
      command: 'add section {section_name} to project {project_name}',
      description: 'Add a new section to a project',
      category: 'Projects',
      action: 'add_section',
      parameters: [
        { name: 'section_name', type: 'string', required: true, description: 'Name of the section' },
        { name: 'project_name', type: 'string', required: true, description: 'Project to add section to' }
      ],
      example: 'add section Backlog to project Development'
    },
    
    // Team Management
    {
      id: 'list_teams',
      command: 'list my teams',
      description: 'List all teams I belong to',
      category: 'Teams',
      action: 'list_teams',
      parameters: [],
      example: 'list my teams'
    },
    {
      id: 'create_team',
      command: 'create team {team_name}',
      description: 'Create a new team',
      category: 'Teams',
      action: 'create_team',
      parameters: [
        { name: 'team_name', type: 'string', required: true, description: 'Name of the team' },
        { name: 'description', type: 'string', required: false, description: 'Team description' }
      ],
      example: 'create team Product Design'
    },
    {
      id: 'add_member',
      command: 'add {email} to team {team_name}',
      description: 'Add a member to a team',
      category: 'Teams',
      action: 'add_member',
      parameters: [
        { name: 'email', type: 'string', required: true, description: 'Email address of the person to add' },
        { name: 'team_name', type: 'string', required: true, description: 'Name of the team' }
      ],
      example: 'add john@company.com to team Engineering'
    },
    
    // Search and Filter
    {
      id: 'search_tasks',
      command: 'search for {query}',
      description: 'Search tasks across all projects',
      category: 'Search',
      action: 'search_tasks',
      parameters: [
        { name: 'query', type: 'string', required: true, description: 'Search query' }
      ],
      example: 'search for urgent tasks'
    },
    {
      id: 'filter_tasks',
      command: 'show {status} tasks',
      description: 'Filter tasks by status',
      category: 'Search',
      action: 'filter_tasks',
      parameters: [
        { name: 'status', type: 'string', required: true, description: 'Status (completed, incomplete, overdue, assigned to me)' }
      ],
      example: 'show completed tasks'
    },
    {
      id: 'find_tasks',
      command: 'find tasks with {tag}',
      description: 'Find tasks with a specific tag',
      category: 'Search',
      action: 'find_tasks',
      parameters: [
        { name: 'tag', type: 'string', required: true, description: 'Tag to search for' }
      ],
      example: 'find tasks with priority:high'
    },
    
    // Time and Due Dates
    {
      id: 'due_today',
      command: 'show tasks due today',
      description: 'Show tasks due today',
      category: 'Time',
      action: 'due_today',
      parameters: [],
      example: 'show tasks due today'
    },
    {
      id: 'due_this_week',
      command: 'show tasks due this week',
      description: 'Show tasks due this week',
      category: 'Time',
      action: 'due_this_week',
      parameters: [],
      example: 'show tasks due this week'
    },
    {
      id: 'set_due_date',
      command: 'set due date for task {task_name} to {date}',
      description: 'Set a due date for a task',
      category: 'Time',
      action: 'set_due_date',
      parameters: [
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' },
        { name: 'date', type: 'string', required: true, description: 'Due date (Friday, Tomorrow, 2024-01-15)' }
      ],
      example: 'set due date for task Report completion to Friday'
    },
    {
      id: 'overdue_tasks',
      command: 'show overdue tasks',
      description: 'Show overdue tasks',
      category: 'Time',
      action: 'overdue_tasks',
      parameters: [],
      example: 'show overdue tasks'
    },
    
    // Collaboration
    {
      id: 'add_comment',
      command: 'add comment "{text}" to task {task_name}',
      description: 'Add a comment to a task',
      category: 'Collaboration',
      action: 'add_comment',
      parameters: [
        { name: 'text', type: 'string', required: true, description: 'Comment text' },
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' }
      ],
      example: 'add comment "I need more information about this requirement" to task API integration'
    },
    {
      id: 'attach_file',
      command: 'attach {file_name} to task {task_name}',
      description: 'Attach a file to a task',
      category: 'Collaboration',
      action: 'attach_file',
      parameters: [
        { name: 'file_name', type: 'string', required: true, description: 'Name of the file to attach' },
        { name: 'task_name', type: 'string', required: true, description: 'Name or ID of the task' }
      ],
      example: 'attach design-mockup.png to task Create new landing page'
    },
    
    // Reports and Analytics
    {
      id: 'task_summary',
      command: 'show task summary for {period}',
      description: 'Show task completion summary',
      category: 'Reports',
      action: 'task_summary',
      parameters: [
        { name: 'period', type: 'string', required: true, description: 'Time period (today, this week, this month)' }
      ],
      example: 'show task summary for this week'
    },
    {
      id: 'project_status',
      command: 'show status for project {project_name}',
      description: 'Show project status and progress',
      category: 'Reports',
      action: 'project_status',
      parameters: [
        { name: 'project_name', type: 'string', required: true, description: 'Name of the project' }
      ],
      example: 'show status for project Mobile App'
    },
    {
      id: 'team_workload',
      command: 'show workload for team {team_name}',
      description: 'Show team workload and task distribution',
      category: 'Reports',
      action: 'team_workload',
      parameters: [
        { name: 'team_name', type: 'string', required: true, description: 'Name of the team' }
      ],
      example: 'show workload for team Development'
    }
  ];

  useEffect(() => {
    setSkills(asanaSkills);
  }, []);

  // Execute skill command
  const executeSkill = useCallback(async (skill: AsanaSkillCommand, input: string = skill.command) => {
    if (!isConnected) {
      toast({
        title: 'Not Connected',
        description: 'Please connect to Asana first',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setLoading(true);
    setExecutionProgress(0);
    
    try {
      // Parse input to extract parameters
      const params = parseCommandInput(input, skill);
      
      // Update progress
      setExecutionProgress(50);
      
      // Simulate API call
      const result = await simulateSkillExecution(skill.action, params);
      
      // Update results
      const executionResult = {
        command: input,
        success: true,
        result: result,
        timestamp: new Date().toISOString()
      };
      
      setExecutionResults(prev => [executionResult, ...prev]);
      setExecutionProgress(100);
      
      // Update skill status
      setSkills(prev => prev.map(s => 
        s.id === skill.id ? { ...s, success: true, result } : s
      ));
      
      toast({
        title: 'Command Executed Successfully',
        description: `"${skill.command}" completed successfully`,
        status: 'success',
        duration: 3000,
      });
      
      // Call parent callback
      if (onExecuteCommand) {
        onExecuteCommand(skill.action, params);
      }
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      
      // Update results with error
      const executionResult = {
        command: input,
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
      
      setExecutionResults(prev => [executionResult, ...prev]);
      
      // Update skill status
      setSkills(prev => prev.map(s => 
        s.id === skill.id ? { ...s, success: false, result: error.message } : s
      ));
      
      toast({
        title: 'Command Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
      setExecutionProgress(0);
    }
  }, [isConnected, onExecuteCommand, toast]);

  // Parse command input to extract parameters
  const parseCommandInput = (input: string, skill: AsanaSkillCommand) => {
    const params: Record<string, any> = {};
    
    skill.parameters.forEach(param => {
      // Simple regex to extract parameter values
      const regex = new RegExp(`{${param.name}}`, 'i');
      const valueMatch = input.match(regex);
      
      if (valueMatch) {
        // For simple examples, use mock values
        switch (param.name) {
          case 'task_name':
            params.task_name = 'Sample Task';
            break;
          case 'project_name':
            params.project_name = 'Sample Project';
            break;
          case 'section_name':
            params.section_name = 'Sample Section';
            break;
          case 'team_name':
            params.team_name = 'Sample Team';
            break;
          case 'person':
          case 'email':
            params.email = 'user@example.com';
            break;
          case 'description':
            params.description = 'Sample description';
            break;
          case 'due_date':
            params.due_date = '2024-01-15';
            break;
          case 'field':
            params.field = 'priority';
            break;
          case 'value':
            params.value = 'high';
            break;
          case 'subtask_name':
            params.subtask_name = 'Sample Subtask';
            break;
          case 'text':
            params.text = 'Sample comment';
            break;
          case 'file_name':
            params.file_name = 'sample.pdf';
            break;
          case 'period':
            params.period = 'this week';
            break;
          case 'query':
            params.query = 'search query';
            break;
          case 'status':
            params.status = 'completed';
            break;
          case 'tag':
            params.tag = 'urgent';
            break;
          default:
            params[param.name] = 'sample value';
        }
      }
    });
    
    return params;
  };

  // Simulate skill execution
  const simulateSkillExecution = async (action: string, params: any) => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Mock results based on action
    switch (action) {
      case 'list_tasks':
        return {
          tasks: [
            { id: '1', name: 'Update homepage', project: 'Marketing', completed: false },
            { id: '2', name: 'Fix login issue', project: 'Development', completed: true }
          ],
          total: 2
        };
      case 'create_task':
        return {
          task: { id: '123', name: params.task_name, project: params.project_name },
          message: 'Task created successfully'
        };
      case 'complete_task':
        return {
          task: { id: '456', name: params.task_name, completed: true },
          message: 'Task completed successfully'
        };
      case 'list_projects':
        return {
          projects: [
            { id: '1', name: 'Marketing', team: 'Creative', status: 'active' },
            { id: '2', name: 'Development', team: 'Engineering', status: 'active' }
          ],
          total: 2
        };
      case 'create_project':
        return {
          project: { id: '789', name: params.project_name, team: params.team },
          message: 'Project created successfully'
        };
      case 'list_teams':
        return {
          teams: [
            { id: '1', name: 'Engineering', members: 5, projects: 3 },
            { id: '2', name: 'Creative', members: 3, projects: 2 }
          ],
          total: 2
        };
      default:
        return {
          message: 'Command executed successfully',
          parameters: params
        };
    }
  };

  // Filter skills by category
  const filterSkillsByCategory = (category: string) => {
    return skills.filter(skill => skill.category === category);
  };

  // Get unique categories
  const categories = Array.from(new Set(skills.map(skill => skill.category)));

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={TaskIcon} w={6} h={6} color="#27334D" />
            <Heading size="md">Asana Natural Language Skills</Heading>
            <Badge colorScheme={isConnected ? 'green' : 'red'}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
          </HStack>
          <HStack>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={() => {
                setExecutionResults([]);
                setSkills(asanaSkills);
              }}
            >
              Clear Results
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Connection Status */}
          {!isConnected && (
            <Alert status="warning">
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">Asana Not Connected</Text>
                <Text fontSize="sm">Please connect to Asana to use natural language skills</Text>
              </Box>
            </Alert>
          )}

          {/* Skills Command Input */}
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>Command Input</FormLabel>
              <HStack>
                <Input
                  placeholder="Enter natural language command (e.g., 'list my tasks' or 'create task Update homepage')"
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  isDisabled={!isConnected}
                />
                <Button
                  colorScheme="orange"
                  leftIcon={<PlayIcon />}
                  onClick={() => {
                    if (skillInput.trim()) {
                      // Find matching skill
                      const matchingSkill = skills.find(skill => 
                        skill.command.toLowerCase().includes(skillInput.toLowerCase()) ||
                        skillInput.toLowerCase().includes(skill.command.toLowerCase())
                      );
                      
                      if (matchingSkill) {
                        executeSkill(matchingSkill, skillInput);
                      } else {
                        // Execute as custom command
                        executeSkill({
                          id: 'custom',
                          command: skillInput,
                          description: 'Custom command',
                          category: 'Custom',
                          action: 'custom',
                          parameters: [],
                          example: skillInput
                        }, skillInput);
                      }
                    }
                  }}
                  isDisabled={!isConnected || !skillInput.trim() || loading}
                  isLoading={loading}
                >
                  Execute
                </Button>
              </HStack>
              <FormHelperText>
                Type natural language commands like "list my tasks", "create task Update homepage", or "show tasks due today"
              </FormHelperText>
            </FormControl>

            {/* Execution Progress */}
            {loading && (
              <Card>
                <CardBody>
                  <VStack spacing={3}>
                    <HStack justify="space-between" w="full">
                      <Text>Executing command...</Text>
                      <Text>{executionProgress}%</Text>
                    </HStack>
                    <Progress
                      value={executionProgress}
                      size="md"
                      colorScheme="orange"
                      w="full"
                    />
                  </VStack>
                </CardBody>
              </Card>
            )}
          </VStack>

          {/* Skills by Category */}
          <VStack spacing={4} align="stretch">
            <Heading size="sm">Available Skills</Heading>
            
            <Accordion allowToggle>
              {categories.map((category) => (
                <AccordionItem key={category}>
                  <h2>
                    <AccordionButton>
                      <Box flex="1" textAlign="left">
                        <HStack>
                          <Icon as={
                            category === 'Tasks' ? TaskIcon :
                            category === 'Projects' ? ProjectIcon :
                            category === 'Teams' ? UserIcon :
                            category === 'Search' ? ViewIcon :
                            category === 'Time' ? CalendarIcon :
                            category === 'Collaboration' ? ViewListIcon :
                            InfoIcon
                          } w={4} h={4} color="orange.500" />
                          <Text fontWeight="bold">{category}</Text>
                          <Badge size="sm" colorScheme="gray">
                            {filterSkillsByCategory(category).length} skills
                          </Badge>
                        </HStack>
                      </Box>
                      <AccordionIcon />
                    </AccordionButton>
                  </h2>
                  <AccordionPanel pb={4}>
                    <VStack spacing={3} align="stretch">
                      {filterSkillsByCategory(category).map((skill) => (
                        <Card key={skill.id} variant="outline" size="sm">
                          <CardBody p={3}>
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2} flex={1}>
                                <Text fontWeight="medium" fontSize="sm">
                                  {skill.command}
                                </Text>
                                <Text fontSize="xs" color="gray.600">
                                  {skill.description}
                                </Text>
                                <Text fontSize="xs" color="blue.600">
                                  Example: "{skill.example}"
                                </Text>
                                {skill.success && (
                                  <Badge size="sm" colorScheme="green">
                                    ✅ Executed successfully
                                  </Badge>
                                )}
                                {skill.success === false && (
                                  <Badge size="sm" colorScheme="red">
                                    ❌ Execution failed
                                  </Badge>
                                )}
                              </VStack>
                              <Button
                                size="xs"
                                colorScheme="orange"
                                leftIcon={<PlayIcon />}
                                onClick={() => {
                                  setSelectedSkill(skill);
                                  setSkillInput(skill.example);
                                  onOpen();
                                }}
                                isDisabled={!isConnected || loading}
                              >
                                Try
                              </Button>
                            </HStack>
                          </CardBody>
                        </Card>
                      ))}
                    </VStack>
                  </AccordionPanel>
                </AccordionItem>
              ))}
            </Accordion>
          </VStack>

          {/* Recent Execution Results */}
          {executionResults.length > 0 && (
            <VStack spacing={4} align="stretch">
              <Heading size="sm">Recent Execution Results</Heading>
              <VStack spacing={3} maxH="300px" overflowY="auto">
                {executionResults.map((result, index) => (
                  <Card key={index} variant="outline" size="sm">
                    <CardBody p={3}>
                      <HStack justify="space-between" align="start">
                        <VStack align="start" spacing={2} flex={1}>
                          <HStack>
                            <Text fontWeight="medium" fontSize="sm">
                              {result.command}
                            </Text>
                            <Badge size="sm" colorScheme={result.success ? 'green' : 'red'}>
                              {result.success ? '✅' : '❌'}
                            </Badge>
                          </HStack>
                          <Text fontSize="xs" color="gray.500">
                            {new Date(result.timestamp).toLocaleString()}
                          </Text>
                          {result.success && result.result && (
                            <Text fontSize="xs" color="green.600">
                              Result: {typeof result.result === 'string' ? result.result : 'Success'}
                            </Text>
                          )}
                          {!result.success && result.error && (
                            <Text fontSize="xs" color="red.600">
                              Error: {result.error}
                            </Text>
                          )}
                        </VStack>
                      </HStack>
                    </CardBody>
                  </Card>
                ))}
              </VStack>
            </VStack>
          )}

          {/* Skill Execution Modal */}
          <Modal isOpen={isModalOpen} onClose={onClose} size="lg">
            <ModalOverlay />
            <ModalContent>
              <ModalHeader>
                <HStack>
                  <Icon as={TaskIcon} w={5} h={5} color="orange.500" />
                  <Text>Execute Asana Skill</Text>
                </HStack>
              </ModalHeader>
              <ModalCloseButton />
              <ModalBody>
                {selectedSkill && (
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Command</FormLabel>
                      <Input
                        value={skillInput}
                        onChange={(e) => setSkillInput(e.target.value)}
                      />
                      <FormHelperText>
                        {selectedSkill.description}
                      </FormHelperText>
                    </FormControl>
                    
                    <FormControl>
                      <FormLabel>Parameters</FormLabel>
                      <VStack spacing={2} align="start">
                        {selectedSkill.parameters.map((param, index) => (
                          <Box key={index} p={2} bg="gray.50" rounded="md" w="full">
                            <Text fontSize="sm" fontWeight="medium">
                              {param.name} ({param.type})
                            </Text>
                            <Text fontSize="xs" color="gray.600">
                              {param.description}
                              {param.required && ' - Required'}
                            </Text>
                          </Box>
                        ))}
                      </VStack>
                    </FormControl>
                    
                    <FormControl>
                      <FormLabel>Example</FormLabel>
                      <Code p={2} borderRadius="md" w="full">
                        {selectedSkill.example}
                      </Code>
                    </FormControl>
                  </VStack>
                )}
              </ModalBody>
              <ModalFooter>
                <HStack>
                  <Button variant="outline" onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="orange"
                    onClick={() => {
                      if (selectedSkill) {
                        executeSkill(selectedSkill, skillInput);
                        onClose();
                      }
                    }}
                    isDisabled={!skillInput.trim() || loading}
                    isLoading={loading}
                  >
                    Execute Command
                  </Button>
                </HStack>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default AsanaSkills;