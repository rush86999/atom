import React, { useState, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  IconButton,
  Badge,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Checkbox,
  Switch,
  useDisclosure,
  SimpleGrid,
  Flex,
  Divider,
  Alert,
  AlertIcon,
  Progress,
  Avatar,
  AvatarGroup,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
} from "@chakra-ui/react";
import {
  AddIcon,
  TimeIcon,
  EditIcon,
  DeleteIcon,
  CheckCircleIcon,
  TimeIcon,
  ViewIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  AttachmentIcon,
  ChatIcon,
  StarIcon,
} from "@chakra-ui/icons";

export interface Task {
  id: string;
  title: string;
  description?: string;
  dueDate: Date;
  priority: "high" | "medium" | "low";
  status: "todo" | "in-progress" | "completed" | "blocked";
  project?: string;
  tags?: string[];
  assignee?: string;
  estimatedHours?: number;
  actualHours?: number;
  dependencies?: string[];
  platform: "notion" | "trello" | "asana" | "jira" | "local";
  color?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  color: string;
  tasks: Task[];
  progress: number;
}

export interface TaskView {
  type: "list" | "board" | "calendar";
  filter: {
    status?: string[];
    priority?: string[];
    project?: string[];
    assignee?: string[];
  };
  sort: {
    field: "dueDate" | "priority" | "createdAt" | "title";
    direction: "asc" | "desc";
  };
}

export interface TaskManagementProps {
  onTaskCreate?: (task: Task) => void;
  onTaskUpdate?: (taskId: string, updates: Partial<Task>) => void;
  onTaskDelete?: (taskId: string) => void;
  onProjectCreate?: (project: Project) => void;
  onProjectUpdate?: (projectId: string, updates: Partial<Project>) => void;
  initialTasks?: Task[];
  initialProjects?: Project[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const TaskManagement: React.FC<TaskManagementProps> = ({
  onTaskCreate,
  onTaskUpdate,
  onTaskDelete,
  onProjectCreate,
  onProjectUpdate,
  initialTasks = [],
  initialProjects = [],
  showNavigation = true,
  compactView = false,
}) => {
  const [tasks, setTasks] = useState<Task[]>(initialTasks);
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [view, setView] = useState<TaskView>({
    type: "board",
    filter: {},
    sort: { field: "dueDate", direction: "asc" },
  });
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const {
    isOpen: isTaskModalOpen,
    onOpen: onTaskModalOpen,
    onClose: onTaskModalClose,
  } = useDisclosure();
  const {
    isOpen: isProjectModalOpen,
    onOpen: onProjectModalOpen,
    onClose: onProjectModalClose,
  } = useDisclosure();
  const toast = useToast();

  // Mock data for demonstration
  useEffect(() => {
    const mockTasks: Task[] = [
      {
        id: "1",
        title: "Implement user authentication",
        description: "Set up OAuth flow and user session management",
        dueDate: new Date(2025, 9, 25),
        priority: "high",
        status: "in-progress",
        project: "project-1",
        tags: ["backend", "security"],
        assignee: "user1",
        estimatedHours: 8,
        platform: "local",
        color: "#3182CE",
        createdAt: new Date(2025, 9, 18),
        updatedAt: new Date(2025, 9, 18),
      },
      {
        id: "2",
        title: "Design dashboard UI",
        description: "Create responsive dashboard components",
        dueDate: new Date(2025, 9, 22),
        priority: "medium",
        status: "todo",
        project: "project-1",
        tags: ["frontend", "design"],
        assignee: "user2",
        estimatedHours: 6,
        platform: "local",
        color: "#38A169",
        createdAt: new Date(2025, 9, 18),
        updatedAt: new Date(2025, 9, 18),
      },
      {
        id: "3",
        title: "Write API documentation",
        description: "Document all backend endpoints",
        dueDate: new Date(2025, 9, 28),
        priority: "low",
        status: "todo",
        project: "project-2",
        tags: ["documentation"],
        estimatedHours: 4,
        platform: "local",
        color: "#DD6B20",
        createdAt: new Date(2025, 9, 18),
        updatedAt: new Date(2025, 9, 18),
      },
    ];

    const mockProjects: Project[] = [
      {
        id: "project-1",
        name: "Web Application",
        description: "Main web application development",
        color: "#3182CE",
        tasks: mockTasks.filter((task) => task.project === "project-1"),
        progress: 33,
      },
      {
        id: "project-2",
        name: "Documentation",
        description: "Project documentation and guides",
        color: "#38A169",
        tasks: mockTasks.filter((task) => task.project === "project-2"),
        progress: 0,
      },
    ];

    setTasks(mockTasks);
    setProjects(mockProjects);
    setLoading(false);
  }, []);

  const handleCreateTask = (
    taskData: Omit<Task, "id" | "createdAt" | "updatedAt">,
  ) => {
    const newTask: Task = {
      ...taskData,
      id: Date.now().toString(),
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setTasks((prev) => [...prev, newTask]);
    onTaskCreate?.(newTask);
    toast({
      title: "Task created",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUpdateTask = (taskId: string, updates: Partial<Task>) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === taskId
          ? { ...task, ...updates, updatedAt: new Date() }
          : task,
      ),
    );
    onTaskUpdate?.(taskId, updates);
    toast({
      title: "Task updated",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
    onTaskDelete?.(taskId);
    toast({
      title: "Task deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleCreateProject = (
    projectData: Omit<Project, "id" | "tasks" | "progress">,
  ) => {
    const newProject: Project = {
      ...projectData,
      id: Date.now().toString(),
      tasks: [],
      progress: 0,
    };
    setProjects((prev) => [...prev, newProject]);
    onProjectCreate?.(newProject);
    toast({
      title: "Project created",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "red";
      case "medium":
        return "orange";
      case "low":
        return "green";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "green";
      case "in-progress":
        return "blue";
      case "blocked":
        return "red";
      case "todo":
        return "gray";
      default:
        return "gray";
    }
  };

  const getFilteredTasks = () => {
    let filtered = [...tasks];

    // Apply filters
    if (view.filter.status?.length) {
      filtered = filtered.filter((task) =>
        view.filter.status?.includes(task.status),
      );
    }
    if (view.filter.priority?.length) {
      filtered = filtered.filter((task) =>
        view.filter.priority?.includes(task.priority),
      );
    }
    if (view.filter.project?.length) {
      filtered = filtered.filter((task) =>
        view.filter.project?.includes(task.project || ""),
      );
    }

    // Apply sorting
    filtered.sort((a, b) => {
      const direction = view.sort.direction === "asc" ? 1 : -1;
      switch (view.sort.field) {
        case "dueDate":
          return (a.dueDate.getTime() - b.dueDate.getTime()) * direction;
        case "priority":
          const priorityOrder = { high: 3, medium: 2, low: 1 };
          return (
            (priorityOrder[a.priority] - priorityOrder[b.priority]) * direction
          );
        case "createdAt":
          return (a.createdAt.getTime() - b.createdAt.getTime()) * direction;
        case "title":
          return a.title.localeCompare(b.title) * direction;
        default:
          return 0;
      }
    });

    return filtered;
  };

  const TaskForm: React.FC<{
    task?: Task;
    onSubmit: (data: Omit<Task, "id" | "createdAt" | "updatedAt">) => void;
    onCancel: () => void;
  }> = ({ task, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      title: task?.title || "",
      description: task?.description || "",
      dueDate: task?.dueDate.toISOString().slice(0, 10) || "",
      priority: task?.priority || "medium",
      status: task?.status || "todo",
      project: task?.project || "",
      tags: task?.tags?.join(", ") || "",
      assignee: task?.assignee || "",
      estimatedHours: task?.estimatedHours || 0,
      platform: task?.platform || "local",
      color: task?.color || "#3182CE",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        title: formData.title,
        description: formData.description,
        dueDate: new Date(formData.dueDate),
        priority: formData.priority as "high" | "medium" | "low",
        status: formData.status as
          | "todo"
          | "in-progress"
          | "completed"
          | "blocked",
        project: formData.project || undefined,
        tags: formData.tags
          ? formData.tags.split(",").map((tag) => tag.trim())
          : undefined,
        assignee: formData.assignee || undefined,
        estimatedHours: formData.estimatedHours,
        platform: formData.platform as
          | "notion"
          | "trello"
          | "asana"
          | "jira"
          | "local",
        color: formData.color,
      });
      onCancel();
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Title</FormLabel>
            <Input
              value={formData.title}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, title: e.target.value }))
              }
              placeholder="Task title"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              placeholder="Task description"
            />
          </FormControl>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl isRequired>
              <FormLabel>Due Date</FormLabel>
              <Input
                type="date"
                value={formData.dueDate}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, dueDate: e.target.value }))
                }
              />
            </FormControl>

            <FormControl>
              <FormLabel>Estimated Hours</FormLabel>
              <Input
                type="number"
                value={formData.estimatedHours}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    estimatedHours: parseInt(e.target.value) || 0,
                  }))
                }
                min="0"
              />
            </FormControl>
          </SimpleGrid>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl>
              <FormLabel>Priority</FormLabel>
              <Select
                value={formData.priority}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, priority: e.target.value }))
                }
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Status</FormLabel>
              <Select
                value={formData.status}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, status: e.target.value }))
                }
              >
                <option value="todo">To Do</option>
                <option value="in-progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="blocked">Blocked</option>
              </Select>
            </FormControl>
          </SimpleGrid>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl>
              <FormLabel>Project</FormLabel>
              <Select
                value={formData.project}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, project: e.target.value }))
                }
              >
                <option value="">No Project</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Platform</FormLabel>
              <Select
                value={formData.platform}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, platform: e.target.value }))
                }
              >
                <option value="local">Local</option>
                <option value="notion">Notion</option>
                <option value="trello">Trello</option>
                <option value="asana">Asana</option>
                <option value="jira">Jira</option>
              </Select>
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Tags (comma separated)</FormLabel>
            <Input
              value={formData.tags}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, tags: e.target.value }))
              }
              placeholder="backend, frontend, design"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Assignee</FormLabel>
            <Input
              value={formData.assignee}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, assignee: e.target.value }))
              }
              placeholder="Assignee name"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Color</FormLabel>
            <Input
              type="color"
              value={formData.color}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, color: e.target.value }))
              }
            />
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {task ? "Update Task" : "Create Task"}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  const ProjectForm: React.FC<{
    project?: Project;
    onSubmit: (data: Omit<Project, "id" | "tasks" | "progress">) => void;
    onCancel: () => void;
  }> = ({ project, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      name: project?.name || "",
      description: project?.description || "",
      color: project?.color || "#3182CE",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        name: formData.name,
        description: formData.description,
        color: formData.color,
      });
      onCancel();
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Project Name</FormLabel>
            <Input
              value={formData.name}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, name: e.target.value }))
              }
              placeholder="Project name"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              placeholder="Project description"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Color</FormLabel>
            <Input
              type="color"
              value={formData.color}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, color: e.target.value }))
              }
            />
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {project ? "Update Project" : "Create Project"}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading tasks...</Text>
      </Box>
    );
  }

  const filteredTasks = getFilteredTasks();

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>Task Management</Heading>
            <HStack spacing={2}>
              <Button
                leftIcon={<AddIcon />}
                colorScheme="blue"
                size={compactView ? "sm" : "md"}
                onClick={() => {
                  setSelectedTask(null);
                  onTaskModalOpen();
                }}
              >
                New Task
              </Button>
              <Button
                leftIcon={<AddIcon />}
                colorScheme="green"
                size={compactView ? "sm" : "md"}
                onClick={() => {
                  setSelectedProject(null);
                  onProjectModalOpen();
                }}
              >
                New Project
              </Button>
            </HStack>
          </Flex>
        )}

        {/* View Controls */}
        {showNavigation && (
          <Card size={compactView ? "sm" : "md"}>
            <CardBody>
              <Flex justify="space-between" align="center">
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    variant={view.type === "board" ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "board" }))
                    }
                  >
                    Board
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "list" ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "list" }))
                    }
                  >
                    List
                  </Button>
                </HStack>

                <HStack spacing={2}>
                  <Text fontSize="sm" fontWeight="bold">
                    {filteredTasks.length} tasks
                  </Text>
                </HStack>
              </Flex>
            </CardBody>
          </Card>
        )}

        {/* Projects Overview */}
        {projects.length > 0 && (
          <Card size={compactView ? "sm" : "md"}>
            <CardHeader>
              <Heading size={compactView ? "sm" : "md"}>Projects</Heading>
            </CardHeader>
            <CardBody>
              <SimpleGrid
                columns={Math.min(projects.length, compactView ? 2 : 3)}
                spacing={4}
              >
                {projects.map((project) => (
                  <Box
                    key={project.id}
                    borderWidth="1px"
                    borderRadius="md"
                    p={3}
                    borderLeftWidth="4px"
                    borderLeftColor={project.color}
                    cursor="pointer"
                    onClick={() => {
                      setSelectedProject(project);
                      // TODO: Filter tasks by project
                    }}
                  >
                    <Text
                      fontWeight="bold"
                      fontSize={compactView ? "sm" : "md"}
                    >
                      {project.name}
                    </Text>
                    <Text
                      fontSize={compactView ? "xs" : "sm"}
                      color="gray.600"
                      mb={2}
                    >
                      {project.description}
                    </Text>
                    <Progress
                      value={project.progress}
                      size="sm"
                      colorScheme="blue"
                      mb={2}
                    />
                    <Text fontSize="xs" color="gray.500">
                      {project.tasks.length} tasks • {project.progress}%
                      complete
                    </Text>
                  </Box>
                ))}
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Task Board View */}
        {view.type === "board" && (
          <Card size={compactView ? "sm" : "md"}>
            <CardHeader>
              <Heading size={compactView ? "sm" : "md"}>Task Board</Heading>
            </CardHeader>
            <CardBody>
              <SimpleGrid columns={4} spacing={4}>
                {["todo", "in-progress", "completed", "blocked"].map(
                  (status) => {
                    const statusTasks = filteredTasks.filter(
                      (task) => task.status === status,
                    );
                    return (
                      <Box
                        key={status}
                        borderWidth="1px"
                        borderRadius="md"
                        p={3}
                      >
                        <Text
                          fontWeight="bold"
                          mb={2}
                          fontSize={compactView ? "sm" : "md"}
                        >
                          {status.replace("-", " ").toUpperCase()} (
                          {statusTasks.length})
                        </Text>
                        <VStack spacing={2} align="stretch">
                          {statusTasks.map((task) => (
                            <Box
                              key={task.id}
                              p={2}
                              borderWidth="1px"
                              borderRadius="md"
                              bg="white"
                              cursor="pointer"
                              onClick={() => {
                                setSelectedTask(task);
                                onTaskModalOpen();
                              }}
                            >
                              <Flex
                                justify="space-between"
                                align="start"
                                mb={1}
                              >
                                <Text
                                  fontWeight="bold"
                                  fontSize={compactView ? "xs" : "sm"}
                                  noOfLines={2}
                                >
                                  {task.title}
                                </Text>
                                <Badge
                                  colorScheme={getPriorityColor(task.priority)}
                                  size={compactView ? "xs" : "sm"}
                                >
                                  {task.priority}
                                </Badge>
                              </Flex>
                              {task.description && (
                                <Text
                                  fontSize={compactView ? "2xs" : "xs"}
                                  color="gray.600"
                                  noOfLines={2}
                                  mb={1}
                                >
                                  {task.description}
                                </Text>
                              )}
                              <Flex justify="space-between" align="center">
                                <Text
                                  fontSize={compactView ? "2xs" : "xs"}
                                  color="gray.500"
                                >
                                  {formatDate(task.dueDate)}
                                </Text>
                                <HStack spacing={1}>
                                  {task.assignee && (
                                    <Avatar size="2xs" name={task.assignee} />
                                  )}
                                  <IconButton
                                    aria-label="Complete task"
                                    icon={<CheckCircleIcon />}
                                    size="xs"
                                    colorScheme="green"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleUpdateTask(task.id, {
                                        status: "completed",
                                      });
                                    }}
                                  />
                                </HStack>
                              </Flex>
                            </Box>
                          ))}
                        </VStack>
                      </Box>
                    );
                  },
                )}
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Upcoming Tasks */}
        <Card size={compactView ? "sm" : "md"}>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Upcoming Tasks</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={2} align="stretch">
              {filteredTasks
                .filter(
                  (task) =>
                    task.status !== "completed" && task.dueDate > new Date(),
                )
                .sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime())
                .slice(0, compactView ? 3 : 5)
                .map((task) => (
                  <Flex
                    key={task.id}
                    justify="space-between"
                    align="center"
                    p={2}
                    borderWidth="1px"
                    borderRadius="md"
                    cursor="pointer"
                    onClick={() => {
                      setSelectedTask(task);
                      onTaskModalOpen();
                    }}
                  >
                    <Box>
                      <Text
                        fontWeight="bold"
                        fontSize={compactView ? "sm" : "md"}
                      >
                        {task.title}
                      </Text>
                      <Text
                        fontSize={compactView ? "xs" : "sm"}
                        color="gray.600"
                      >
                        Due {formatDate(task.dueDate)} •{" "}
                        {task.project
                          ? projects.find((p) => p.id === task.project)?.name
                          : "No Project"}
                      </Text>
                    </Box>
                    <HStack>
                      <Badge
                        colorScheme={getStatusColor(task.status)}
                        size={compactView ? "sm" : "md"}
                      >
                        {task.status}
                      </Badge>
                      <IconButton
                        aria-label="Edit task"
                        icon={<EditIcon />}
                        size="xs"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTask(task);
                          onTaskModalOpen();
                        }}
                      />
                      <IconButton
                        aria-label="Delete task"
                        icon={<DeleteIcon />}
                        size="xs"
                        variant="ghost"
                        colorScheme="red"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteTask(task.id);
                        }}
                      />
                    </HStack>
                  </Flex>
                ))}
            </VStack>
          </CardBody>
        </Card>
      </VStack>

      {/* Task Modal */}
      <Modal
        isOpen={isTaskModalOpen}
        onClose={onTaskModalClose}
        size={compactView ? "md" : "lg"}
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedTask ? "Edit Task" : "Create New Task"}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <TaskForm
              task={selectedTask || undefined}
              onSubmit={(data) => {
                if (selectedTask) {
                  handleUpdateTask(selectedTask.id, data);
                } else {
                  handleCreateTask(data);
                }
              }}
              onCancel={onTaskModalClose}
            />
          </ModalBody>
        </ModalContent>
      </Modal>

      {/* Project Modal */}
      <Modal
        isOpen={isProjectModalOpen}
        onClose={onProjectModalClose}
        size={compactView ? "md" : "lg"}
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedProject ? "Edit Project" : "Create New Project"}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <ProjectForm
              project={selectedProject || undefined}
              onSubmit={(data) => {
                if (selectedProject) {
                  // TODO: Implement project update
                } else {
                  handleCreateProject(data);
                }
              }}
              onCancel={onProjectModalClose}
            />
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default TaskManagement;
