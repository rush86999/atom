/**
 * GitLab Integration Component - Tauri Desktop
 * Fully integrated with ATOM desktop app and workflow automation
 */

import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

const GitLabDesktopManager = ({ user, onServiceConnected, onWorkflowUpdate }) => {
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

  const [desktopFeatures, setDesktopFeatures] = useState({
    nativeNotifications: true,
    systemTray: true,
    autoStart: true,
    backgroundSync: false
  });

  const [activityLog, setActivityLog] = useState([]);

  // Initialize GitLab for desktop
  const initializeDesktopGitLab = async () => {
    setGitlabStatus(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      // Check backend connection
      const backendConnected = await checkBackendConnection();
      if (!backendConnected) {
        throw new Error('Backend connection failed');
      }

      // Check if GitLab is already connected
      const connectionStatus = await checkGitLabConnection();
      
      if (connectionStatus.connected) {
        // Load existing data
        await loadDesktopGitLabData(connectionStatus.accessToken);
        
        // Setup desktop features
        await setupDesktopFeatures(connectionStatus.accessToken);
        
        setActivityLog(prev => [...prev, {
          type: 'success',
          message: 'GitLab desktop integration initialized',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error('Desktop GitLab initialization error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: `Desktop initialization failed: ${error.message}`
      }));
    }
  };

  // Check backend connection
  const checkBackendConnection = async () => {
    try {
      const response = await invoke('check_backend_connection');
      return response.status === 'healthy';
    } catch (error) {
      console.error('Backend connection check failed:', error);
      return false;
    }
  };

  // Check existing GitLab connection
  const checkGitLabConnection = async () => {
    try {
      const response = await invoke('get_gitlab_connection', { 
        userId: user.id 
      });
      return response;
    } catch (error) {
      console.error('Error checking GitLab connection:', error);
      return { connected: false };
    }
  };

  // Connect GitLab (Desktop)
  const connectDesktopGitLab = async () => {
    setGitlabStatus(prev => ({ ...prev, loading: true }));
    
    try {
      // Get OAuth URL from backend
      const response = await invoke('get_gitlab_oauth_url', {
        userId: user.id
      });
      
      if (response.success) {
        // Store OAuth state securely in desktop storage
        const oauthState = {
          state: response.state,
          timestamp: Date.now(),
          provider: 'gitlab',
          userId: user.id
        };
        
        await invoke('store_oauth_state', { state: oauthState });
        setOauthFlow(prev => ({ ...prev, state: response.state }));
        
        // Open system browser for OAuth
        await invoke('open_browser', { url: response.oauth_url });
      } else {
        throw new Error(response.error || 'Failed to get GitLab OAuth URL');
      }
    } catch (error) {
      console.error('Desktop GitLab OAuth error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: `Desktop OAuth failed: ${error.message}`
      }));
    }
  };

  // Setup desktop features
  const setupDesktopFeatures = async (accessToken) => {
    try {
      // Setup system tray integration
      if (desktopFeatures.systemTray) {
        await setupSystemTray(accessToken);
      }
      
      // Setup native notifications
      if (desktopFeatures.nativeNotifications) {
        await setupNativeNotifications(accessToken);
      }
      
      // Setup background sync
      if (desktopFeatures.backgroundSync) {
        await setupBackgroundSync(accessToken);
      }
      
      setActivityLog(prev => [...prev, {
        type: 'success',
        message: 'Desktop features configured',
        timestamp: new Date().toISOString()
      }]);
      
    } catch (error) {
      console.error('Error setting up desktop features:', error);
      setActivityLog(prev => [...prev, {
        type: 'warning',
        message: `Desktop features setup incomplete: ${error.message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Setup system tray
  const setupSystemTray = async (accessToken) => {
    try {
      await invoke('setup_gitlab_tray', { 
        accessToken,
        updateInterval: 300000 // 5 minutes
      });
      
      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'GitLab system tray integration enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('System tray setup error:', error);
    }
  };

  // Setup native notifications
  const setupNativeNotifications = async (accessToken) => {
    try {
      await invoke('setup_gitlab_notifications', { 
        accessToken,
        events: ['issue_created', 'merge_request_opened', 'pipeline_failed']
      });
      
      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'GitLab native notifications enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Native notifications setup error:', error);
    }
  };

  // Setup background sync
  const setupBackgroundSync = async (accessToken) => {
    try {
      await invoke('setup_gitlab_background_sync', { 
        accessToken,
        syncInterval: 600000 // 10 minutes
      });
      
      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'GitLab background sync enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Background sync setup error:', error);
    }
  };

  // Load GitLab data for desktop
  const loadDesktopGitLabData = async (accessToken) => {
    try {
      // Load repositories
      const repos = await invoke('get_gitlab_repositories', { accessToken });
      
      // Load issues
      const issues = await invoke('get_gitlab_issues', { accessToken });
      
      // Load merge requests
      const mrs = await invoke('get_gitlab_merge_requests', { accessToken });
      
      // Get user info
      const userInfo = await invoke('get_gitlab_user_info', { accessToken });
      
      setGitlabStatus({
        connected: true,
        loading: false,
        error: null,
        user: userInfo,
        repositories: repos.repositories || [],
        issues: issues.issues || [],
        mergeRequests: mrs.merge_requests || []
      });
      
    } catch (error) {
      console.error('Error loading desktop GitLab data:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: `Data loading failed: ${error.message}`
      }));
    }
  };

  // Handle OAuth callback (Desktop)
  const handleDesktopOAuthCallback = async (code, state) => {
    setOauthFlow(prev => ({ ...prev, codeExchangeLoading: true }));
    
    try {
      const result = await invoke('exchange_gitlab_oauth_code', {
        code: code,
        state: state,
        userId: user.id
      });
      
      if (result.success) {
        // Store access token securely
        await invoke('store_gitlab_token', { 
          token: result.tokens.access_token,
          userId: user.id 
        });
        
        setOauthFlow(prev => ({ 
          ...prev, 
          accessToken: result.tokens.access_token 
        }));
        
        // Load GitLab data
        await loadDesktopGitLabData(result.tokens.access_token);
        
        // Setup desktop features
        await setupDesktopFeatures(result.tokens.access_token);
        
        // Notify parent component
        if (onServiceConnected) {
          onServiceConnected('gitlab', {
            user: result.user_info,
            workspaceInfo: result.workspace_info,
            tokens: result.tokens
          });
        }
        
        setActivityLog(prev => [...prev, {
          type: 'success',
          message: 'GitLab desktop connected successfully',
          timestamp: new Date().toISOString()
        }]);
      } else {
        throw new Error(result.error || 'Failed to exchange OAuth code');
      }
    } catch (error) {
      console.error('Desktop OAuth token exchange error:', error);
      setGitlabStatus(prev => ({
        ...prev,
        loading: false,
        error: `OAuth exchange failed: ${error.message}`
      }));
    } finally {
      setOauthFlow(prev => ({ ...prev, codeExchangeLoading: false }));
    }
  };

  // Create desktop workflow
  const createDesktopWorkflow = async (action, repository = null) => {
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
        description: `GitLab desktop workflow: ${action}`,
        parameters: {
          repository_id: repository?.id,
          action_type: action,
          user_info: gitlabStatus.user,
          desktop_features: desktopFeatures
        }
      };
      
      // Generate workflow using desktop agent
      const workflow = await invoke('generate_desktop_workflow', { 
        workflowData 
      });
      
      // Execute workflow
      const execution = await invoke('execute_desktop_workflow', { 
        workflow,
        service: 'gitlab'
      });
      
      // Notify parent
      if (onWorkflowUpdate) {
        onWorkflowUpdate(workflow);
      }
      
      setActivityLog(prev => [...prev, {
        type: 'success',
        message: `GitLab desktop workflow executed: ${action}`,
        timestamp: new Date().toISOString(),
        workflowId: workflow.id,
        executionId: execution.id
      }]);
      
    } catch (error) {
      console.error('Desktop workflow creation error:', error);
      setActivityLog(prev => [...prev, {
        type: 'error',
        message: `Desktop workflow failed: ${error.message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Toggle desktop features
  const toggleDesktopFeature = async (feature, value) => {
    setDesktopFeatures(prev => ({ ...prev, [feature]: value }));
    
    try {
      if (feature === 'backgroundSync') {
        if (value) {
          await setupBackgroundSync(oauthFlow.accessToken);
        } else {
          await invoke('stop_gitlab_background_sync');
        }
      }
      
      if (feature === 'systemTray') {
        if (value) {
          await setupSystemTray(oauthFlow.accessToken);
        } else {
          await invoke('remove_gitlab_tray');
        }
      }
      
      if (feature === 'nativeNotifications') {
        if (value) {
          await setupNativeNotifications(oauthFlow.accessToken);
        } else {
          await invoke('stop_gitlab_notifications');
        }
      }
      
    } catch (error) {
      console.error(`Error toggling ${feature}:`, error);
    }
  };

  // Listen for OAuth callback events
  useEffect(() => {
    const unlisten = listen('gitlab-oauth-callback', (event) => {
      const { code, state } = event.payload;
      handleDesktopOAuthCallback(code, state);
    });
    
    return () => {
      unlisten.then(unlistener => unlistener());
    };
  }, [user]);

  // Initialize on mount
  useEffect(() => {
    initializeDesktopGitLab();
  }, []);

  return (
    <div className="gitlab-desktop-manager p-4 bg-gray-50 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-gray-800">
          🦊 GitLab Desktop Integration
        </h2>
        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            gitlabStatus.connected 
              ? 'bg-green-100 text-green-800' 
              : 'bg-gray-200 text-gray-600'
          }`}>
            {gitlabStatus.connected ? 'Desktop Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Desktop Features Status */}
      <div className="bg-white p-4 rounded border mb-4">
        <h3 className="font-semibold mb-3">Desktop Features</h3>
        <div className="space-y-2">
          <label className="flex items-center justify-between">
            <span className="text-sm">Native Notifications</span>
            <input
              type="checkbox"
              checked={desktopFeatures.nativeNotifications}
              onChange={(e) => toggleDesktopFeature('nativeNotifications', e.target.checked)}
              className="rounded"
            />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm">System Tray Integration</span>
            <input
              type="checkbox"
              checked={desktopFeatures.systemTray}
              onChange={(e) => toggleDesktopFeature('systemTray', e.target.checked)}
              className="rounded"
            />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm">Background Sync</span>
            <input
              type="checkbox"
              checked={desktopFeatures.backgroundSync}
              onChange={(e) => toggleDesktopFeature('backgroundSync', e.target.checked)}
              className="rounded"
            />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm">Start with System</span>
            <input
              type="checkbox"
              checked={desktopFeatures.autoStart}
              onChange={(e) => setDesktopFeatures(prev => ({ ...prev, autoStart: e.target.checked }))}
              className="rounded"
            />
          </label>
        </div>
      </div>

      {/* Connection UI - similar to web version but with desktop features */}
      {!gitlabStatus.connected ? (
        <div className="text-center py-8">
          <div className="mb-4">
            <div className="w-16 h-16 mx-auto bg-orange-100 rounded-full flex items-center justify-center">
              <span className="text-2xl">🦊</span>
            </div>
          </div>
          <h3 className="text-lg font-semibold mb-2">Connect GitLab Desktop</h3>
          <p className="text-gray-600 mb-4">
            Connect your GitLab account with desktop features including notifications, system tray, and background sync
          </p>
          <button
            onClick={connectDesktopGitLab}
            disabled={gitlabStatus.loading}
            className="bg-orange-500 text-white px-6 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
          >
            {gitlabStatus.loading ? 'Connecting...' : 'Connect GitLab Desktop'}
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

          {/* Desktop Status */}
          <div className="bg-white p-4 rounded border">
            <h3 className="font-semibold mb-2">Desktop Features Status</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className={`p-2 rounded ${
                desktopFeatures.nativeNotifications ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-500'
              }`}>
                Notifications: {desktopFeatures.nativeNotifications ? 'Active' : 'Inactive'}
              </div>
              <div className={`p-2 rounded ${
                desktopFeatures.systemTray ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-500'
              }`}>
                System Tray: {desktopFeatures.systemTray ? 'Active' : 'Inactive'}
              </div>
              <div className={`p-2 rounded ${
                desktopFeatures.backgroundSync ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-500'
              }`}>
                Background Sync: {desktopFeatures.backgroundSync ? 'Active' : 'Inactive'}
              </div>
              <div className={`p-2 rounded ${
                desktopFeatures.autoStart ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-500'
              }`}>
                Auto Start: {desktopFeatures.autoStart ? 'Enabled' : 'Disabled'}
              </div>
            </div>
          </div>

          {/* Statistics and Actions - reuse from web component */}
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

          {/* Desktop-specific Actions */}
          <div className="bg-white p-4 rounded border">
            <h3 className="font-semibold mb-3">Desktop Actions</h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => createDesktopWorkflow('enable_desktop_notifications')}
                className="bg-green-500 text-white px-3 py-2 rounded hover:bg-green-600 text-sm"
              >
                Enable Notifications
              </button>
              <button
                onClick={() => createDesktopWorkflow('start_background_sync')}
                className="bg-blue-500 text-white px-3 py-2 rounded hover:bg-blue-600 text-sm"
              >
                Start Background Sync
              </button>
              <button
                onClick={() => createDesktopWorkflow('open_in_system_tray')}
                className="bg-purple-500 text-white px-3 py-2 rounded hover:bg-purple-600 text-sm"
              >
                Add to System Tray
              </button>
              <button
                onClick={() => createDesktopWorkflow('sync_all_data')}
                className="bg-orange-500 text-white px-3 py-2 rounded hover:bg-orange-600 text-sm"
              >
                Sync All Data
              </button>
            </div>
          </div>

          {/* Activity Log */}
          {activityLog.length > 0 && (
            <div className="bg-white p-4 rounded border">
              <h3 className="font-semibold mb-3">Desktop Activity</h3>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {activityLog.slice(-5).map((activity, index) => (
                  <div key={index} className={`text-xs p-2 rounded ${
                    activity.type === 'success' ? 'bg-green-50 text-green-700' :
                    activity.type === 'error' ? 'bg-red-50 text-red-700' :
                    activity.type === 'warning' ? 'bg-yellow-50 text-yellow-700' :
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

export default GitLabDesktopManager;