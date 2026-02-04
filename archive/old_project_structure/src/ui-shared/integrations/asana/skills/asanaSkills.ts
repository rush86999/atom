import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Asana Enhanced Skills
 * Complete Asana task management and project coordination system
 */

// Task Management Skills
export class AsanaCreateTaskSkill implements Skill {
  id = 'asana_create_task';
  name = 'Create Asana Task';
  description = 'Create a new task in Asana';
  category = 'productivity';
  examples = [
    'Create Asana task for project proposal',
    'Add task to complete code review',
    'Create task in Asana for meeting notes due tomorrow'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract task details
      const taskName = this.extractTaskName(intent) ||
                     entities.find((e: any) => e.type === 'task_name')?.value ||
                     'New Task';
      
      const projectName = this.extractProjectName(intent) ||
                        entities.find((e: any) => e.type === 'project_name')?.value;
      
      const assignee = this.extractAssignee(intent) ||
                     entities.find((e: any) => e.type === 'assignee')?.value;
      
      const dueDate = this.extractDueDate(intent) ||
                    entities.find((e: any) => e.type === 'due_date')?.value;
      
      const description = this.extractDescription(intent) ||
                       entities.find((e: any) => e.type === 'description')?.value ||
                       intent;

      if (!taskName) {
        return {
          success: false,
          message: 'Task name is required',
          error: 'Missing task name'
        };
      }

      // Call Asana API
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: taskName,
            notes: description,
            projects: projectName ? [{ name: projectName }] : [],
            assignee: assignee || 'me',
            due_at: dueDate,
            priority: 'medium'
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Asana task "${taskName}" created successfully`,
          data: {
            task: result.data.task,
            url: result.data.url,
            name: taskName,
            project: projectName
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Asana',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Asana task: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Asana task: ${error}`,
        error: error as any
      };
    }
  }

  private extractTaskName(intent: string): string | null {
    const patterns = [
      /create (?:asana )?task (?:for|to) (.+?)(?: in|due|:|$)/i,
      /add task (?:for|to) (.+?)(?: in|due|:|$)/i,
      /task (.+?)(?: in|due|:|$)/i,
      /(?:for|to) (.+?)(?: in|due|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (.+?)(?: due|:|$)/i,
      /project (.+?)(?: due|:|$)/i,
      /for project (.+?)(?: due|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractAssignee(intent: string): string | null {
    const patterns = [
      /assign to (.+?)(?: in|due|:|$)/i,
      /assigned to (.+?)(?: in|due|:|$)/i,
      /for (.+?)(?: in|due|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDueDate(intent: string): string | null {
    const patterns = [
      /due (.+?)(?: in|:|$)/i,
      /deadline (.+?)(?: in|:|$)/i,
      /by (.+?)(?: in|:|$)/i,
      /tomorrow/i,
      /today/i,
      /next week/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        const dateStr = match[1]?.trim() || match[0];
        return dateStr;
      }
    }

    return null;
  }

  private extractDescription(intent: string): string {
    // The description is typically the entire intent after extracting key information
    return intent;
  }
}

export class AsanaSearchTasksSkill implements Skill {
  id = 'asana_search_tasks';
  name = 'Search Asana Tasks';
  description = 'Search tasks in Asana';
  category = 'productivity';
  examples = [
    'Search Asana for tasks related to project proposal',
    'Find Asana tasks assigned to John',
    'Search for completed tasks in project X'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const projectName = this.extractProjectName(intent) ||
                        entities.find((e: any) => e.type === 'project_name')?.value;
      
      const assignee = this.extractAssignee(intent) ||
                     entities.find((e: any) => e.type === 'assignee')?.value;
      
      const completed = this.extractCompletedStatus(intent) ||
                       entities.find((e: any) => e.type === 'completed')?.value ||
                       'not_completed';
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Asana API
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          project_id: projectName,
          assignee: assignee,
          completed: completed,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const tasks = result.data.tasks || [];
        const taskCount = tasks.length;

        return {
          success: true,
          message: `Found ${taskCount} Asana task${taskCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            tasks: tasks,
            total_count: result.data.total_count,
            query: query,
            project: projectName,
            assignee: assignee
          },
          actions: tasks.map((task: any) => ({
            type: 'open_url',
            label: `View ${task.name}`,
            url: task.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Asana tasks: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Asana tasks: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:asana )?tasks? (?:for|related to) (.+)/i,
      /find (?:asana )?tasks? (?:for|about) (.+)/i,
      /tasks? (?:for|about) (.+)/i,
      /(.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (.+?)(?: project|assigned|due)/i,
      /project (.+?)(?: assigned|due)/i,
      /for project (.+?)(?: assigned|due)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractAssignee(intent: string): string | null {
    const patterns = [
      /assigned to (.+?)(?: in|project)/i,
      /for (.+?)(?: in|project)/i,
      /by (.+?)(?: in|project)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractCompletedStatus(intent: string): string | null {
    if (intent.toLowerCase().includes('completed')) {
      return 'true';
    } else if (intent.toLowerCase().includes('not completed') || intent.toLowerCase().includes('incomplete')) {
      return 'false';
    }
    return null;
  }
}

export class AsanaCompleteTaskSkill implements Skill {
  id = 'asana_complete_task';
  name = 'Complete Asana Task';
  description = 'Mark a task as completed in Asana';
  category = 'productivity';
  examples = [
    'Complete task for project proposal',
    'Mark code review task as done',
    'Finish Asana task for meeting notes'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract task identifier
      const taskName = this.extractTaskName(intent) ||
                     entities.find((e: any) => e.type === 'task_name')?.value;
      
      const taskId = this.extractTaskId(intent) ||
                    entities.find((e: any) => e.type === 'task_id')?.value;

      if (!taskName && !taskId) {
        return {
          success: false,
          message: 'Task name or ID is required',
          error: 'Missing task identifier'
        };
      }

      // Call Asana API
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'complete',
          task_id: taskId,
          data: {
            name: taskName,
            completed: true,
            completed_at: new Date().toISOString()
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Asana task "${taskName || taskId}" completed successfully`,
          data: {
            task: result.data.task,
            message: result.data.message
          }
        };
      } else {
        return {
          success: false,
          message: `Failed to complete Asana task: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error completing Asana task: ${error}`,
        error: error as any
      };
    }
  }

  private extractTaskName(intent: string): string | null {
    const patterns = [
      /complete task (?:for|to) (.+?)(?: in|due|:|$)/i,
      /finish task (?:for|to) (.+?)(?: in|due|:|$)/i,
      /mark (.+?)(?: task)? as (?:done|completed)/i,
      /task (.+?)(?: as done|completed)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractTaskId(intent: string): string | null {
    const patterns = [
      /task (\d+)/i,
      /id (\d+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }
}

// Project Management Skills
export class AsanaCreateProjectSkill implements Skill {
  id = 'asana_create_project';
  name = 'Create Asana Project';
  description = 'Create a new project in Asana';
  category = 'productivity';
  examples = [
    'Create Asana project for Q4 product development',
    'Start new project for marketing campaign',
    'Create project in Asana for website redesign'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract project details
      const projectName = this.extractProjectName(intent) ||
                        entities.find((e: any) => e.type === 'project_name')?.value ||
                        'New Project';
      
      const description = this.extractDescription(intent) ||
                       entities.find((e: any) => e.type === 'description')?.value ||
                       intent;
      
      const teamName = this.extractTeamName(intent) ||
                      entities.find((e: any) => e.type === 'team_name')?.value;

      if (!projectName) {
        return {
          success: false,
          message: 'Project name is required',
          error: 'Missing project name'
        };
      }

      // Call Asana API
      const response = await fetch('/api/integrations/asana/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: projectName,
            notes: description,
            team: teamName ? { name: teamName } : undefined,
            public: true,
            color: 'light-blue'
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Asana project "${projectName}" created successfully`,
          data: {
            project: result.data.project,
            url: result.data.url,
            name: projectName,
            team: teamName
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Asana',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Asana project: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Asana project: ${error}`,
        error: error as any
      };
    }
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /create (?:asana )?project (?:for|to) (.+?)(?: due|in|:|$)/i,
      /start (?:new )?project (?:for|to) (.+?)(?: due|in|:|$)/i,
      /project (.+?)(?: due|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string {
    const patterns = [
      /(?:for|to) (.+?)(?: due|in|:|$)/i,
      /description (.+?)(?: due|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return intent;
  }

  private extractTeamName(intent: string): string | null {
    const patterns = [
      /team (.+?)(?: due|in|:|$)/i,
      /for team (.+?)(?: due|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

export class AsanaSearchProjectsSkill implements Skill {
  id = 'asana_search_projects';
  name = 'Search Asana Projects';
  description = 'Search projects in Asana';
  category = 'productivity';
  examples = [
    'Search Asana for projects related to product development',
    'Find Asana projects in Q4',
    'Search for marketing projects'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const teamName = this.extractTeamName(intent) ||
                      entities.find((e: any) => e.type === 'team_name')?.value;
      
      const archived = this.extractArchivedStatus(intent) ||
                     entities.find((e: any) => e.type === 'archived')?.value ||
                     'false';
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Asana API
      const response = await fetch('/api/integrations/asana/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          team: teamName,
          archived: archived,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const projects = result.data.projects || [];
        const projectCount = projects.length;

        return {
          success: true,
          message: `Found ${projectCount} Asana project${projectCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            projects: projects,
            total_count: result.data.total_count,
            query: query,
            team: teamName
          },
          actions: projects.map((project: any) => ({
            type: 'open_url',
            label: `View ${project.name}`,
            url: project.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Asana projects: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Asana projects: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:asana )?projects? (?:for|related to) (.+)/i,
      /find (?:asana )?projects? (?:for|about) (.+)/i,
      /projects? (?:for|about) (.+)/i,
      /(.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractTeamName(intent: string): string | null {
    const patterns = [
      /team (.+?)(?: project|assigned|due)/i,
      /for team (.+?)(?: project|assigned|due)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractArchivedStatus(intent: string): string | null {
    if (intent.toLowerCase().includes('archived')) {
      return 'true';
    } else if (intent.toLowerCase().includes('active') || intent.toLowerCase().includes('not archived')) {
      return 'false';
    }
    return null;
  }
}

// Team Management Skills
export class AsanaListTeamsSkill implements Skill {
  id = 'asana_list_teams';
  name = 'List Asana Teams';
  description = 'List teams in Asana';
  category = 'productivity';
  examples = [
    'List all Asana teams',
    'Show my teams in Asana',
    'Display Asana teams'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Asana API
      const response = await fetch('/api/integrations/asana/teams', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const teams = result.data.teams || [];
        const teamCount = teams.length;

        return {
          success: true,
          message: `Found ${teamCount} Asana team${teamCount !== 1 ? 's' : ''}`,
          data: {
            teams: teams,
            total_count: result.data.total_count
          },
          actions: teams.map((team: any) => ({
            type: 'open_url',
            label: `View ${team.name}`,
            url: team.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to list Asana teams: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error listing Asana teams: ${error}`,
        error: error as any
      };
    }
  }
}

// Comment and Collaboration Skills
export class AsanaAddCommentSkill implements Skill {
  id = 'asana_add_comment';
  name = 'Add Asana Comment';
  description = 'Add a comment to a task in Asana';
  category = 'productivity';
  examples = [
    'Add comment to project proposal task',
    'Comment on code review task that the changes look good',
    'Leave a note on the design task'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract comment details
      const taskName = this.extractTaskName(intent) ||
                     entities.find((e: any) => e.type === 'task_name')?.value;
      
      const taskId = this.extractTaskId(intent) ||
                    entities.find((e: any) => e.type === 'task_id')?.value;
      
      const comment = this.extractComment(intent) ||
                   entities.find((e: any) => e.type === 'comment')?.value ||
                   intent;

      if ((!taskName && !taskId) || !comment) {
        return {
          success: false,
          message: 'Task name/ID and comment are required',
          error: 'Missing required parameters'
        };
      }

      // Call Asana API
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'add_comment',
          task_id: taskId,
          comment: comment
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Comment added successfully to task "${taskName || taskId}"`,
          data: {
            story: result.data.story,
            message: result.data.message
          }
        };
      } else {
        return {
          success: false,
          message: `Failed to add comment: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error adding comment: ${error}`,
        error: error as any
      };
    }
  }

  private extractTaskName(intent: string): string | null {
    const patterns = [
      /comment (?:on|to) (.+?)(?: task|that|:|$)/i,
      /add note (?:on|to) (.+?)(?: task|that|:|$)/i,
      /leave (?:a )?note (?:on|to) (.+?)(?: task|that|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractTaskId(intent: string): string | null {
    const patterns = [
      /task (\d+)/i,
      /id (\d+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractComment(intent: string): string | null {
    const patterns = [
      /comment (?:that )?(.+?)(?: is|looks|:|$)/i,
      /note (?:that )?(.+?)(?: is|looks|:|$)/i,
      /say (.+?)(?: on|to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// Universal Search Skill
export class AsanaSearchSkill implements Skill {
  id = 'asana_search';
  name = 'Search Asana';
  description = 'Search across Asana tasks, projects, and teams';
  category = 'productivity';
  examples = [
    'Search Asana for product development',
    'Find everything related to marketing campaign',
    'Search Asana for Q4 initiatives'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search details
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const searchType = this.extractSearchType(intent) ||
                       entities.find((e: any) => e.type === 'search_type')?.value ||
                       'all';
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Asana API
      const response = await fetch('/api/integrations/asana/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          type: searchType,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const searchResults = result.data.results || [];
        const resultCount = searchResults.length;

        return {
          success: true,
          message: `Found ${resultCount} result${resultCount !== 1 ? 's' : ''} for "${query}" in Asana`,
          data: {
            results: searchResults,
            total_count: result.data.total_count,
            query: query,
            search_type: searchType
          },
          actions: searchResults.map((item: any) => ({
            type: 'open_url',
            label: `View ${item.name} (${item.type})`,
            url: item.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Asana: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Asana: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:asana )?for (.+)/i,
      /find (.+?) in asana/i,
      /(.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractSearchType(intent: string): string | null {
    if (intent.toLowerCase().includes('tasks')) {
      return 'tasks';
    } else if (intent.toLowerCase().includes('projects')) {
      return 'projects';
    } else if (intent.toLowerCase().includes('teams')) {
      return 'teams';
    }
    return 'all';
  }
}

// Export all Asana skills
export const ASANA_SKILLS = [
  new AsanaCreateTaskSkill(),
  new AsanaSearchTasksSkill(),
  new AsanaCompleteTaskSkill(),
  new AsanaCreateProjectSkill(),
  new AsanaSearchProjectsSkill(),
  new AsanaListTeamsSkill(),
  new AsanaAddCommentSkill(),
  new AsanaSearchSkill()
];

// Export skills registry
export const ASANA_SKILLS_REGISTRY = {
  'asana_create_task': AsanaCreateTaskSkill,
  'asana_search_tasks': AsanaSearchTasksSkill,
  'asana_complete_task': AsanaCompleteTaskSkill,
  'asana_create_project': AsanaCreateProjectSkill,
  'asana_search_projects': AsanaSearchProjectsSkill,
  'asana_list_teams': AsanaListTeamsSkill,
  'asana_add_comment': AsanaAddCommentSkill,
  'asana_search': AsanaSearchSkill
};