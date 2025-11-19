import React, { useState, useEffect } from "react";
import TaskManagement, { Task, Project } from "./shared/TaskManagement";
import { useToast } from "@chakra-ui/react";

const TaskManagementWrapper: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const fetchData = async () => {
    try {
      const [tasksRes, projectsRes] = await Promise.all([
        fetch("/api/v1/tasks"),
        fetch("/api/v1/projects")
      ]);

      if (tasksRes.ok && projectsRes.ok) {
        const tasksData = await tasksRes.json();
        const projectsData = await projectsRes.json();

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
      console.error("Error fetching data:", error);
      toast({
        title: "Error fetching data",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateTask = async (task: Task) => {
    try {
      const response = await fetch("/api/v1/tasks", {
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
        toast({ title: "Task created", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to create task");
      }
    } catch (error) {
      console.error("Error creating task:", error);
      toast({ title: "Failed to create task", status: "error", duration: 3000 });
    }
  };

  const handleUpdateTask = async (taskId: string, updates: Partial<Task>) => {
    try {
      const response = await fetch(`/api/v1/tasks/${taskId}`, {
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
        toast({ title: "Task updated", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to update task");
      }
    } catch (error) {
      console.error("Error updating task:", error);
      toast({ title: "Failed to update task", status: "error", duration: 3000 });
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/v1/tasks/${taskId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setTasks((prev) => prev.filter(t => t.id !== taskId));
        setProjects(prev => prev.map(p => ({
          ...p,
          tasks: p.tasks.filter(t => t.id !== taskId)
        })));
        toast({ title: "Task deleted", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to delete task");
      }
    } catch (error) {
      console.error("Error deleting task:", error);
      toast({ title: "Failed to delete task", status: "error", duration: 3000 });
    }
  };

  const handleCreateProject = async (project: Project) => {
    try {
      const response = await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project),
      });

      if (response.ok) {
        const data = await response.json();
        const newProject = { ...data.project, tasks: [] };
        setProjects((prev) => [...prev, newProject]);
        toast({ title: "Project created", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to create project");
      }
    } catch (error) {
      console.error("Error creating project:", error);
      toast({ title: "Failed to create project", status: "error", duration: 3000 });
    }
  };

  const handleUpdateProject = async (projectId: string, updates: Partial<Project>) => {
    try {
      const response = await fetch(`/api/v1/projects/${projectId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        const data = await response.json();
        setProjects((prev) => prev.map(p => p.id === projectId ? { ...p, ...data.project } : p));
        toast({ title: "Project updated", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to update project");
      }
    } catch (error) {
      console.error("Error updating project:", error);
      toast({ title: "Failed to update project", status: "error", duration: 3000 });
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
