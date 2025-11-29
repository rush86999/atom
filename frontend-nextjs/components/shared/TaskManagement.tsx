import React, { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";
import { Progress } from "@/components/ui/progress";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Plus,
  Clock,
  Edit,
  Trash,
  CheckCircle,
  List,
  LayoutGrid,
  Calendar as CalendarIcon,
} from "lucide-react";

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
  const [isTaskDialogOpen, setIsTaskDialogOpen] = useState(false);
  const [isProjectDialogOpen, setIsProjectDialogOpen] = useState(false);
  const { toast } = useToast();

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
      description: "Your task has been successfully created.",
      duration: 2000,
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
      description: "Your task has been successfully updated.",
      duration: 2000,
    });
  };

  const handleDeleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
    onTaskDelete?.(taskId);
    toast({
      title: "Task deleted",
      description: "Your task has been successfully deleted.",
      duration: 2000,
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
      description: "Your project has been successfully created.",
      duration: 2000,
    });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "destructive";
      case "medium":
        return "default"; // orange equivalent in shadcn usually warning or secondary
      case "low":
        return "secondary";
      default:
        return "outline";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "default"; // green
      case "in-progress":
        return "secondary"; // blue
      case "blocked":
        return "destructive"; // red
      case "todo":
        return "outline"; // gray
      default:
        return "outline";
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
      <form onSubmit={handleSubmit} data-testid="task-form" className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Title</label>
          <Input
            value={formData.title}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, title: e.target.value }))
            }
            placeholder="Task title"
            data-testid="task-title"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Description</label>
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
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Due Date</label>
            <Input
              type="date"
              value={formData.dueDate}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, dueDate: e.target.value }))
              }
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Estimated Hours</label>
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
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Priority</label>
            <Select
              value={formData.priority}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, priority: value }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Status</label>
            <Select
              value={formData.status}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, status: value }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todo">To Do</SelectItem>
                <SelectItem value="in-progress">In Progress</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="blocked">Blocked</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Project</label>
            <Select
              value={formData.project}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, project: value }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="No Project" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="no-project">No Project</SelectItem>
                {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id} data-testid="task-project">
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Platform</label>
            <Select
              value={formData.platform}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, platform: value }))
              }
              data-testid="task-platform"
            >
              <SelectTrigger>
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">Local</SelectItem>
                <SelectItem value="notion">Notion</SelectItem>
                <SelectItem value="trello" data-testid="sync-trello">Trello</SelectItem>
                <SelectItem value="asana" data-testid="sync-asana">Asana</SelectItem>
                <SelectItem value="jira" data-testid="sync-jira">Jira</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Tags (comma separated)</label>
          <Input
            value={formData.tags}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, tags: e.target.value }))
            }
            placeholder="backend, frontend, design"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Assignee</label>
          <Input
            value={formData.assignee}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, assignee: e.target.value }))
            }
            placeholder="Assignee name"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Color</label>
          <Input
            type="color"
            value={formData.color}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, color: e.target.value }))
            }
            className="h-10 w-full"
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit" data-testid="task-submit">
            {task ? "Update Task" : "Create Task"}
          </Button>
        </div>
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
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Project Name</label>
          <Input
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder="Project name"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Description</label>
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
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Color</label>
          <Input
            type="color"
            value={formData.color}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, color: e.target.value }))
            }
            className="h-10 w-full"
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit">
            {project ? "Update Project" : "Create Project"}
          </Button>
        </div>
      </form>
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <Spinner className="h-8 w-8" />
        <p className="mt-4 text-sm text-muted-foreground">Loading tasks...</p>
      </div>
    );
  }

  const filteredTasks = getFilteredTasks();

  return (
    <div className={compactView ? "p-2" : "p-6"}>
      <div className={`flex flex-col gap-${compactView ? "3" : "6"}`}>
        {/* Header */}
        {showNavigation && (
          <div className="flex justify-between items-center">
            <h2 className={`font-bold ${compactView ? "text-xl" : "text-2xl"}`}>Task Management</h2>
            <div className="flex space-x-2">
              <Button
                size={compactView ? "sm" : "default"}
                onClick={() => {
                  setSelectedTask(null);
                  setIsTaskDialogOpen(true);
                }}
                data-testid="new-task-btn"
              >
                <Plus className="mr-2 h-4 w-4" />
                New Task
              </Button>
              <Button
                variant="secondary"
                size={compactView ? "sm" : "default"}
                onClick={() => {
                  setSelectedProject(null);
                  setIsProjectDialogOpen(true);
                }}
              >
                <Plus className="mr-2 h-4 w-4" />
                New Project
              </Button>
            </div>
          </div>
        )}

        {/* View Controls */}
        {showNavigation && (
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div className="flex space-x-2">
                  <Button
                    size="sm"
                    variant={view.type === "board" ? "default" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "board" }))
                    }
                  >
                    <LayoutGrid className="mr-2 h-4 w-4" />
                    Board
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "list" ? "default" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "list" }))
                    }
                  >
                    <List className="mr-2 h-4 w-4" />
                    List
                  </Button>
                </div>

                <div className="flex space-x-2">
                  <span className="text-sm font-bold">
                    {filteredTasks.length} tasks
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Projects Overview */}
        {projects.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Projects</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`grid grid-cols-${Math.min(projects.length, compactView ? 2 : 3)} gap-4`}>
                {projects.map((project) => (
                  <div
                    key={project.id}
                    className="border rounded-md p-3 border-l-4 cursor-pointer hover:bg-accent transition-colors"
                    style={{ borderLeftColor: project.color }}
                    onClick={() => {
                      setSelectedProject(project);
                      // TODO: Filter tasks by project
                    }}
                  >
                    <div className={`font-bold ${compactView ? "text-sm" : "text-base"}`}>
                      {project.name}
                    </div>
                    <div className={`text-muted-foreground mb-2 ${compactView ? "text-xs" : "text-sm"}`}>
                      {project.description}
                    </div>
                    <Progress
                      value={project.progress}
                      className="h-2 mb-2"
                    />
                    <div className="text-xs text-muted-foreground">
                      {project.tasks.length} tasks • {project.progress}%
                      complete
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Task Board View */}
        {view.type === "board" && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Task Board</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-4">
                {["todo", "in-progress", "completed", "blocked"].map(
                  (status) => {
                    const statusTasks = filteredTasks.filter(
                      (task) => task.status === status,
                    );
                    return (
                      <div
                        key={status}
                        className="border rounded-md p-3 bg-muted/20"
                      >
                        <div className={`font-bold mb-2 ${compactView ? "text-sm" : "text-base"}`}>
                          {status.replace("-", " ").toUpperCase()} (
                          {statusTasks.length})
                        </div>
                        <div className="flex flex-col gap-2">
                          {statusTasks.map((task) => (
                            <div
                              key={task.id}
                              className="p-2 border rounded-md bg-background cursor-pointer hover:shadow-sm transition-shadow"
                              onClick={() => {
                                setSelectedTask(task);
                                setIsTaskDialogOpen(true);
                              }}
                            >
                              <div className="flex justify-between items-start mb-1">
                                <div className={`font-bold line-clamp-2 ${compactView ? "text-xs" : "text-sm"}`}>
                                  {task.title}
                                </div>
                                <Badge
                                  variant={getPriorityColor(task.priority) as any}
                                  className={compactView ? "text-[10px] h-4 px-1" : ""}
                                >
                                  {task.priority}
                                </Badge>
                              </div>
                              {task.description && (
                                <div className={`text-muted-foreground line-clamp-2 mb-1 ${compactView ? "text-[10px]" : "text-xs"}`}>
                                  {task.description}
                                </div>
                              )}
                              <div className="flex justify-between items-center">
                                <div className={`text-muted-foreground ${compactView ? "text-[10px]" : "text-xs"}`}>
                                  {formatDate(task.dueDate)}
                                </div>
                                <div className="flex items-center gap-1">
                                  {task.assignee && (
                                    <Avatar className="h-4 w-4">
                                      <AvatarFallback>{task.assignee[0]}</AvatarFallback>
                                    </Avatar>
                                  )}
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 text-green-600 hover:text-green-700 hover:bg-green-100"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleUpdateTask(task.id, {
                                        status: "completed",
                                      });
                                    }}
                                  >
                                    <CheckCircle className="h-3 w-3" />
                                  </Button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Upcoming Tasks */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className={compactView ? "text-lg" : "text-xl"}>Upcoming Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {filteredTasks
                .filter(
                  (task) =>
                    task.status !== "completed" && task.dueDate > new Date(),
                )
                .sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime())
                .slice(0, compactView ? 3 : 5)
                .map((task) => (
                  <div
                    key={task.id}
                    className="flex justify-between items-center p-2 border rounded-md hover:bg-accent cursor-pointer transition-colors"
                    onClick={() => {
                      setSelectedTask(task);
                      setIsTaskDialogOpen(true);
                    }}
                  >
                    <div>
                      <div className={`font-bold ${compactView ? "text-sm" : "text-base"}`}>
                        {task.title}
                      </div>
                      <div className={`text-muted-foreground ${compactView ? "text-xs" : "text-sm"}`}>
                        Due {formatDate(task.dueDate)} •{" "}
                        {task.project
                          ? projects.find((p) => p.id === task.project)?.name
                          : "No Project"}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={getStatusColor(task.status) as any}
                      >
                        {task.status}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTask(task);
                          setIsTaskDialogOpen(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteTask(task.id);
                        }}
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Task Dialog */}
      <Dialog open={isTaskDialogOpen} onOpenChange={setIsTaskDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {selectedTask ? "Edit Task" : "Create New Task"}
            </DialogTitle>
          </DialogHeader>
          <TaskForm
            task={selectedTask || undefined}
            onSubmit={(data) => {
              if (selectedTask) {
                handleUpdateTask(selectedTask.id, data);
              } else {
                handleCreateTask(data);
              }
              setIsTaskDialogOpen(false);
            }}
            onCancel={() => setIsTaskDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Project Dialog */}
      <Dialog open={isProjectDialogOpen} onOpenChange={setIsProjectDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {selectedProject ? "Edit Project" : "Create New Project"}
            </DialogTitle>
          </DialogHeader>
          <ProjectForm
            project={selectedProject || undefined}
            onSubmit={(data) => {
              if (selectedProject) {
                // TODO: Implement project update
              } else {
                handleCreateProject(data);
              }
              setIsProjectDialogOpen(false);
            }}
            onCancel={() => setIsProjectDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TaskManagement;
