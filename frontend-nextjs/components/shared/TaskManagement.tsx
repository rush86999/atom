import React, { useState, useEffect, useRef } from "react";
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
  dueDate: Date | null;
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

type TaskCreateData = Omit<Task, "id" | "createdAt" | "updatedAt">;
type ProjectCreateData = Omit<Project, "id" | "tasks" | "progress">;

type TaskMutationResult = Task | void;
type ProjectMutationResult = Project | void;

export interface TaskManagementProps {
  /**
   * Controlled task collection. When supplied, `initialTasks` is ignored and
   * this prop is the source of truth. The parent publishes confirmed server
   * results; no local mirror can replace the controlled collection.
   */
  tasks?: Task[];
  /**
   * Controlled project collection. When supplied, `initialProjects` is
   * ignored and this prop is the source of truth.
   */
  projects?: Project[];
  onTaskCreate?: (
    task: Task,
  ) => TaskMutationResult | Promise<TaskMutationResult>;
  onTaskUpdate?: (
    taskId: string,
    updates: Partial<Task>,
  ) => TaskMutationResult | Promise<TaskMutationResult>;
  onTaskDelete?: (
    taskId: string,
  ) => boolean | void | Promise<boolean | void>;
  onProjectCreate?: (
    project: Project,
  ) => ProjectMutationResult | Promise<ProjectMutationResult>;
  onProjectUpdate?: (
    projectId: string,
    updates: Partial<Project>,
  ) => ProjectMutationResult | Promise<ProjectMutationResult>;
  initialTasks?: Task[];
  initialProjects?: Project[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const isPromiseLike = (value: unknown): value is PromiseLike<unknown> =>
  value !== null &&
  (typeof value === "object" || typeof value === "function") &&
  "then" in value &&
  typeof value.then === "function";

const isTaskConfirmation = (value: unknown): value is Task =>
  typeof value === "object" &&
  value !== null &&
  "id" in value &&
  typeof value.id === "string" &&
  value.id.length > 0 &&
  "title" in value &&
  typeof value.title === "string";

const isProjectConfirmation = (value: unknown): value is Project =>
  typeof value === "object" &&
  value !== null &&
  "id" in value &&
  typeof value.id === "string" &&
  value.id.length > 0 &&
  "name" in value &&
  typeof value.name === "string";

const normalizeDate = (value: unknown, fallback?: Date): Date | null => {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? fallback ?? null : value;
  }
  if (typeof value === "string" || typeof value === "number") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? fallback ?? null : parsed;
  }
  return fallback ?? null;
};

export const normalizeTask = (task: Task): Task => {
  const createdAt = normalizeDate(task.createdAt);
  const updatedAt = normalizeDate(task.updatedAt);
  const dueDate = task.dueDate == null ? null : normalizeDate(task.dueDate);
  if (!isTaskConfirmation(task) || !createdAt || !updatedAt || (task.dueDate != null && !dueDate)) {
    throw new Error("Task result is incomplete");
  }
  return { ...task, dueDate, createdAt, updatedAt };
};

export const normalizeProject = (project: Project): Project => {
  if (!isProjectConfirmation(project) || !Array.isArray(project.tasks) ||
      !Number.isFinite(project.progress) || project.progress < 0 || project.progress > 100) {
    throw new Error("Project result is incomplete");
  }
  return { ...project, tasks: project.tasks.map(normalizeTask) };
};

const toDateInputValue = (value: unknown): string => {
  const date = normalizeDate(value);
  return date ? date.toISOString().slice(0, 10) : "";
};

interface TaskFormState {
  title: string;
  description: string;
  dueDate: string;
  priority: Task["priority"];
  status: Task["status"];
  project: string;
  tags: string;
  assignee: string;
  estimatedHours: number;
  platform: Task["platform"];
  color: string;
}

const buildTaskFormState = (task?: Task): TaskFormState => ({
  title: task?.title || "",
  description: task?.description || "",
  dueDate: toDateInputValue(task?.dueDate),
  priority: task?.priority || "medium",
  status: task?.status || "todo",
  project: task?.project || "",
  tags: task?.tags?.join(", ") || "",
  assignee: task?.assignee || "",
  estimatedHours: task?.estimatedHours || 0,
  platform: task?.platform || "local",
  color: task?.color || "#3182CE",
});

interface TaskFormProps {
  task?: Task;
  projects: Project[];
  onSubmit: (data: TaskCreateData) => Promise<boolean>;
  onCancel: () => void;
  pending?: boolean;
}

const TaskForm: React.FC<TaskFormProps> = ({
  task,
  projects,
  onSubmit,
  onCancel,
  pending = false,
}) => {
  const editedTaskId = useRef(task?.id);
  const [formData, setFormData] = useState<TaskFormState>(() =>
    buildTaskFormState(task),
  );

  // Only an actual change of edited record identity resets the draft. An
  // unrelated parent render (new callback props, project list, pending state,
  // etc.) must not discard what the user has typed.
  useEffect(() => {
    if (editedTaskId.current !== task?.id) {
      editedTaskId.current = task?.id;
      setFormData(buildTaskFormState(task));
    }
  }, [task]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pending) return;

    try {
      const saved = await onSubmit({
        title: formData.title,
        description: formData.description,
        dueDate: formData.dueDate ? new Date(formData.dueDate) : null,
        priority: formData.priority,
        status: formData.status,
        project:
          formData.project && formData.project !== "no-project"
            ? formData.project
            : undefined,
        tags: formData.tags
          ? formData.tags.split(",").map((tag) => tag.trim())
          : undefined,
        assignee: formData.assignee || undefined,
        estimatedHours: formData.estimatedHours,
        platform: formData.platform,
        color: formData.color,
      });
      if (saved) onCancel();
    } catch {
      // The parent reports the failure; keeping the form mounted preserves
      // the draft so the user can retry or correct it.
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="task-form"
      className="space-y-4"
      aria-busy={pending}
    >
      <fieldset
        disabled={pending}
        className="m-0 min-w-0 space-y-4 border-0 p-0"
      >
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
                setFormData((prev) => ({
                  ...prev,
                  priority: value as "high" | "medium" | "low",
                }))
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
                setFormData((prev) => ({
                  ...prev,
                  status: value as
                    | "todo"
                    | "in-progress"
                    | "completed"
                    | "blocked",
                }))
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
                  <SelectItem
                    key={project.id}
                    value={project.id}
                    data-testid="task-project"
                  >
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
                setFormData((prev) => ({
                  ...prev,
                  platform: value as
                    | "local"
                    | "notion"
                    | "trello"
                    | "asana"
                    | "jira",
                }))
              }
              data-testid="task-platform"
            >
              <SelectTrigger>
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">Local</SelectItem>
                <SelectItem value="notion">Notion</SelectItem>
                <SelectItem value="trello" data-testid="sync-trello">
                  Trello
                </SelectItem>
                <SelectItem value="asana" data-testid="sync-asana">
                  Asana
                </SelectItem>
                <SelectItem value="jira" data-testid="sync-jira">
                  Jira
                </SelectItem>
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

        <div className="flex items-center justify-end space-x-3 pt-4">
          {pending && (
            <p
              role="status"
              data-testid="task-form-pending"
              className="mr-auto text-sm text-muted-foreground"
            >
              Saving task...
            </p>
          )}
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit" data-testid="task-submit">
            {pending ? "Saving..." : task ? "Update Task" : "Create Task"}
          </Button>
        </div>
      </fieldset>
    </form>
  );
};

interface ProjectFormState {
  name: string;
  description: string;
  color: string;
}

const buildProjectFormState = (project?: Project): ProjectFormState => ({
  name: project?.name || "",
  description: project?.description || "",
  color: project?.color || "#3182CE",
});

interface ProjectFormProps {
  project?: Project;
  onSubmit: (data: ProjectCreateData) => Promise<boolean>;
  onCancel: () => void;
  pending?: boolean;
}

const ProjectForm: React.FC<ProjectFormProps> = ({
  project,
  onSubmit,
  onCancel,
  pending = false,
}) => {
  const editedProjectId = useRef(project?.id);
  const [formData, setFormData] = useState<ProjectFormState>(() =>
    buildProjectFormState(project),
  );

  useEffect(() => {
    if (editedProjectId.current !== project?.id) {
      editedProjectId.current = project?.id;
      setFormData(buildProjectFormState(project));
    }
  }, [project]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pending) return;

    try {
      const saved = await onSubmit({
        name: formData.name,
        description: formData.description,
        color: formData.color,
      });
      if (saved) onCancel();
    } catch {
      // Keep the draft open when persistence was not confirmed.
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4"
      aria-busy={pending}
    >
      <fieldset
        disabled={pending}
        className="m-0 min-w-0 space-y-4 border-0 p-0"
      >
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

        <div className="flex items-center justify-end space-x-3 pt-4">
          {pending && (
            <p
              role="status"
              data-testid="project-form-pending"
              className="mr-auto text-sm text-muted-foreground"
            >
              Saving project...
            </p>
          )}
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit">
            {pending
              ? "Saving..."
              : project
                ? "Update Project"
                : "Create Project"}
          </Button>
        </div>
      </fieldset>
    </form>
  );
};

const TaskManagement: React.FC<TaskManagementProps> = ({
  onTaskCreate,
  onTaskUpdate,
  onTaskDelete,
  onProjectCreate,
  onProjectUpdate,
  tasks: controlledTasks,
  projects: controlledProjects,
  initialTasks = [],
  initialProjects = [],
  showNavigation = true,
  compactView = false,
}) => {
  const taskIsControlled = controlledTasks !== undefined;
  const projectIsControlled = controlledProjects !== undefined;

  const [localTasks, setLocalTasks] = useState<Task[]>(initialTasks);
  const [localProjects, setLocalProjects] = useState<Project[]>(initialProjects);
  const tasks = controlledTasks ?? localTasks;
  const projects = controlledProjects ?? localProjects;
  const setTasks: React.Dispatch<React.SetStateAction<Task[]>> = next => {
    if (!taskIsControlled) setLocalTasks(next);
  };
  const setProjects: React.Dispatch<React.SetStateAction<Project[]>> = next => {
    if (!projectIsControlled) setLocalProjects(next);
  };
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
  const [isMutating, setIsMutating] = useState(false);
  const mutationInFlight = useRef(false);
  const { toast } = useToast();

  // Controlled collections render directly from parent state; no shadow cache.
  const beginMutation = () => {
    if (mutationInFlight.current) return false;
    mutationInFlight.current = true;
    setIsMutating(true);
    return true;
  };

  const endMutation = () => {
    mutationInFlight.current = false;
    setIsMutating(false);
  };

  const showMutationFailure = (title: string) => {
    toast({ title, variant: "error", duration: 3000 });
  };

  const upsertTaskInProjects = (task: Task) => {
    setProjects((prev) =>
      prev.map((project) => {
        const remaining = project.tasks.filter((item) => item.id !== task.id);
        if (project.id === task.project) {
          return { ...project, tasks: [...remaining, task] };
        }
        return remaining.length === project.tasks.length
          ? project
          : { ...project, tasks: remaining };
      }),
    );
  };

  const handleCreateTask = async (
    taskData: TaskCreateData,
  ): Promise<boolean> => {
    if (!beginMutation()) return false;
    try {
      if (!onTaskCreate && taskIsControlled) {
        showMutationFailure("Failed to create task");
        return false;
      }

      const newTask: Task = {
        ...taskData,
        id: Date.now().toString(),
        createdAt: new Date(),
        updatedAt: new Date(),
      };
      const rawResult = onTaskCreate?.(newTask);
      const asyncResult = isPromiseLike(rawResult);
      const result: unknown = asyncResult ? await rawResult : rawResult;

      if (isTaskConfirmation(result)) {
        const confirmed = normalizeTask(result);
        setTasks((prev) => [...prev, confirmed]);
        upsertTaskInProjects(confirmed);
      } else if (
        !taskIsControlled &&
        !asyncResult &&
        result === undefined
      ) {
        // Legacy standalone behavior: a synchronous void callback is an
        // accepted local save, so a local record can be synthesized.
        setTasks((prev) => [...prev, newTask]);
        upsertTaskInProjects(newTask);
      } else {
        // Pending/rejected/unconfirmed saves never create a visible record.
        showMutationFailure("Failed to create task");
        return false;
      }

      toast({
        title: "Task created",
        description: "Your task has been successfully created.",
        duration: 2000,
      });
      return true;
    } catch {
      showMutationFailure("Failed to create task");
      return false;
    } finally {
      endMutation();
    }
  };

  const handleUpdateTask = async (
    taskId: string,
    updates: Partial<Task>,
  ): Promise<boolean> => {
    if (!beginMutation()) return false;
    try {
      if (!onTaskUpdate && taskIsControlled) {
        showMutationFailure("Failed to update task");
        return false;
      }

      const rawResult = onTaskUpdate?.(taskId, updates);
      const asyncResult = isPromiseLike(rawResult);
      const result: unknown = asyncResult ? await rawResult : rawResult;

      if (isTaskConfirmation(result) && result.id === taskId) {
        const confirmed = normalizeTask(result);
        setTasks((prev) =>
          prev.map((task) => (task.id === taskId ? confirmed : task)),
        );
        upsertTaskInProjects(confirmed);
      } else if (
        !taskIsControlled &&
        !asyncResult &&
        result === undefined
      ) {
        const current = tasks.find((task) => task.id === taskId);
        if (current) {
          const updated = {
            ...current,
            ...updates,
            updatedAt: new Date(),
          };
          setTasks((prev) =>
            prev.map((task) => (task.id === taskId ? updated : task)),
          );
          upsertTaskInProjects(updated);
        }
      } else {
        showMutationFailure("Failed to update task");
        return false;
      }

      toast({
        title: "Task updated",
        description: "Your task has been successfully updated.",
        duration: 2000,
      });
      return true;
    } catch {
      showMutationFailure("Failed to update task");
      return false;
    } finally {
      endMutation();
    }
  };

  const handleDeleteTask = async (taskId: string): Promise<boolean> => {
    if (!beginMutation()) return false;
    try {
      if (!onTaskDelete && taskIsControlled) {
        showMutationFailure("Failed to delete task");
        return false;
      }

      const rawResult = onTaskDelete?.(taskId);
      const asyncResult = isPromiseLike(rawResult);
      const result: unknown = asyncResult ? await rawResult : rawResult;
      const confirmed =
        result === true ||
        (!taskIsControlled && !asyncResult && result === undefined);

      if (!confirmed) {
        // A refused or unconfirmed delete must leave the row in place.
        showMutationFailure("Failed to delete task");
        return false;
      }

      setTasks((prev) => prev.filter((task) => task.id !== taskId));
      setProjects((prev) =>
        prev.map((project) => ({
          ...project,
          tasks: project.tasks.filter((task) => task.id !== taskId),
        })),
      );
      toast({
        title: "Task deleted",
        description: "Your task has been successfully deleted.",
        duration: 2000,
      });
      return true;
    } catch {
      showMutationFailure("Failed to delete task");
      return false;
    } finally {
      endMutation();
    }
  };

  const handleCreateProject = async (
    projectData: ProjectCreateData,
  ): Promise<boolean> => {
    if (!beginMutation()) return false;
    try {
      if (!onProjectCreate && projectIsControlled) {
        showMutationFailure("Failed to create project");
        return false;
      }

      const newProject: Project = {
        ...projectData,
        id: Date.now().toString(),
        tasks: [],
        progress: 0,
      };
      const rawResult = onProjectCreate?.(newProject);
      const asyncResult = isPromiseLike(rawResult);
      const result: unknown = asyncResult ? await rawResult : rawResult;

      if (isProjectConfirmation(result)) {
        setProjects((prev) => [...prev, normalizeProject(result)]);
      } else if (
        !projectIsControlled &&
        !asyncResult &&
        result === undefined
      ) {
        setProjects((prev) => [...prev, newProject]);
      } else {
        showMutationFailure("Failed to create project");
        return false;
      }

      toast({
        title: "Project created",
        description: "Your project has been successfully created.",
        duration: 2000,
      });
      return true;
    } catch {
      showMutationFailure("Failed to create project");
      return false;
    } finally {
      endMutation();
    }
  };

  const handleUpdateProject = async (
    projectId: string,
    updates: Partial<Project>,
  ): Promise<boolean> => {
    if (!beginMutation()) return false;
    try {
      if (!onProjectUpdate && projectIsControlled) {
        showMutationFailure("Failed to update project");
        return false;
      }

      const rawResult = onProjectUpdate?.(projectId, updates);
      const asyncResult = isPromiseLike(rawResult);
      const result: unknown = asyncResult ? await rawResult : rawResult;

      if (isProjectConfirmation(result) && result.id === projectId) {
        const confirmed = normalizeProject(result);
        setProjects((prev) =>
          prev.map((project) => {
            if (project.id !== projectId) return project;
            return {
              ...project,
              ...confirmed,
              tasks: Array.isArray(result.tasks)
                ? confirmed.tasks
                : project.tasks,
              progress:
                typeof result.progress === "number"
                  ? confirmed.progress
                  : project.progress,
            };
          }),
        );
      } else if (
        !projectIsControlled &&
        !asyncResult &&
        result === undefined
      ) {
        setProjects((prev) =>
          prev.map((project) =>
            project.id === projectId
              ? { ...project, ...updates }
              : project,
          ),
        );
      } else {
        showMutationFailure("Failed to update project");
        return false;
      }

      toast({
        title: "Project updated",
        description: "Your project has been successfully updated.",
        duration: 2000,
      });
      return true;
    } catch {
      showMutationFailure("Failed to update project");
      return false;
    } finally {
      endMutation();
    }
  };

  const closeTaskDialog = () => {
    setIsTaskDialogOpen(false);
    setSelectedTask(null);
  };

  const closeProjectDialog = () => {
    setIsProjectDialogOpen(false);
    setSelectedProject(null);
  };

  const handleTaskDialogOpenChange = (open: boolean) => {
    if (!open && mutationInFlight.current) return;
    setIsTaskDialogOpen(open);
    if (!open) setSelectedTask(null);
  };

  const handleProjectDialogOpenChange = (open: boolean) => {
    if (!open && mutationInFlight.current) return;
    setIsProjectDialogOpen(open);
    if (!open) setSelectedProject(null);
  };

  const formatDate = (date: Date | null) => {
    if (!date) return "No due date";
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
          if (!a.dueDate) return b.dueDate ? 1 : 0;
          if (!b.dueDate) return -1;
          return ((a.dueDate?.getTime() ?? Infinity) - (b.dueDate?.getTime() ?? Infinity)) * direction;
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
        {isMutating && (
          <div
            role="status"
            aria-live="polite"
            data-testid="task-management-pending"
            className="text-sm text-muted-foreground"
          >
            Saving changes...
          </div>
        )}
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
                disabled={isMutating}
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
                disabled={isMutating}
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
                  <Select
                    value={view.filter.status?.[0] || "all"}
                    onValueChange={(value) =>
                      setView((prev) => ({
                        ...prev,
                        filter:
                          value === "all"
                            ? { ...prev.filter, status: undefined }
                            : { ...prev.filter, status: [value] },
                      }))
                    }
                  >
                    <SelectTrigger data-testid="status-filter" className="w-[130px]">
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="todo">To Do</SelectItem>
                      <SelectItem value="in-progress">In Progress</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="blocked">Blocked</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={view.filter.priority?.[0] || "all"}
                    onValueChange={(value) =>
                      setView((prev) => ({
                        ...prev,
                        filter:
                          value === "all"
                            ? { ...prev.filter, priority: undefined }
                            : { ...prev.filter, priority: [value] },
                      }))
                    }
                  >
                    <SelectTrigger data-testid="priority-filter" className="w-[120px]">
                      <SelectValue placeholder="All priorities" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All priorities</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={`${view.sort.field}-${view.sort.direction}`}
                    onValueChange={(value) => {
                      const [field, direction] = value.split("-") as [
                        typeof view.sort.field,
                        "asc" | "desc",
                      ];
                      setView((prev) => ({
                        ...prev,
                        sort: { field, direction },
                      }));
                    }}
                  >
                    <SelectTrigger data-testid="sort-select" className="w-[150px]">
                      <SelectValue placeholder="Sort by" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="dueDate-asc">Due date ↑</SelectItem>
                      <SelectItem value="dueDate-desc">Due date ↓</SelectItem>
                      <SelectItem value="priority-desc">Priority ↓</SelectItem>
                      <SelectItem value="priority-asc">Priority ↑</SelectItem>
                      <SelectItem value="title-asc">Title A-Z</SelectItem>
                      <SelectItem value="title-desc">Title Z-A</SelectItem>
                      <SelectItem value="createdAt-asc">Oldest first</SelectItem>
                      <SelectItem value="createdAt-desc">Newest first</SelectItem>
                    </SelectContent>
                  </Select>
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
                      setIsProjectDialogOpen(true);
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
                                      void handleUpdateTask(task.id, {
                                        status: "completed",
                                      });
                                    }}
                                    disabled={isMutating}
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

        {/* Task List View */}
        {view.type === "list" && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Task List</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-2">
                {filteredTasks.map((task) => (
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
                        {task.dueDate ? "Due " : ""}{formatDate(task.dueDate)} •{" "}
                        {task.project
                          ? projects.find((p) => p.id === task.project)?.name
                          : "No Project"}
                      </div>
                    </div>
                    <Badge variant={getStatusColor(task.status) as any}>
                      {task.status}
                    </Badge>
                  </div>
                ))}
                {filteredTasks.length === 0 && (
                  <p className="text-muted-foreground text-sm py-4 text-center">
                    No tasks match the current filters.
                  </p>
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
                    task.status !== "completed" && task.dueDate !== null && task.dueDate > new Date(),
                )
                .sort((a, b) => (a.dueDate?.getTime() ?? Infinity) - (b.dueDate?.getTime() ?? Infinity))
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
                        {task.dueDate ? "Due " : ""}{formatDate(task.dueDate)} •{" "}
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
                          void handleDeleteTask(task.id);
                        }}
                        disabled={isMutating}
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
      <Dialog
        open={isTaskDialogOpen}
        onOpenChange={handleTaskDialogOpenChange}
      >
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {selectedTask ? "Edit Task" : "Create New Task"}
            </DialogTitle>
          </DialogHeader>
          <TaskForm
            key={selectedTask?.id ?? "new-task"}
            task={selectedTask || undefined}
            projects={projects}
            pending={isMutating}
            onSubmit={(data) => {
              if (selectedTask) {
                return handleUpdateTask(selectedTask.id, data);
              }
              return handleCreateTask(data);
            }}
            onCancel={closeTaskDialog}
          />
        </DialogContent>
      </Dialog>

      {/* Project Dialog */}
      <Dialog
        open={isProjectDialogOpen}
        onOpenChange={handleProjectDialogOpenChange}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {selectedProject ? "Edit Project" : "Create New Project"}
            </DialogTitle>
          </DialogHeader>
          <ProjectForm
            key={selectedProject?.id ?? "new-project"}
            project={selectedProject || undefined}
            pending={isMutating}
            onSubmit={(data) => {
              if (selectedProject) {
                return handleUpdateProject(selectedProject.id, data);
              }
              return handleCreateProject(data);
            }}
            onCancel={closeProjectDialog}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TaskManagement;
