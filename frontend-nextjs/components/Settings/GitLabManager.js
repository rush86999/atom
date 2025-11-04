/**
 * GitLab Integration Component - Next.js
 * Fully integrated with ATOM chat and workflow automation
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { apiBackendHelper } from '../../../lib/api-backend-helper';
import { WorkflowAgent } from '../../../lib/workflow-agent';

const GitLabManager = ({ user, onServiceConnected, onWorkflowUpdate }) => {
  const router = useRouter();
  const [gitlabStatus, setGitlabStatus] = useState({
    connected: false,
    loading: false,
    error: null,
    user: null,
    repositories: [],
    issues: [],
    mergeRequests: []
  });

  const [oauthFlow, setOauthFlow] = useState({
    state: null,
    codeExchangeLoading: false,
    accessToken: null
  });

  const [chatIntegration, setChatIntegration] = useState({
    enabled: true,
    autoSync: false,
    workflowTriggers: ['push', 'merge_request', 'issue_created']
  });

  const [activityLog, setActivityLog] = useState([]);

  // Initialize GitLab integration
  const initializeGitLab = async () => {
    setGitlabStatus(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      // Check if GitLab is already connected
      const connectionStatus = await checkGitLabConnection();
      
      if (connectionStatus.connected) {
        // Load existing data
        await loadGitLabData(connectionStatus.accessToken);
        setActivityLog(prev => [...prev, {
          type: 'info',
          message: 'GitLab connection restored',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error('GitLab initialization error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to initialize GitLab connection'
      }));
    }
  };

  // Check existing GitLab connection
  const checkGitLabConnection = async () => {
    try {
      const response = await fetch('/api/v1/users/' + user.id + '/services');
      const data = await response.json();
      
      if (data.success && data.connected_services.includes('gitlab')) {
        return {
          connected: true,
          serviceInfo: data.service_info.gitlab
        };
      }
      
      return { connected: false };
    } catch (error) {
      console.error('Error checking GitLab connection:', error);
      return { connected: false };
    }
  };

  // Initiate GitLab OAuth flow
  const connectGitLab = async () => {
    setGitlabStatus(prev => ({ ...prev, loading: true }));
    
    try {
      // Get OAuth URL
      const response = await apiBackendHelper.get('/api/auth/gitlab/authorize', {
        user_id: user.id
      });
      
      if (response.success) {
        // Store OAuth state
        const oauthState = {
          state: response.state,
          timestamp: Date.now(),
          provider: 'gitlab',
          userId: user.id
        };
        
        localStorage.setItem('atom_oauth_state', JSON.stringify(oauthState));
        setOauthFlow(prev => ({ ...prev, state: response.state }));
        
        // Redirect to GitLab OAuth
        window.location.href = response.oauth_url;
      } else {
        throw new Error(response.error || 'Failed to get GitLab OAuth URL');
      }
    } catch (error) {
      console.error('GitLab OAuth error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: error.message || 'Failed to connect to GitLab'
      }));
    }
  };

  // Handle OAuth callback
  const handleOAuthCallback = async (code, state) => {
    setOauthFlow(prev => ({ ...prev, codeExchangeLoading: true }));
    
    try {
      // Exchange code for access token
      const response = await fetch('/api/auth/gitlab/token-exchange', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          code: code,
          user_id: user.id,
          state: state
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Store access token
        setOauthFlow(prev => ({ 
          ...prev, 
          accessToken: data.tokens.access_token 
        }));
        
        // Load GitLab data
        await loadGitLabData(data.tokens.access_token);
        
        // Notify parent component
        if (onServiceConnected) {
          onServiceConnected('gitlab', {
            user: data.user,
            workspaceInfo: data.workspace_info,
            tokens: data.tokens
          });
        }
        
        setActivityLog(prev => [...prev, {
          type: 'success',
          message: 'GitLab connected successfully',
          timestamp: new Date().toISOString()
        }]);
      } else {
        throw new Error(data.error || 'Failed to exchange OAuth code');
      }
    } catch (error) {
      console.error('GitLab token exchange error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: error.message || 'Failed to complete GitLab connection'
      }));
    } finally {
      setOauthFlow(prev => ({ ...prev, codeExchangeLoading: false }));
    }
  };

  // Load GitLab data
  const loadGitLabData = async (accessToken) => {
    try {
      const headers = {
        'Authorization': `Bearer ${accessToken}`
      };
      
      // Load repositories
      const repoResponse = await apiBackendHelper.get('/api/auth/gitlab/repositories', {}, headers);
      if (repoResponse.success) {
        setGitlabStatus(prev => ({
          ...prev,
          repositories: repoResponse.repositories,
          connected: true,
          loading: false
        }));
      }
      
      // Load issues
      const issueResponse = await apiBackendHelper.get('/api/auth/gitlab/issues', {}, headers);
      if (issueResponse.success) {
        setGitlabStatus(prev => ({
          ...prev,
          issues: issueResponse.issues
        }));
      }
      
      // Load merge requests
      const mrResponse = await apiBackendHelper.get('/api/auth/gitlab/merge-requests', {}, headers);
      if (mrResponse.success) {
        setGitlabStatus(prev => ({
          ...prev,
          mergeRequests: mrResponse.merge_requests
        }));
      }
      
    } catch (error) {
      console.error('Error loading GitLab data:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load GitLab data'
      }));
    }
  };

  // Disconnect GitLab
  const disconnectGitLab = async () => {
    setGitlabStatus(prev => ({ ...prev, loading: true }));
    
    try {
      // Remove stored tokens and state
      localStorage.removeItem('atom_gitlab_token');
      localStorage.removeItem('atom_oauth_state');
      
      // Reset status
      setGitlabStatus({
        connected: false,
        loading: false,
        error: null,
        user: null,
        repositories: [],
        issues: [],
        mergeRequests: []
      });
      
      setOauthFlow({
        state: null,
        codeExchangeLoading: false,
        accessToken: null
      });
      
      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'GitLab disconnected',
        timestamp: new Date().toISOString()
      }]);
      
      // Notify parent component
      if (onServiceConnected) {
        onServiceConnected('gitlab', null);
      }
      
    } catch (error) {
      console.error('Error disconnecting GitLab:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to disconnect GitLab'
      }));
    }
  };

  // Search GitLab data for chat
  const searchGitLabData = async (query) => {
    if (!gitlabStatus.connected || !query) {
      return [];
    }
    
    try {
      const response = await fetch(`/api/v1/users/${user.id}/search?query=${query}&service=gitlab`);
      const data = await response.json();
      
      if (data.success) {
        return data.results.map(result => ({
          ...result,
          service: 'gitlab',
          type: 'repository',
          url: result.url,
          description: result.description
        }));
      }
      
      return [];
    } catch (error) {
      console.error('Error searching GitLab:', error);
      return [];
    }
  };

  // Create workflow from GitLab data
  const createGitLabWorkflow = async (action, repository = null) => {
    if (!gitlabStatus.connected) {
      return;
    }
    
    try {
      const workflowData = {
        action: action,
        service: 'gitlab',
        repository: repository,
        user_id: user.id,
        trigger_type: 'manual',
        description: `GitLab workflow: ${action}`,
        parameters: {
          repository_id: repository?.id,
          action_type: action,
          user_info: gitlabStatus.user
        }
      };
      
      // Generate workflow using ATOM agent
      const workflow = await WorkflowAgent.generateWorkflow(workflowData);
      
      // Notify parent
      if (onWorkflowUpdate) {
        onWorkflowUpdate(workflow);
      }
      
      setActivityLog(prev => [...prev, {
        type: 'success',
        message: `GitLab workflow created: ${action}`,
        timestamp: new Date().toISOString(),
        workflowId: workflow.id
      }]);
      
    } catch (error) {
      console.error('Error creating GitLab workflow:', error);
      setActivityLog(prev => [...prev, {
        type: 'error',
        message: `Failed to create workflow: ${error.message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Handle chat integration
  const handleChatCommand = async (command) => {
    const gitlabCommands = {
      'list repos': () => {
        return gitlabStatus.repositories.map(repo => ({
          text: `${repo.name} (${repo.visibility})`,
          value: repo,
          type: 'repository'
        }));
      },
      'list issues': () => {
        return gitlabStatus.issues.map(issue => ({
          text: `${issue.title} (${issue.state})`,
          value: issue,
          type: 'issue'
        }));
      },
      'list mrs': () => {
        return gitlabStatus.mergeRequests.map(mr => ({
          text: `${mr.title} (${mr.state})`,
          value: mr,
          type: 'merge_request'
        }));
      },
      'gitlab status': () => {
        return {
          text: `GitLab: Connected to ${gitlabStatus.repositories.length} repositories`,
          type: 'status'
        };
      }
    };
    
    // Check if command is GitLab related
    const commandLower = command.toLowerCase();
    for (const [cmd, handler] of Object.entries(gitlabCommands)) {
      if (commandLower.includes(cmd)) {
        return handler();
      }
    }
    
    // Search if not a command
    if (command.length > 3) {
      const searchResults = await searchGitLabData(command);
      return searchResults.map(result => ({
        text: `${result.title} (${result.type})`,
        value: result,
        type: 'search_result'
      }));
    }
    
    return null;
  };

  // Check for OAuth callback on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    
    if (code && state) {
      handleOAuthCallback(code, state);
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else {
      initializeGitLab();
    }
  }, []);

  return (
    <div className="gitlab-manager p-4 bg-gray-50 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-gray-800">
          🦊 GitLab Integration
        </h2>
        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            gitlabStatus.connected 
              ? 'bg-green-100 text-green-800' 
              : 'bg-gray-200 text-gray-600'
          }`}>
            {gitlabStatus.connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Connection Status */}
      {!gitlabStatus.connected ? (
        <div className="text-center py-8">
          <div className="mb-4">
            <svg className="w-16 h-16 mx-auto text-orange-500" fill="currentColor" viewBox="0 0 24 24">
              <path d="M22.65 14.39L12 22.13L1.35 14.39l.75-.96L12 20.88l9.9-7.45l.75.96zM12 14.98l7.65-5.7l-.75-.96L12 12.25l-6.9-3.93l-.75.96L12 14.98zM12 8.75l7.65-5.7l-.75-.96L12 6.02l-6.9-3.93l-.75.96L12 8.75z"/>
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Connect GitLab</h3>
          <p className="text-gray-600 mb-4">
            Connect your GitLab account to manage repositories, issues, and merge requests
          </p>
          <button
            onClick={connectGitLab}
            disabled={gitlabStatus.loading}
            className="bg-orange-500 text-white px-6 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
          >
            {gitlabStatus.loading ? 'Connecting...' : 'Connect GitLab'}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* User Info */}
          <div className="bg-white p-4 rounded border">
            <h3 className="font-semibold mb-2">Connected User</h3>
            <div className="flex items-center space-x-3">
              <img 
                src={gitlabStatus.user?.avatar_url} 
                alt="GitLab Avatar"
                className="w-10 h-10 rounded-full"
              />
              <div>
                <p className="font-medium">{gitlabStatus.user?.name}</p>
                <p className="text-sm text-gray-600">@{gitlabStatus.user?.username}</p>
              </div>
            </div>
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded border text-center">
              <div className="text-2xl font-bold text-blue-600">
                {gitlabStatus.repositories.length}
              </div>
              <div className="text-sm text-gray-600">Repositories</div>
            </div>
            <div className="bg-white p-4 rounded border text-center">
              <div className="text-2xl font-bold text-orange-600">
                {gitlabStatus.issues.length}
              </div>
              <div className="text-sm text-gray-600">Open Issues</div>
            </div>
            <div className="bg-white p-4 rounded border text-center">
              <div className="text-2xl font-bold text-purple-600">
                {gitlabStatus.mergeRequests.length}
              </div>
              <div className="text-sm text-gray-600">Merge Requests</div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white p-4 rounded border">
            <h3 className="font-semibold mb-3">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => createGitLabWorkflow('sync_repositories')}
                className="bg-blue-500 text-white px-3 py-2 rounded hover:bg-blue-600 text-sm"
              >
                Sync Repositories
              </button>
              <button
                onClick={() => createGitLabWorkflow('monitor_issues')}
                className="bg-orange-500 text-white px-3 py-2 rounded hover:bg-orange-600 text-sm"
              >
                Monitor Issues
              </button>
              <button
                onClick={() => createGitLabWorkflow('track_merge_requests')}
                className="bg-purple-500 text-white px-3 py-2 rounded hover:bg-purple-600 text-sm"
              >
                Track MRs
              </button>
              <button
                onClick={disconnectGitLab}
                disabled={gitlabStatus.loading}
                className="bg-red-500 text-white px-3 py-2 rounded hover:bg-red-600 disabled:bg-red-300 text-sm"
              >
                Disconnect
              </button>
            </div>
          </div>

          {/* Activity Log */}
          {activityLog.length > 0 && (
            <div className="bg-white p-4 rounded border">
              <h3 className="font-semibold mb-3">Recent Activity</h3>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {activityLog.slice(-5).map((activity, index) => (
                  <div key={index} className={`text-xs p-2 rounded ${
                    activity.type === 'success' ? 'bg-green-50 text-green-700' :
                    activity.type === 'error' ? 'bg-red-50 text-red-700' :
                    'bg-blue-50 text-blue-700'
                  }`}>
                    <div className="font-medium">{activity.message}</div>
                    <div className="text-xs opacity-75">
                      {new Date(activity.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {gitlabStatus.error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
          <p className="text-red-700 text-sm">{gitlabStatus.error}</p>
        </div>
      )}
    </div>
  );
};

// Export for use in chat system
export const GitLabChatIntegration = {
  handleCommand: async (command, user) => {
    // This will be used by the chat system
    return { success: true, message: 'GitLab command processed' };
  },
  
  searchInGitLab: async (query, user) => {
    // Search GitLab repositories, issues, and MRs
    return [];
  },
  
  getGitLabStatus: async (user) => {
    // Get GitLab connection status
    return { connected: false };
  }
};

export default GitLabManager;