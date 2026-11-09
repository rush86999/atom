import { authFetch } from "@/lib/auth-headers";
import React, { useState, useEffect, useCallback } from "react";
import TaskManagement, { Task, Project } from "./shared/TaskManagement";
import { useToast } from "@/components/ui/use-toast";

const TaskManagementWrapper: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const allTasks = async () => {
        const tasks = [];
        const seen = new Set<string>();
        const pageSize = 100;
        // Bound resource use without ever presenting a partial population as complete.
        for (let page = 0; page < 1000; page++) {
          const response = await authFetch(`/api/v1/tasks?limit=${pageSize}&offset=${page * pageSize}`);
          if (!response.ok) throw new Error("Unable to load tasks");
          const payload = await response.json();
          if (!Array.isArray(payload?.tasks) || payload.tasks.length > pageSize) {
            throw new Error("Invalid task collection");
          }
          for (const task of payload.tasks) {
            if (!task || typeof task.id !== "string" || !task.id || seen.has(task.id)) {
              throw new Error("Task collection changed while loading");
            }
            seen.add(task.id);
            tasks.push(task);
          }
          if (payload.tasks.length < pageSize) return { tasks };
        }
        throw new Error("Task collection exceeds this view's loading limit");
      };
      const [tasksData, projectsRes] = await Promise.all([
        allTasks(),
        authFetch("/api/v1/projects")
      ]);

      if (projectsRes.ok) {
        const projectsData = await projectsRes.json();
        if (!Array.isArray(projectsData?.projects)) throw new Error("Invalid project collection");

        const parsedTasks = tasksData.tasks.map((t: any) => ({
          ...t,
          dueDate: new Date(t.dueDate),
          createdAt: new Date(t.createdAt),
          updatedAt: new Date(t.updatedAt),
        }));

        const parsedProjects = projectsData.projects.map((p: any) => ({
          ...p,
          tasks: parsedTasks.filter((t: any) => t.project === p.id)
        }));

        setTasks(parsedTasks);
        setProjects(parsedProjects);
      } else {
        throw new Error("Failed to fetch data");
      }
    } catch (error) {
      console.error("Error fetching task/project data");
      setLoadError("Unable to load tasks and projects. Please try again.");
      toast({
        title: "Error fetching data",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <p className="mt-4 text-sm text-muted-foreground">Loading tasks...</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div role="alert" className="p-6">
        <p>{loadError}</p>
        <button type="button" onClick={() => void fetchData()} className="mt-3 underline">Try again</button>
      </div>
    );
  }

  const handleCreateTask = async (task: Task) => {
    try {
      const response = await authFetch("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(task),
      });

      if (response.ok) {
        const data = await response.json();
        const newTask = {
          ...data.task,
          dueDate: new Date(data.task.dueDate),
          createdAt: new Date(data.task.createdAt),
          updatedAt: new Date(data.task.updatedAt)
        };
        setTasks((prev) => [...prev, newTask]);
        // Update project task list if assigned
        if (newTask.project) {
          setProjects(prev => prev.map(p =>
            p.id === newTask.project
              ? { ...p, tasks: [...p.tasks, newTask] }
              : p
          ));
        }
        toast({ title: "Task created" });
      } else {
        throw new Error("Failed to create task");
      }
    } catch (error) {
      console.error("Error creating task:", error);
      toast({ title: "Failed to create task", variant: "error" });
    }
  };

  const handleUpdateTask = async (taskId: string, updates: Partial<Task>) => {
    try {
      const response = await authFetch(`/api/v1/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        const data = await response.json();
        const updatedTask = {
          ...data.task,
          dueDate: new Date(data.task.dueDate),
          createdAt: new Date(data.task.createdAt),
          updatedAt: new Date(data.task.updatedAt)
        };
        setTasks((prev) => prev.map(t => t.id === taskId ? updatedTask : t));
        toast({ title: "Task updated" });
      } else {
        throw new Error("Failed to update task");
      }
    } catch (error) {
      console.error("Error updating task:", error);
      toast({ title: "Failed to update task", variant: "error" });
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      const response = await authFetch(`/api/v1/tasks/${taskId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setTasks((prev) => prev.filter(t => t.id !== taskId));
        setProjects(prev => prev.map(p => ({
          ...p,
          tasks: p.tasks.filter(t => t.id !== taskId)
        })));
        toast({ title: "Task deleted" });
      } else {
        throw new Error("Failed to delete task");
      }
    } catch (error) {
      console.error("Error deleting task:", error);
      toast({ title: "Failed to delete task", variant: "error" });
    }
  };

  const handleCreateProject = async (project: Project) => {
    try {
      const response = await authFetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project),
      });

      if (response.ok) {
        const data = await response.json();
        const newProject = { ...data.project, tasks: [] };
        setProjects((prev) => [...prev, newProject]);
        toast({ title: "Project created" });
      } else {
        throw new Error("Failed to create project");
      }
    } catch (error) {
      console.error("Error creating project:", error);
      toast({ title: "Failed to create project", variant: "error" });
    }
  };

  const handleUpdateProject = async (projectId: string, updates: Partial<Project>) => {
    try {
      const response = await authFetch(`/api/v1/projects/${projectId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        const data = await response.json();
        setProjects((prev) => prev.map(p => p.id === projectId ? { ...p, ...data.project } : p));
        toast({ title: "Project updated" });
      } else {
        throw new Error("Failed to update project");
      }
    } catch (error) {
      console.error("Error updating project:", error);
      toast({ title: "Failed to update project", variant: "error" });
    }
  };

  return (
    <TaskManagement
      showNavigation={true}
      compactView={false}
      initialTasks={tasks}
      initialProjects={projects}
      onTaskCreate={handleCreateTask}
      onTaskUpdate={handleUpdateTask}
      onTaskDelete={handleDeleteTask}
      onProjectCreate={handleCreateProject}
      onProjectUpdate={handleUpdateProject}
    />
  );
};

export default TaskManagementWrapper;
