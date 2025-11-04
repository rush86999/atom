/**
 * Asana Skills - Project and Task Management Automation
 * Desktop app version following GitLab pattern
 */

import { SkillExecutionContext } from "../types/skillTypes";
import { Logger } from "../utils/Logger";

interface AsanaTask {
  id: string;
  name: string;
  notes?: string;
  due_on?: string;
  assignee?: {
    id: string;
    name: string;
  };
  completed: boolean;
  projects?: Array<{
    id: string;
    name: string;
  }>;
  created_at: string;
  modified_at: string;
}

interface AsanaProject {
  id: string;
  name: string;
  notes?: string;
  color?: string;
  archived: boolean;
  created_at: string;
  modified_at: string;
}

interface AsanaTeam {
  id: string;
  name: string;
  description?: string;
}

interface AsanaUser {
  id: string;
  name: string;
  email?: string;
}

interface AsanaSkillParams {
  action:
    | "get_tasks"
    | "create_task"
    | "update_task"
    | "get_projects"
    | "get_teams"
    | "get_users"
    | "search";
  taskId?: string;
  projectId?: string;
  teamId?: string;
  name?: string;
  description?: string;
  dueDate?: string;
  assigneeId?: string;
  searchQuery?: string;
  limit?: number;
  completed?: boolean;
}

export class AsanaSkills {
  private logger = new Logger("AsanaSkills");

  async execute(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    this.logger.info("Executing Asana Skill", {
      action: params.action,
      params,
    });

    try {
      switch (params.action) {
        case "get_tasks":
          return await this.getTasks(params, context);
        case "create_task":
          return await this.createTask(params, context);
        case "update_task":
          return await this.updateTask(params, context);
        case "get_projects":
          return await this.getProjects(params, context);
        case "get_teams":
          return await this.getTeams(params, context);
        case "get_users":
          return await this.getUsers(params, context);
        case "search":
          return await this.searchAsana(params, context);
        default:
          throw new Error(`Unknown Asana action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error("Asana Skill failed", error);
      throw error;
    }
  }

  private async getTasks(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    const options: any = {
      args: {
        userId: context.userId || "default-user",
        limit: params.limit || 50,
      },
    };

    if (params.projectId) {
      options.args.projectId = params.projectId;
    }

    if (params.completed !== undefined) {
      options.args.completed = params.completed;
    }

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "get_asana_tasks",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.tasks || [],
          total: result.tasks?.length || 0,
        };
      } else {
        throw new Error(result.error || "Failed to get Asana tasks");
      }
    } catch (error) {
      this.logger.error("Failed to get Asana tasks", error);
      throw error;
    }
  }

  private async createTask(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    if (!params.name) {
      throw new Error("Task name is required");
    }

    const taskData = {
      name: params.name,
      notes: params.description,
      due_on: params.dueDate,
      assignee: params.assigneeId,
    };

    const options = {
      args: {
        userId: context.userId || "default-user",
        name: params.name,
        notes: params.description,
        due_on: params.dueDate,
        assignee: params.assigneeId,
        projects: params.projectId ? [params.projectId] : [],
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "create_asana_task",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.task,
          message: `Task "${params.name}" created successfully`,
        };
      } else {
        throw new Error(result.error || "Failed to create Asana task");
      }
    } catch (error) {
      this.logger.error("Failed to create Asana task", error);
      throw error;
    }
  }

  private async updateTask(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    if (!params.taskId) {
      throw new Error("Task ID is required");
    }

    const updates: any = {};
    if (params.name) updates.name = params.name;
    if (params.description) updates.notes = params.description;
    if (params.dueDate) updates.due_on = params.dueDate;
    if (params.assigneeId) updates.assignee = params.assigneeId;
    if (params.completed !== undefined) updates.completed = params.completed;

    const options = {
      args: {
        userId: context.userId || "default-user",
        taskId: params.taskId,
        ...updates,
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "update_asana_task",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.task,
          message: `Task updated successfully`,
        };
      } else {
        throw new Error(result.error || "Failed to update Asana task");
      }
    } catch (error) {
      this.logger.error("Failed to update Asana task", error);
      throw error;
    }
  }

  private async getProjects(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    const options = {
      args: {
        userId: context.userId || "default-user",
        limit: params.limit || 50,
        teamId: params.teamId,
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "get_asana_projects",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.projects || [],
          total: result.projects?.length || 0,
        };
      } else {
        throw new Error(result.error || "Failed to get Asana projects");
      }
    } catch (error) {
      this.logger.error("Failed to get Asana projects", error);
      throw error;
    }
  }

  private async getTeams(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    const options = {
      args: {
        userId: context.userId || "default-user",
        limit: params.limit || 50,
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "get_asana_teams",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.teams || [],
          total: result.teams?.length || 0,
        };
      } else {
        throw new Error(result.error || "Failed to get Asana teams");
      }
    } catch (error) {
      this.logger.error("Failed to get Asana teams", error);
      throw error;
    }
  }

  private async getUsers(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    const options = {
      args: {
        userId: context.userId || "default-user",
        limit: params.limit || 50,
        teamId: params.teamId,
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "get_asana_users",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.users || [],
          total: result.users?.length || 0,
        };
      } else {
        throw new Error(result.error || "Failed to get Asana users");
      }
    } catch (error) {
      this.logger.error("Failed to get Asana users", error);
      throw error;
    }
  }

  private async searchAsana(
    params: AsanaSkillParams,
    context: SkillExecutionContext,
  ): Promise<any> {
    if (!params.searchQuery) {
      throw new Error("Search query is required");
    }

    const options = {
      args: {
        userId: context.userId || "default-user",
        query: params.searchQuery,
        limit: params.limit || 50,
      },
    };

    try {
      const result = await (window as any).__TAURI_INVOKE__(
        "search_asana",
        options,
      );

      if (result.success) {
        return {
          success: true,
          data: result.results || [],
          total: result.results?.length || 0,
        };
      } else {
        throw new Error(result.error || "Failed to search Asana");
      }
    } catch (error) {
      this.logger.error("Failed to search Asana", error);
      throw error;
    }
  }
}

// Export skill instance
export const asanaSkills = new AsanaSkills();

// Export types for external use
export type { AsanaSkillParams, AsanaTask, AsanaProject, AsanaTeam, AsanaUser };
