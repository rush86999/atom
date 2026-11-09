import { authFetch } from "@/lib/auth-headers";
import React, { useState, useEffect, useCallback } from "react";
import TaskManagement, { Task, Project, normalizeTask, normalizeProject } from "./shared/TaskManagement";
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

        const parsedTasks = tasksData.tasks.map(normalizeTask);

        const parsedProjects = projectsData.projects.map((p: Project) => normalizeProject({
          ...p,
          tasks: parsedTasks.filter((t: Task) => t.project === p.id)
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

  const saveTaskInProjects = (saved: Task) => {
    setProjects(previous => previous.map(project => ({
      ...project,
      tasks: [...project.tasks.filter(task => task.id !== saved.id), ...(project.id === saved.project ? [saved] : [])],
    })));
  };

  const handleCreateTask = async (task: Task): Promise<Task> => {
    const response = await authFetch("/api/v1/tasks", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(task),
    });
    if (!response.ok) throw new Error("Task creation was not confirmed");
    const data = await response.json();
    const saved = normalizeTask(data.task);
    setTasks(previous => [...previous, saved]);
    saveTaskInProjects(saved);
    return saved;
  };

  const handleUpdateTask = async (taskId: string, updates: Partial<Task>): Promise<Task> => {
    const response = await authFetch(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(updates),
    });
    if (!response.ok) throw new Error("Task update was not confirmed");
    const data = await response.json();
    const saved = normalizeTask(data.task);
    if (saved.id !== taskId) throw new Error("Task result does not match the request");
    setTasks(previous => previous.map(task => task.id === taskId ? saved : task));
    saveTaskInProjects(saved);
    return saved;
  };

  const handleDeleteTask = async (taskId: string): Promise<boolean> => {
    const response = await authFetch(`/api/v1/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
    if (!response.ok) throw new Error("Task deletion was not confirmed");
    const data = await response.json();
    if (data.success !== true || data.deleted !== taskId) throw new Error("Task deletion result does not match the request");
    setTasks(previous => previous.filter(task => task.id !== taskId));
    setProjects(previous => previous.map(project => ({ ...project, tasks: project.tasks.filter(task => task.id !== taskId) })));
    return true;
  };

  const handleCreateProject = async (project: Project): Promise<Project> => {
    const response = await authFetch("/api/v1/projects", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project),
    });
    if (!response.ok) throw new Error("Project creation was not confirmed");
    const data = await response.json();
    const saved = normalizeProject(data.project);
    setProjects(previous => [...previous, saved]);
    return saved;
  };

  const handleUpdateProject = async (projectId: string, updates: Partial<Project>): Promise<Project> => {
    const response = await authFetch(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(updates),
    });
    if (!response.ok) throw new Error("Project update was not confirmed");
    const data = await response.json();
    const saved = normalizeProject(data.project);
    if (saved.id !== projectId) throw new Error("Project result does not match the request");
    setProjects(previous => previous.map(project => project.id === projectId ? saved : project));
    return saved;
  };

  return (
    <TaskManagement
      showNavigation={true}
      compactView={false}
      tasks={tasks}
      projects={projects}
      onTaskCreate={handleCreateTask}
      onTaskUpdate={handleUpdateTask}
      onTaskDelete={handleDeleteTask}
      onProjectCreate={handleCreateProject}
      onProjectUpdate={handleUpdateProject}
    />
  );
};

export default TaskManagementWrapper;
