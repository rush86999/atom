/**
 * Jira Integration Skills
 * Complete Jira integration with comprehensive project management capabilities
 */

export interface JiraSkillConfig {
  accessToken?: string;
  cloudId?: string;
  baseUrl?: string;
  userAgent?: string;
}

export interface JiraIssue {
  id: string;
  key: string;
  summary: string;
  description: string;
  issueType: {
    id: string;
    name: string;
    iconUrl: string;
    description: string;
  };
  status: {
    id: string;
    name: string;
    statusCategory: {
      id: number;
      key: string;
      colorName: string;
    };
  };
  priority: {
    id: string;
    name: string;
    statusColor: string;
  };
  assignee: {
    accountId: string;
    displayName: string;
    emailAddress?: string;
  };
  reporter: {
    accountId: string;
    displayName: string;
    emailAddress?: string;
  };
  project: {
    id: string;
    key: string;
    name: string;
  };
  created: string;
  updated: string;
  dueDate: string;
  resolutionDate: string;
  components: Array<{
    id: string;
    name: string;
  }>;
  labels: string[];
  fixVersions: Array<{
    id: string;
    name: string;
  }>;
  versions: Array<{
    id: string;
    name: string;
  }>;
  environment: string;
  timeEstimate: number;
  timeSpent: number;
  watches: number;
  comments: any[];
}

export interface JiraProject {
  id: string;
  key: string;
  name: string;
  description: string;
  projectType: string;
  lead: {
    accountId: string;
    displayName: string;
  };
  url: string;
  avatarUrls: {
    '48x48': string;
    '24x24': string;
  };
  projectCategory: {
    id: string;
    name: string;
    description: string;
  };
  style: string;
  isPrivate: boolean;
  issueTypes: Array<{
    id: string;
    name: string;
  }>;
  versions: Array<{
    id: string;
    name: string;
  }>;
  components: Array<{
    id: string;
    name: string;
  }>;
  roles: Record<string, string>;
}

export interface JiraBoard {
  id: string;
  name: string;
  type: string;
  filterId: string;
  filterName: string;
  projectId: string;
  projectKey: string;
  projectName: string;
  sprintStartDate: string;
  sprintEndDate: string;
  completeDate: string;
  sprintState: string;
  rank: number;
}

export interface JiraUser {
  accountId: string;
  accountType: string;
  active: boolean;
  displayName: string;
  emailAddress: string;
  avatarUrls: {
    '48x48': string;
    '24x24': string;
  };
  timeZone: string;
  locale: string;
  groups: Array<{
    name: string;
  }>;
  applicationRoles: Array<{
    name: string;
  }>;
}

export interface JiraSprint {
  id: string;
  name: string;
  state: string;
  goal: string;
  startDate: string;
  endDate: string;
  completeDate: string;
  originBoardId: string;
  createdDate: string;
  rapidViewId: string;
  sequence: number;
}

/**
 * Jira Skills Registry - Complete set of Jira integration capabilities
 */
export const jiraSkills = {
  
  /**
   * Create a new Jira issue
   */
  jiraCreateIssue: {
    id: 'jiraCreateIssue',
    name: 'Create Jira Issue',
    description: 'Create a new Jira issue with configuration options',
    category: 'project-management',
    icon: '🐛',
    parameters: {
      type: 'object',
      properties: {
        projectKey: {
          type: 'string',
          description: 'Project key (required)',
          minLength: 2,
          maxLength: 10
        },
        summary: {
          type: 'string',
          description: 'Issue summary (required)',
          minLength: 1,
          maxLength: 255
        },
        issueType: {
          type: 'string',
          enum: ['Story', 'Task', 'Bug', 'Epic', 'Sub-task'],
          description: 'Issue type (required)'
        },
        description: {
          type: 'string',
          description: 'Issue description in Markdown (optional)',
          maxLength: 32768
        },
        priority: {
          type: 'string',
          enum: ['Highest', 'High', 'Medium', 'Low', 'Lowest'],
          description: 'Issue priority (default: Medium)',
          default: 'Medium'
        },
        assignee: {
          type: 'string',
          description: 'Assignee account ID (optional)',
          minLength: 1
        },
        labels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Issue labels (optional)',
          default: []
        },
        components: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Issue components (optional)',
          default: []
        },
        dueDate: {
          type: 'string',
          description: 'Due date in ISO 8601 format (optional)'
        }
      },
      required: ['projectKey', 'summary', 'issueType']
    }
  },

  /**
   * Search Jira issues
   */
  jiraSearchIssues: {
    id: 'jiraSearchIssues',
    name: 'Search Jira Issues',
    description: 'Search for issues using JQL (Jira Query Language)',
    category: 'project-management',
    icon: '🔍',
    parameters: {
      type: 'object',
      properties: {
        jql: {
          type: 'string',
          description: 'JQL query (required)',
          minLength: 1,
          maxLength: 1000
        },
        limit: {
          type: 'number',
          description: 'Maximum number of issues to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        },
        startAt: {
          type: 'number',
          description: 'Starting index for pagination (default: 0)',
          default: 0,
          minimum: 0
        },
        fields: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Fields to include in response (optional)',
          default: ['summary', 'status', 'priority', 'assignee', 'created', 'updated']
        }
      },
      required: ['jql']
    }
  },

  /**
   * Get Jira issue details
   */
  jiraGetIssue: {
    id: 'jiraGetIssue',
    name: 'Get Issue Details',
    description: 'Get detailed information about a Jira issue',
    category: 'project-management',
    icon: '📋',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        }
      },
      required: ['issueKey']
    }
  },

  /**
   * Update Jira issue
   */
  jiraUpdateIssue: {
    id: 'jiraUpdateIssue',
    name: 'Update Jira Issue',
    description: 'Update fields of an existing Jira issue',
    category: 'project-management',
    icon: '✏️',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        },
        fields: {
          type: 'object',
          description: 'Fields to update (required)',
          properties: {
            summary: {
              type: 'string',
              description: 'Issue summary',
              maxLength: 255
            },
            description: {
              type: 'string',
              description: 'Issue description',
              maxLength: 32768
            },
            priority: {
              type: 'object',
              description: 'Issue priority',
              properties: {
                name: {
                  type: 'string',
                  enum: ['Highest', 'High', 'Medium', 'Low', 'Lowest']
                }
              }
            },
            assignee: {
              type: 'object',
              description: 'Assignee',
              properties: {
                accountId: {
                  type: 'string'
                }
              }
            },
            status: {
              type: 'object',
              description: 'Issue status',
              properties: {
                name: {
                  type: 'string'
                }
              }
            },
            labels: {
              type: 'array',
              items: {
                type: 'string'
              },
              description: 'Issue labels'
            }
          }
        }
      },
      required: ['issueKey', 'fields']
    }
  },

  /**
   * List Jira projects
   */
  jiraListProjects: {
    id: 'jiraListProjects',
    name: 'List Jira Projects',
    description: 'List projects accessible to the authenticated user',
    category: 'project-management',
    icon: '📁',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of projects to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
      }
    }
  },

  /**
   * List Jira boards
   */
  jiraListBoards: {
    id: 'jiraListBoards',
    name: 'List Jira Boards',
    description: 'List agile boards accessible to the user',
    category: 'project-management',
    icon: '📊',
    parameters: {
      type: 'object',
      properties: {
        projectKey: {
          type: 'string',
          description: 'Filter boards by project key (optional)',
          minLength: 2
        },
        limit: {
          type: 'number',
          description: 'Maximum number of boards to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
      }
    }
  },

  /**
   * List Jira sprints
   */
  jiraListSprints: {
    id: 'jiraListSprints',
    name: 'List Jira Sprints',
    description: 'List sprints for a specific board',
    category: 'project-management',
    icon: '🏃',
    parameters: {
      type: 'object',
      properties: {
        boardId: {
          type: 'string',
          description: 'Board ID to get sprints for (required)',
          minLength: 1
        },
        state: {
          type: 'string',
          enum: ['active', 'closed', 'future'],
          description: 'Filter sprints by state (optional)'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of sprints to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
      },
      required: ['boardId']
    }
  },

  /**
   * Search Jira users
   */
  jiraSearchUsers: {
    id: 'jiraSearchUsers',
    name: 'Search Jira Users',
    description: 'Search for Jira users by name or email',
    category: 'user-management',
    icon: '👥',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (user name or email) (required)',
          minLength: 2,
          maxLength: 255
        },
        limit: {
          type: 'number',
          description: 'Maximum number of users to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
      },
      required: ['query']
    }
  },

  /**
   * Get project information
   */
  jiraGetProject: {
    id: 'jiraGetProject',
    name: 'Get Project Info',
    description: 'Get detailed information about a Jira project',
    category: 'project-management',
    icon: 'ℹ️',
    parameters: {
      type: 'object',
      properties: {
        projectKey: {
          type: 'string',
          description: 'Project key (required)',
          minLength: 2,
          maxLength: 10
        }
      },
      required: ['projectKey']
    }
  },

  /**
   * Create sprint
   */
  jiraCreateSprint: {
    id: 'jiraCreateSprint',
    name: 'Create Jira Sprint',
    description: 'Create a new sprint for a board',
    category: 'project-management',
    icon: '🏃',
    parameters: {
      type: 'object',
      properties: {
        boardId: {
          type: 'string',
          description: 'Board ID to create sprint for (required)',
          minLength: 1
        },
        name: {
          type: 'string',
          description: 'Sprint name (required)',
          minLength: 1,
          maxLength: 255
        },
        goal: {
          type: 'string',
          description: 'Sprint goal (optional)',
          maxLength: 1000
        },
        startDate: {
          type: 'string',
          description: 'Sprint start date in ISO 8601 format (optional)'
        },
        endDate: {
          type: 'string',
          description: 'Sprint end date in ISO 8601 format (optional)'
        }
      },
      required: ['boardId', 'name']
    }
  },

  /**
   * Add comment to issue
   */
  jiraAddComment: {
    id: 'jiraAddComment',
    name: 'Add Issue Comment',
    description: 'Add a comment to a Jira issue',
    category: 'project-management',
    icon: '💬',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        },
        body: {
          type: 'string',
          description: 'Comment body in Markdown (required)',
          minLength: 1,
          maxLength: 32768
        },
        visibility: {
          type: 'object',
          description: 'Comment visibility (optional)',
          properties: {
            type: {
              type: 'string',
              enum: ['role', 'group']
            },
            value: {
              type: 'string'
            }
          }
        }
      },
      required: ['issueKey', 'body']
    }
  },

  /**
   * Transition issue status
   */
  jiraTransitionIssue: {
    id: 'jiraTransitionIssue',
    name: 'Transition Issue Status',
    description: 'Change the status of a Jira issue',
    category: 'project-management',
    icon: '🔄',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        },
        transition: {
          type: 'object',
          description: 'Transition details (required)',
          properties: {
            id: {
              type: 'string',
              description: 'Transition ID'
            },
            name: {
              type: 'string',
              description: 'Transition name'
            }
          },
          required: ['id']
        },
        comment: {
          type: 'string',
          description: 'Comment for the transition (optional)',
          maxLength: 32768
        }
      },
      required: ['issueKey', 'transition']
    }
  },

  /**
   * Assign issue to user
   */
  jiraAssignIssue: {
    id: 'jiraAssignIssue',
    name: 'Assign Issue',
    description: 'Assign a Jira issue to a user',
    category: 'project-management',
    icon: '👤',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        },
        assignee: {
          type: 'string',
          description: 'Assignee account ID (required)',
          minLength: 1
        }
      },
      required: ['issueKey', 'assignee']
    }
  },

  /**
   * Add attachment to issue
   */
  jiraAddAttachment: {
    id: 'jiraAddAttachment',
    name: 'Add Issue Attachment',
    description: 'Add an attachment to a Jira issue',
    category: 'file-management',
    icon: '📎',
    parameters: {
      type: 'object',
      properties: {
        issueKey: {
          type: 'string',
          description: 'Issue key (e.g., PROJ-123) (required)',
          minLength: 3
        },
        filePath: {
          type: 'string',
          description: 'Path to file to attach (required)',
          minLength: 1
        },
        filename: {
          type: 'string',
          description: 'Custom filename (optional)',
          maxLength: 255
        }
      },
      required: ['issueKey', 'filePath']
    }
  }
};

/**
 * Jira skill utilities and formatting helpers
 */
export const jiraUtils = {
  /**
   * Format issue for display
   */
  formatIssue: (issue: JiraIssue): string => {
    const typeIcon = jiraUtils.getIssueTypeIcon(issue.issueType.name);
    const statusColor = jiraUtils.getStatusColor(issue.status.statusCategory.colorName);
    const priorityIcon = jiraUtils.getPriorityIcon(issue.priority.name);
    const assignee = issue.assignee ? ` (${issue.assignee.displayName})` : '';
    return `${typeIcon} ${priorityIcon} ${issue.key}: ${issue.issueType.name} - ${issue.summary}${assignee}`;
  },

  /**
   * Format project for display
   */
  formatProject: (project: JiraProject): string => {
    const typeIcon = jiraUtils.getProjectTypeIcon(project.projectType);
    const privacy = project.isPrivate ? '🔒' : '🌍';
    return `${typeIcon} ${privacy} ${project.name} (${project.key})`;
  },

  /**
   * Format user for display
   */
  formatUser: (user: JiraUser): string => {
    const active = user.active ? '✅' : '❌';
    return `${active} ${user.displayName}`;
  },

  /**
   * Format sprint for display
   */
  formatSprint: (sprint: JiraSprint): string => {
    const stateIcon = jiraUtils.getSprintStateIcon(sprint.state);
    const dates = sprint.startDate && sprint.endDate ? 
      ` (${jiraUtils.formatDate(sprint.startDate)} - ${jiraUtils.formatDate(sprint.endDate)})` : '';
    return `${stateIcon} ${sprint.name}${dates}`;
  },

  /**
   * Get issue URL
   */
  getIssueUrl: (issue: JiraIssue, baseUrl: string = 'https://company.atlassian.net'): string => {
    return `${baseUrl}/browse/${issue.key}`;
  },

  /**
   * Get project URL
   */
  getProjectUrl: (project: JiraProject, baseUrl: string = 'https://company.atlassian.net'): string => {
    return `${baseUrl}/projects/${project.key}`;
  },

  /**
   * Get board URL
   */
  getBoardUrl: (board: JiraBoard, baseUrl: string = 'https://company.atlassian.net'): string => {
    return `${baseUrl}/secure/RapidBoard.jspa?rapidView=${board.id}`;
  },

  /**
   * Get user initials
   */
  getUserInitials: (user: JiraUser): string => {
    const names = user.displayName.split(' ');
    if (names.length >= 2) {
      return names[0][0].toUpperCase() + names[names.length - 1][0].toUpperCase();
    }
    return names[0] ? names[0].substring(0, 2).toUpperCase() : 'UN';
  },

  /**
   * Validate issue key format
   */
  validateIssueKey: (issueKey: string): boolean => {
    const issueKeyPattern = /^[A-Z][A-Z0-9]*-\d+$/;
    return issueKeyPattern.test(issueKey);
  },

  /**
   * Validate JQL query
   */
  validateJQL: (jql: string): boolean => {
    // Basic JQL validation
    if (!jql || jql.trim().length === 0) return false;
    
    // Check for common JQL keywords
    const jqlKeywords = ['project=', 'status=', 'assignee=', 'priority=', 'type=', 'ORDER BY'];
    const hasValidKeyword = jqlKeywords.some(keyword => jql.toUpperCase().includes(keyword));
    
    return hasValidKeyword;
  },

  /**
   * Format date time
   */
  formatDateTime: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateTime;
    }
  },

  /**
   * Format date only
   */
  formatDate: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateTime;
    }
  },

  /**
   * Format time only
   */
  formatTime: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateTime;
    }
  },

  /**
   * Get issue type icon
   */
  getIssueTypeIcon: (issueType: string): string => {
    const icons: Record<string, string> = {
      'Story': '📖',
      'Task': '📋',
      'Bug': '🐛',
      'Epic': '🏗️',
      'Sub-task': '🔹',
      'Improvement': '⚡',
      'New Feature': '✨',
      'Change': '🔄'
    };
    
    return icons[issueType] || '📝';
  },

  /**
   * Get priority icon
   */
  getPriorityIcon: (priority: string): string => {
    const icons: Record<string, string> = {
      'Highest': '🔴',
      'High': '🟠',
      'Medium': '🟡',
      'Low': '🟢',
      'Lowest': '🔵'
    };
    
    return icons[priority] || '⚪';
  },

  /**
   * Get status color
   */
  getStatusColor: (colorName: string): string => {
    const colors: Record<string, string> = {
      'blue-gray': '#6B778C',
      'yellow': '#FFAB00',
      'green': '#00875A',
      'blue': '#0052CC',
      'red': '#DE350B',
      'gray': '#42526E'
    };
    
    return colors[colorName] || '#42526E';
  },

  /**
   * Get project type icon
   */
  getProjectTypeIcon: (projectType: string): string => {
    const icons: Record<string, string> = {
      'software': '💻',
      'service_desk': '🎧',
      'business': '💼',
      'next-gen': '🚀'
    };
    
    return icons[projectType] || '📁';
  },

  /**
   * Get sprint state icon
   */
  getSprintStateIcon: (state: string): string => {
    const icons: Record<string, string> = {
      'active': '🏃',
      'closed': '✅',
      'future': '⏳',
      'planned': '📅'
    };
    
    return icons[state] || '❓';
  },

  /**
   * Format duration
   */
  formatDuration: (seconds: number): string => {
    if (!seconds) return '0m';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    
    return `${minutes}m`;
  },

  /**
   * Calculate days until due
   */
  getDaysUntilDue: (dueDate: string): number => {
    if (!dueDate) return -1;
    
    const now = new Date();
    const due = new Date(dueDate);
    const diffTime = due.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return diffDays;
  },

  /**
   * Format relative time
   */
  getRelativeTime: (dateTime: string): string => {
    const date = new Date(dateTime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays > 0) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    }
    
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours > 0) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    }
    
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    if (diffMinutes > 0) {
      return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    }
    
    return 'Just now';
  },

  /**
   * Truncate text
   */
  truncateText: (text: string, maxLength: number = 50): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
  },

  /**
   * Extract project key from issue key
   */
  extractProjectKey: (issueKey: string): string => {
    const match = issueKey.match(/^([A-Z][A-Z0-9]*)-\d+$/);
    return match ? match[1] : '';
  },

  /**
   * Format issue number
   */
  formatIssueNumber: (issueKey: string): string => {
    const match = issueKey.match(/^([A-Z][A-Z0-9]*)-(\d+)$/);
    return match ? match[2] : '';
  },

  /**
   * Check if issue is overdue
   */
  isOverdue: (issue: JiraIssue): boolean => {
    if (!issue.dueDate || issue.resolutionDate) return false;
    
    const now = new Date();
    const due = new Date(issue.dueDate);
    
    return now > due;
  },

  /**
   * Get progress percentage
   */
  getProgressPercentage: (timeSpent: number, timeEstimate: number): number => {
    if (!timeEstimate || timeEstimate === 0) return 0;
    return Math.min(Math.round((timeSpent / timeEstimate) * 100), 100);
  },

  /**
   * Format progress bar
   */
  formatProgressBar: (percentage: number, width: number = 20): string => {
    const filled = Math.round((percentage / 100) * width);
    const empty = width - filled;
    const filledChar = percentage >= 100 ? '🟢' : '🔵';
    return `${filledChar.repeat(filled)}⚪${empty}`;

  /**
   * Generate common JQL queries
   */
  getCommonJQLQueries: (): Array<{name: string, jql: string, description: string}> => {
    return [
      {
        name: 'My Open Issues',
        jql: 'assignee = currentUser() AND status not in (Closed, Done, Resolved)',
        description: 'Issues assigned to me that are not closed'
      },
      {
        name: 'My Created Issues',
        jql: 'reporter = currentUser() ORDER BY created DESC',
        description: 'Issues I created, ordered by creation date'
      },
      {
        name: 'High Priority Issues',
        jql: 'priority in (Highest, High) AND status not in (Closed, Done)',
        description: 'High priority issues that are not resolved'
      },
      {
        name: 'Issues Due This Week',
        jql: 'due >= startOfWeek() AND due <= endOfWeek() AND status not in (Closed, Done)',
        description: 'Issues due this week'
      },
      {
        name: 'Overdue Issues',
        jql: 'duedate < now() AND status not in (Closed, Done)',
        description: 'Issues that are past their due date'
      }
    ];
  }
};

export default jiraSkills;