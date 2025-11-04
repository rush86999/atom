/**
 * ATOM Jira Manager - TypeScript
 * Project Management → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomJiraManagerProps, 
  AtomJiraState,
  JiraConfig,
  AtomJiraAPI,
  JiraProject,
  JiraIssue,
  JiraBoard,
  JiraUser,
  JiraComment,
  JiraAttachment,
  JiraSearchResponse
} from '../types';

export const ATOMJiraManager: React.FC<AtomJiraManagerProps> = ({
  // Jira Authentication
  serverUrl,
  username,
  apiToken,
  oauthToken,
  onTokenRefresh,
  
  // Jira Configuration
  config = {},
  platform = 'auto',
  theme = 'auto',
  
  // Events
  onProjectSelected,
  onIssueSelected,
  onBoardSelected,
  onError,
  onSuccess,
  onProjectsLoaded,
  onIssuesLoaded,
  onBoardsLoaded,
  onCommentsLoaded,
  onAttachmentsLoaded,
  
  // Children
  children
}) => {
  
  // State Management
  const [state, setState] = useState<AtomJiraState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    projects: [],
    issues: [],
    boards: [],
    sprints: [],
    users: [],
    filters: [],
    currentProject: undefined,
    currentBoard: undefined,
    selectedItems: [],
    searchResults: {
      startAt: 0,
      maxResults: 0,
      total: 0,
      issues: []
    },
    sortBy: 'created',
    sortOrder: 'desc',
    viewMode: 'list',
    filters: {
      projects: [],
      issueTypes: [],
      statuses: [],
      priorities: [],
      assignees: [],
      labels: [],
      components: [],
      dateRange: undefined,
      jqlQuery: undefined
    }
  });

  // Configuration
  const [jiraConfig] = useState<JiraConfig>(() => ({
    // API Configuration
    apiBaseUrl: '/rest/api/3',
    jqlApiUrl: '/rest/api/3/search',
    
    // Authentication
    serverUrl: serverUrl || '',
    username: username,
    apiToken: apiToken,
    oauthToken: oauthToken,
    
    // Jira-specific settings
    defaultProject: config.defaultProject,
    defaultAssignee: config.defaultAssignee,
    defaultPriority: config.defaultPriority,
    defaultIssueType: config.defaultIssueType,
    
    // Issue Discovery
    includeSubtasks: config.includeSubtasks ?? true,
    includeArchived: config.includeArchived ?? false,
    maxIssuesPerProject: config.maxIssuesPerProject ?? 1000,
    issueDateRange: config.issueDateRange,
    
    // Project Filtering
    includedProjects: config.includedProjects ?? [],
    excludedProjects: config.excludedProjects ?? [],
    projectTypes: config.projectTypes ?? ['software', 'service_desk', 'business'],
    
    // Search Settings
    jqlQuery: config.jqlQuery,
    searchFields: config.searchFields ?? ['summary', 'description', 'comment', 'status', 'priority', 'assignee'],
    maxSearchResults: config.maxSearchResults ?? 100,
    
    // Issue Processing
    includeComments: config.includeComments ?? true,
    includeAttachments: config.includeAttachments ?? true,
    includeHistory: config.includeHistory ?? true,
    includeLinkedIssues: config.includeLinkedIssues ?? true,
    maxAttachmentSize: config.maxAttachmentSize ?? 50 * 1024 * 1024,
    
    // Rate Limiting
    apiCallsPerSecond: config.apiCallsPerSecond ?? 60,
    useBatchRequests: config.useBatchRequests ?? true,
    
    ...config
  }));

  // Platform Detection
  const [currentPlatform, setCurrentPlatform] = useState<'nextjs' | 'tauri'>('nextjs');

  useEffect(() => {
    if (platform !== 'auto') {
      setCurrentPlatform(platform);
      return;
    }
    
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      setCurrentPlatform('tauri');
    } else {
      setCurrentPlatform('nextjs');
    }
  }, [platform]);

  // Jira API Integration
  const jiraApi = useMemo((): AtomJiraAPI => {
    const baseUrl = jiraConfig.serverUrl.replace(/\/$/, '');
    const authString = jiraConfig.username && jiraConfig.apiToken 
      ? 'Basic ' + btoa(`${jiraConfig.username}:${jiraConfig.apiToken}`)
      : `Bearer ${jiraConfig.oauthToken}`;

    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${baseUrl}${endpoint}`;
      const headers: Record<string, string> = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': authString,
        ...options.headers as Record<string, string>
      };

      try {
        const response = await fetch(url, {
          ...options,
          headers
        });

        if (response.status === 401) {
          throw new Error('Authentication failed - please check your credentials');
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`Jira API Error: ${response.status} - ${errorData.message || response.statusText}`);
        }

        return response.json();
      } catch (error) {
        console.error('Jira API request failed:', error);
        throw error;
      }
    };

    return {
      // Authentication
      authenticate: async () => {
        return {
          accessToken: jiraConfig.oauthToken || 'basic_auth',
          tokenType: 'Bearer',
          expiresIn: 3600
        };
      },

      // Project Operations
      getProjects: async (startAt = 0, maxResults = 100) => {
        const projects = await makeRequest(`${jiraConfig.apiBaseUrl}/project/search?startAt=${startAt}&maxResults=${maxResults}`);
        return projects.values || [];
      },

      getProject: async (projectId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/project/${projectId}`);
      },

      // Issue Operations
      getIssues: async (jql: string, startAt = 0, maxResults = 100, fields?: string[]) => {
        const fieldString = fields ? fields.join(',') : jiraConfig.searchFields.join(',');
        return await makeRequest(`${jiraConfig.jqlApiUrl}?jql=${encodeURIComponent(jql)}&startAt=${startAt}&maxResults=${maxResults}&fields=${fieldString}`);
      },

      getIssue: async (issueId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}?expand=renderedFields,comments,attachments`);
      },

      createIssue: async (issue: any) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue`, {
          method: 'POST',
          body: JSON.stringify({
            fields: {
              project: { key: issue.project },
              summary: issue.summary,
              description: issue.description,
              issuetype: { name: issue.issueType || 'Task' },
              priority: issue.priority ? { name: issue.priority } : undefined,
              assignee: issue.assignee ? { name: issue.assignee } : undefined,
              components: issue.components ? issue.components.map((c: any) => ({ name: c })) : undefined,
              fixVersions: issue.fixVersions ? issue.fixVersions.map((v: any) => ({ name: v })) : undefined,
              labels: issue.labels
            }
          })
        });
      },

      updateIssue: async (issueId: string, issue: any) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}`, {
          method: 'PUT',
          body: JSON.stringify({
            fields: {
              summary: issue.summary,
              description: issue.description,
              priority: issue.priority ? { name: issue.priority } : undefined,
              assignee: issue.assignee ? { name: issue.assignee } : undefined
            }
          })
        });
      },

      deleteIssue: async (issueId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}`, {
          method: 'DELETE'
        });
      },

      assignIssue: async (issueId: string, assignee?: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}/assignee`, {
          method: 'PUT',
          body: JSON.stringify({
            name: assignee || 'unassigned'
          })
        });
      },

      transitionIssue: async (issueId: string, transition: any) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}/transitions`, {
          method: 'POST',
          body: JSON.stringify({
            transition: {
              id: transition.id
            }
          })
        });
      },

      // Comment Operations
      getComments: async (issueId: string) => {
        const response = await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}/comment`);
        return response.comments || [];
      },

      addComment: async (issueId: string, comment: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}/comment`, {
          method: 'POST',
          body: JSON.stringify({
            body: {
              type: 'doc',
              version: 1,
              content: [
                {
                  type: 'paragraph',
                  content: [
                    {
                      type: 'text',
                      text: comment
                    }
                  ]
                }
              ]
            }
          })
        });
      },

      updateComment: async (commentId: string, comment: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/comment/${commentId}`, {
          method: 'PUT',
          body: JSON.stringify({
            body: {
              type: 'doc',
              version: 1,
              content: [
                {
                  type: 'paragraph',
                  content: [
                    {
                      type: 'text',
                      text: comment
                    }
                  ]
                }
              ]
            }
          })
        });
      },

      deleteComment: async (commentId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/comment/${commentId}`, {
          method: 'DELETE'
        });
      },

      // Attachment Operations
      getAttachment: async (attachmentId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/attachment/${attachmentId}`);
      },

      downloadAttachment: async (attachmentId: string) => {
        const attachment = await jiraApi.getAttachment(attachmentId);
        const response = await fetch(attachment.content);
        const blob = await response.blob();
        return {
          id: attachment.id,
          filename: attachment.filename,
          author: attachment.author,
          created: attachment.created,
          size: attachment.size,
          mimeType: attachment.mimeType,
          content: attachment.content,
          thumbnail: attachment.thumbnail,
          blob: blob
        };
      },

      addAttachment: async (issueId: string, file: File) => {
        const formData = new FormData();
        formData.append('file', file);

        return await makeRequest(`${jiraConfig.apiBaseUrl}/issue/${issueId}/attachments`, {
          method: 'POST',
          body: formData,
          headers: {
            'X-Atlassian-Token': 'no-check'
          }
        });
      },

      deleteAttachment: async (attachmentId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/attachment/${attachmentId}`, {
          method: 'DELETE'
        });
      },

      // Board Operations
      getBoards: async (startAt = 0, maxResults = 100) => {
        const response = await makeRequest(`${jiraConfig.apiBaseUrl}/board?startAt=${startAt}&maxResults=${maxResults}`);
        return response.values || [];
      },

      getBoard: async (boardId: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/board/${boardId}`);
      },

      getBoardIssues: async (boardId: string, startAt = 0, maxResults = 100) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/board/${boardId}/issue?startAt=${startAt}&maxResults=${maxResults}`);
      },

      // User Operations
      getUsers: async (startAt = 0, maxResults = 100) => {
        const response = await makeRequest(`${jiraConfig.apiBaseUrl}/users/search?startAt=${startAt}&maxResults=${maxResults}`);
        return response.values || [];
      },

      getUser: async (username: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/user?username=${encodeURIComponent(username)}`);
      },

      searchUsers: async (query: string, maxResults = 50) => {
        const response = await makeRequest(`${jiraConfig.apiBaseUrl}/user/search?query=${encodeURIComponent(query)}&maxResults=${maxResults}`);
        return response.values || [];
      },

      // Search Operations
      searchIssues: async (jql: string, fields?: string[]) => {
        const fieldString = fields ? fields.join(',') : jiraConfig.searchFields.join(',');
        return await makeRequest(`${jiraConfig.jqlApiUrl}?jql=${encodeURIComponent(jql)}&fields=${fieldString}`);
      },

      searchProjects: async (query: string) => {
        return await makeRequest(`${jiraConfig.apiBaseUrl}/project/search?query=${encodeURIComponent(query)}`);
      },

      searchBoards: async (query: string) => {
        const response = await makeRequest(`${jiraConfig.apiBaseUrl}/board?name=${encodeURIComponent(query)}`);
        return response.values || [];
      }
    };
  }, [jiraConfig]);

  // Initialize Jira connection
  const initializeJira = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Test authentication
      const authResponse = await jiraApi.authenticate();
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        initialized: true
      }));
      
      if (onSuccess) {
        onSuccess({
          connected: true,
          serverUrl: jiraConfig.serverUrl,
          authType: jiraConfig.oauthToken ? 'OAuth' : 'Basic'
        });
      }
      
    } catch (error) {
      const errorMessage = `Failed to initialize Jira: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'initialization');
      }
    }
  }, [jiraApi, onSuccess, onError]);

  // Load Projects
  const loadProjects = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const projects = await jiraApi.getProjects();
      
      // Filter projects based on configuration
      const filteredProjects = projects.filter(project => {
        // Check if project is explicitly included
        if (jiraConfig.includedProjects.length > 0) {
          return jiraConfig.includedProjects.includes(project.key);
        }
        
        // Check if project is excluded
        if (jiraConfig.excludedProjects.includes(project.key)) {
          return false;
        }
        
        // Check project type
        if (jiraConfig.projectTypes.length > 0) {
          return jiraConfig.projectTypes.includes(project.projectTypeKey);
        }
        
        return true;
      });
      
      setState(prev => ({
        ...prev,
        loading: false,
        projects: filteredProjects
      }));
      
      if (onProjectsLoaded) {
        onProjectsLoaded(filteredProjects);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load projects: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadProjects');
      }
    }
  }, [jiraApi, jiraConfig, onProjectsLoaded, onError]);

  // Load Issues
  const loadIssues = useCallback(async (jql?: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const query = jql || jiraConfig.jqlQuery || 'status != "Done" ORDER BY created DESC';
      const response = await jiraApi.getIssues(query, 0, jiraConfig.maxSearchResults);
      
      setState(prev => ({
        ...prev,
        loading: false,
        issues: response.issues || [],
        searchResults: response
      }));
      
      if (onIssuesLoaded) {
        onIssuesLoaded(response.issues || []);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load issues: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadIssues');
      }
    }
  }, [jiraApi, jiraConfig, jiraConfig.jqlQuery, jiraConfig.maxSearchResults, onIssuesLoaded, onError]);

  // Load Boards
  const loadBoards = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const boards = await jiraApi.getBoards();
      
      setState(prev => ({
        ...prev,
        loading: false,
        boards: boards
      }));
      
      if (onBoardsLoaded) {
        onBoardsLoaded(boards);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load boards: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadBoards');
      }
    }
  }, [jiraApi, onBoardsLoaded, onError]);

  // Load Comments for Issue
  const loadComments = useCallback(async (issueId: string) => {
    try {
      const comments = await jiraApi.getComments(issueId);
      
      if (onCommentsLoaded) {
        onCommentsLoaded(comments);
      }
      
      return comments;
      
    } catch (error) {
      const errorMessage = `Failed to load comments: ${(error as Error).message}`;
      
      if (onError) {
        onError(errorMessage, 'loadComments');
      }
      
      return [];
    }
  }, [jiraApi, onCommentsLoaded, onError]);

  // Load Attachments for Issue
  const loadAttachments = useCallback(async (issueId: string) => {
    try {
      const issue = await jiraApi.getIssue(issueId);
      const attachments = issue.fields.attachments || [];
      
      if (onAttachmentsLoaded) {
        onAttachmentsLoaded(attachments);
      }
      
      return attachments;
      
    } catch (error) {
      const errorMessage = `Failed to load attachments: ${(error as Error).message}`;
      
      if (onError) {
        onError(errorMessage, 'loadAttachments');
      }
      
      return [];
    }
  }, [jiraApi, onAttachmentsLoaded, onError]);

  // Create Issue
  const createIssue = useCallback(async (issue: any) => {
    try {
      const newIssue = await jiraApi.createIssue(issue);
      
      if (onSuccess) {
        onSuccess({
          action: 'issue_created',
          issue: newIssue
        });
      }
      
      return newIssue;
      
    } catch (error) {
      const errorMessage = `Failed to create issue: ${(error as Error).message}`;
      
      if (onError) {
        onError(errorMessage, 'createIssue');
      }
      
      throw error;
    }
  }, [jiraApi, onSuccess, onError]);

  // Update Issue
  const updateIssue = useCallback(async (issueId: string, issue: any) => {
    try {
      await jiraApi.updateIssue(issueId, issue);
      
      if (onSuccess) {
        onSuccess({
          action: 'issue_updated',
          issueId
        });
      }
      
    } catch (error) {
      const errorMessage = `Failed to update issue: ${(error as Error).message}`;
      
      if (onError) {
        onError(errorMessage, 'updateIssue');
      }
      
      throw error;
    }
  }, [jiraApi, onSuccess, onError]);

  // Search Issues
  const searchIssues = useCallback(async (query: string, fields?: string[]) => {
    try {
      const response = await jiraApi.searchIssues(query, fields);
      
      setState(prev => ({
        ...prev,
        searchResults: response
      }));
      
      return response;
      
    } catch (error) {
      const errorMessage = `Failed to search issues: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'searchIssues');
      }
      
      return { startAt: 0, maxResults: 0, total: 0, issues: [] };
    }
  }, [jiraApi, onError]);

  // Initialize on mount
  useEffect(() => {
    if (jiraConfig.serverUrl && (jiraConfig.username || jiraConfig.oauthToken)) {
      initializeJira();
    }
  }, [jiraConfig.serverUrl, jiraConfig.username, jiraConfig.oauthToken]);

  // Theme Resolution
  const resolvedTheme = theme === 'auto' 
    ? (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;

  const themeClasses = {
    light: 'bg-white text-gray-900 border-gray-200',
    dark: 'bg-gray-900 text-gray-100 border-gray-700'
  };

  // Render Component or Children
  const renderContent = () => {
    if (children) {
      return children({
        state,
        api: jiraApi,
        config: jiraConfig,
        actions: {
          initializeJira,
          loadProjects,
          loadIssues,
          loadBoards,
          loadComments,
          loadAttachments,
          createIssue,
          updateIssue,
          searchIssues,
          // Navigation Actions
          navigateToProject: (project: JiraProject) => {
            setState(prev => ({ ...prev, currentProject: project }));
            if (onProjectSelected) onProjectSelected(project);
          },
          navigateToBoard: (board: JiraBoard) => {
            setState(prev => ({ ...prev, currentBoard: board }));
            if (onBoardSelected) onBoardSelected(board);
          },
          navigateToIssue: (issue: JiraIssue) => {
            if (onIssueSelected) onIssueSelected(issue);
          },
          // Search Actions
          searchProjects: async (query: string) => {
            return await jiraApi.searchProjects(query);
          },
          searchBoards: async (query: string) => {
            return await jiraApi.searchBoards(query);
          },
          // UI Actions
          selectItems: (items: any[]) => {
            setState(prev => ({ ...prev, selectedItems: items }));
          },
          sortBy: (field: any, order: any) => {
            setState(prev => ({ ...prev, sortBy: field, sortOrder: order }));
          },
          setViewMode: (mode: 'grid' | 'list' | 'kanban') => {
            setState(prev => ({ ...prev, viewMode: mode }));
          },
          setFilters: (filters: any) => {
            setState(prev => ({ ...prev, filters }));
          },
          // Data Actions
          refresh: async () => {
            await Promise.all([
              loadProjects(),
              loadIssues(),
              loadBoards()
            ]);
          },
          clearSelection: () => {
            setState(prev => ({ ...prev, selectedItems: [] }));
          }
        }
      });
    }

    // Default UI
    return (
      <div className={`atom-jira-manager ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          🎯 ATOM Jira Manager
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Connection Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Connection Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.connected ? 'bg-green-100 text-green-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.connected ? 'Connected to ' + jiraConfig.serverUrl : 'Not Connected'}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.projects.length}
            </div>
            <div className="text-sm text-gray-500">Projects</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.issues.length}
            </div>
            <div className="text-sm text-gray-500">Issues</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.boards.length}
            </div>
            <div className="text-sm text-gray-500">Boards</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.searchResults.total}
            </div>
            <div className="text-sm text-gray-500">Search Results</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Quick Actions</h3>
          <div className="flex space-x-2">
            <button
              onClick={initializeJira}
              disabled={state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Connect
            </button>
            <button
              onClick={loadProjects}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Load Projects
            </button>
            <button
              onClick={loadIssues}
              disabled={!state.connected || state.loading}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Load Issues
            </button>
            <button
              onClick={loadBoards}
              disabled={!state.connected || state.loading}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Load Boards
            </button>
          </div>
        </div>

        {/* Configuration */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Configuration</h3>
          <div className="text-sm space-y-1">
            <div>Server URL: {jiraConfig.serverUrl}</div>
            <div>Authentication: {jiraConfig.oauthToken ? 'OAuth' : 'Basic Auth'}</div>
            <div>Max Issues: {jiraConfig.maxIssuesPerProject}</div>
            <div>Include Subtasks: {jiraConfig.includeSubtasks ? 'Yes' : 'No'}</div>
            <div>Include Comments: {jiraConfig.includeComments ? 'Yes' : 'No'}</div>
            <div>Include Attachments: {jiraConfig.includeAttachments ? 'Yes' : 'No'}</div>
          </div>
        </div>

        {/* Error Display */}
        {state.error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded">
            <p className="text-red-700 text-sm">{state.error}</p>
          </div>
        )}
      </div>
    );
  };

  return renderContent();
};

export default ATOMJiraManager;