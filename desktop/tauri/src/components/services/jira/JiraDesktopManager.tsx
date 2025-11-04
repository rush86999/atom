/**
 * Jira Integration Component - Tauri Desktop
 * Fully integrated with ATOM desktop app and workflow automation
 */

import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

interface JiraUser {
  accountId: string;
  displayName: string;
  emailAddress: string;
  avatarUrls: Record<string, string>;
}

interface JiraProject {
  id: string;
  key: string;
  name: string;
  projectTypeKey: string;
  avatarUrls: Record<string, string>;
}

interface JiraIssue {
  id: string;
  key: string;
  summary: string;
  description: string;
  status: string;
  assignee: string;
  reporter: string;
  created: string;
  updated: string;
}

interface JiraStatus {
  connected: boolean;
  loading: boolean;
  error: string | null;
  user: JiraUser | null;
  projects: JiraProject[];
  issues: JiraIssue[];
  accessibleResources: any[];
}

interface OAuthFlow {
  state: string | null;
  codeExchangeLoading: boolean;
  accessToken: string | null;
}

interface DesktopFeatures {
  nativeNotifications: boolean;
  systemTray: boolean;
  autoStart: boolean;
  backgroundSync: boolean;
}

interface ActivityLog {
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  timestamp: string;
}

interface JiraDesktopManagerProps {
  user: any;
  onServiceConnected: (service: string, status: boolean) => void;
  onWorkflowUpdate: (workflow: any) => void;
}

const JiraDesktopManager: React.FC<JiraDesktopManagerProps> = ({
  user,
  onServiceConnected,
  onWorkflowUpdate
}) => {
  const [jiraStatus, setJiraStatus] = useState<JiraStatus>({
    connected: false,
    loading: false,
    error: null,
    user: null,
    projects: [],
    issues: [],
    accessibleResources: []
  });

  const [oauthFlow, setOauthFlow] = useState<OAuthFlow>({
    state: null,
    codeExchangeLoading: false,
    accessToken: null
  });

  const [desktopFeatures, setDesktopFeatures] = useState<DesktopFeatures>({
    nativeNotifications: true,
    systemTray: true,
    autoStart: true,
    backgroundSync: false
  });

  const [activityLog, setActivityLog] = useState<ActivityLog[]>([]);

  // Initialize Jira for desktop
  const initializeDesktopJira = async () => {
    setJiraStatus(prev => ({ ...prev, loading: true, error: null }));

    try {
      // Check backend connection
      const backendConnected = await checkBackendConnection();
      if (!backendConnected) {
        throw new Error('Backend connection failed');
      }

      // Check if Jira is already connected
      const connectionStatus = await checkJiraConnection();

      if (connectionStatus.connected) {
        // Load existing data
        await loadDesktopJiraData(connectionStatus.accessToken);

        // Setup desktop features
        await setupDesktopFeatures(connectionStatus.accessToken);

        setActivityLog(prev => [...prev, {
          type: 'success',
          message: 'Jira desktop integration initialized',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error('Desktop Jira initialization error:', error);
      setJiraStatus(prev => ({
        ...prev,
        loading: false,
        error: `Desktop initialization failed: ${(error as Error).message}`
      }));
    }
  };

  // Check backend connection
  const checkBackendConnection = async (): Promise<boolean> => {
    try {
      const response = await invoke('check_backend_connection');
      return (response as any).status === 'healthy';
    } catch (error) {
      console.error('Backend connection check failed:', error);
      return false;
    }
  };

  // Check existing Jira connection
  const checkJiraConnection = async (): Promise<any> => {
    try {
      const response = await invoke('get_jira_connection', {
        userId: user.id
      });
      return response;
    } catch (error) {
      console.error('Error checking Jira connection:', error);
      return { connected: false };
    }
  };

  // Connect Jira (Desktop)
  const connectDesktopJira = async () => {
    setJiraStatus(prev => ({ ...prev, loading: true }));

    try {
      // Get OAuth URL from backend
      const response = await invoke('get_jira_oauth_url', {
        userId: user.id
      });

      if ((response as any).success) {
        // Store OAuth state securely in desktop storage
        const oauthState = {
          state: (response as any).state,
          timestamp: Date.now(),
          provider: 'jira',
          userId: user.id
        };

        await invoke('store_oauth_state', { state: oauthState });
        setOauthFlow(prev => ({ ...prev, state: (response as any).state }));

        // Open system browser for OAuth
        await invoke('open_browser', { url: (response as any).oauth_url });

        // Listen for OAuth callback
        await setupOAuthCallbackListener();
      } else {
        throw new Error((response as any).error || 'Failed to get Jira OAuth URL');
      }
    } catch (error) {
      console.error('Desktop Jira OAuth error:', error);
      setJiraStatus(prev => ({
        ...prev,
        loading: false,
        error: `Desktop OAuth failed: ${(error as Error).message}`
      }));
    }
  };

  // Setup OAuth callback listener
  const setupOAuthCallbackListener = async () => {
    try {
      await listen('jira_oauth_callback', (event: any) => {
        const { code, state } = event.payload;
        handleOAuthCallback(code, state);
      });
    } catch (error) {
      console.error('Error setting up OAuth callback listener:', error);
    }
  };

  // Handle OAuth callback
  const handleOAuthCallback = async (code: string, state: string) => {
    setOauthFlow(prev => ({ ...prev, codeExchangeLoading: true }));

    try {
      // Exchange code for access token
      const tokenResponse = await invoke('exchange_jira_oauth_code', {
        code,
        state,
        userId: user.id
      });

      if ((tokenResponse as any).success) {
        const accessToken = (tokenResponse as any).access_token;
        setOauthFlow(prev => ({ ...prev, accessToken, codeExchangeLoading: false }));

        // Load Jira data
        await loadDesktopJiraData(accessToken);

        // Setup desktop features
        await setupDesktopFeatures(accessToken);

        // Notify parent component
        onServiceConnected('jira', true);

        setActivityLog(prev => [...prev, {
          type: 'success',
          message: 'Jira OAuth completed successfully',
          timestamp: new Date().toISOString()
        }]);
      } else {
        throw new Error((tokenResponse as any).error || 'Failed to exchange OAuth code');
      }
    } catch (error) {
      console.error('OAuth callback handling error:', error);
      setOauthFlow(prev => ({ ...prev, codeExchangeLoading: false }));
      setActivityLog(prev => [...prev, {
        type: 'error',
        message: `OAuth callback failed: ${(error as Error).message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Setup desktop features
  const setupDesktopFeatures = async (accessToken: string) => {
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
        message: `Desktop features setup incomplete: ${(error as Error).message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Setup system tray
  const setupSystemTray = async (accessToken: string) => {
    try {
      await invoke('setup_jira_tray', {
        accessToken,
        updateInterval: 300000 // 5 minutes
      });

      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'Jira system tray integration enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('System tray setup error:', error);
    }
  };

  // Setup native notifications
  const setupNativeNotifications = async (accessToken: string) => {
    try {
      await invoke('setup_jira_notifications', {
        accessToken,
        events: ['issue_created', 'issue_updated', 'issue_assigned']
      });

      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'Jira native notifications enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Native notifications setup error:', error);
    }
  };

  // Setup background sync
  const setupBackgroundSync = async (accessToken: string) => {
    try {
      await invoke('setup_jira_background_sync', {
        accessToken,
        syncInterval: 600000 // 10 minutes
      });

      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'Jira background sync enabled',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Background sync setup error:', error);
    }
  };

  // Load Jira data for desktop
  const loadDesktopJiraData = async (accessToken: string) => {
    try {
      // Get accessible resources
      const resources = await invoke('get_jira_resources', { accessToken });

      // Load projects for first resource
      if ((resources as any).resources && (resources as any).resources.length > 0) {
        const firstResource = (resources as any).resources[0];
        const projects = await invoke('get_jira_projects', {
          accessToken,
          cloudId: firstResource.cloud_id
        });

        // Load recent issues
        const issues = await invoke('get_jira_issues', {
          accessToken,
          cloudId: firstResource.cloud_id,
          projectKey: (projects as any).projects[0]?.key
        });

        // Get user info
        const userInfo = await invoke('get_jira_user_info', { accessToken });

        setJiraStatus({
          connected: true,
          loading: false,
          error: null,
          user: userInfo as JiraUser,
          projects: (projects as any).projects || [],
          issues: (issues as any).issues || [],
          accessibleResources: (resources as any).resources || []
        });
      }

    } catch (error) {
      console.error('Error loading desktop Jira data:', error);
      setJiraStatus(prev => ({
        ...prev,
        loading: false,
        error: `Failed to load Jira data: ${(error as Error).message}`
      }));
    }
  };

  // Disconnect Jira
  const disconnectDesktopJira = async () => {
    try {
      await invoke('disconnect_jira', { userId: user.id });

      setJiraStatus({
        connected: false,
        loading: false,
        error: null,
        user: null,
        projects: [],
        issues: [],
        accessibleResources: []
      });

      setOauthFlow({
        state: null,
        codeExchangeLoading: false,
        accessToken: null
      });

      onServiceConnected('jira', false);

      setActivityLog(prev => [...prev, {
        type: 'info',
        message: 'Jira disconnected successfully',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Error disconnecting Jira:', error);
      setActivityLog(prev => [...prev, {
        type: 'error',
        message: `Failed to disconnect Jira: ${(error as Error).message}`,
        timestamp: new Date().toISOString()
      }]);
    }
  };

  // Create Jira issue
  const createJiraIssue = async (projectKey: string, summary: string, description: string) => {
    try {
      const response = await invoke('create_jira_issue', {
        accessToken: oauthFlow.accessToken,
        cloudId: jiraStatus.accessibleResources[0]?.cloud_id,
        projectKey,
        summary,
        description
      });

      if ((response as any).success) {
        setActivityLog(prev => [...prev, {
          type: 'success',
          message: `Created issue: ${summary}`,
          timestamp: new Date().toISOString()
        }]);

        // Refresh issues
        await loadDesktopJiraData(oauthFlow.accessToken!);
      }

      return response;
    } catch (error) {
      console.error('Error creating Jira issue:', error);
      setActivityLog(prev => [...prev, {
        type: 'error',
        message: `Failed to create issue: ${(error as Error).message}`,
        timestamp: new Date().toISOString()
      }]);
      throw error;
    }
  };

  // Search Jira issues
  const searchJiraIssues = async (query: string, projectKey?: string) => {
    try {
      const response = await invoke('search_jira_issues', {
        accessToken: oauthFlow.accessToken,
        cloudId: jiraStatus.accessibleResources[0]?.cloud_id,
        query,
        projectKey
      });

      return response;
    } catch (error) {
      console.error('Error searching Jira issues:', error);
      throw error;
    }
  };

  // Initialize on component mount
  useEffect(() => {
    if (user?.id) {
      initializeDesktopJira();
    }
  }, [user?.id]);

  return (
    <div className="jira-desktop-manager">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-blue-600 font-bold text-lg">J</span>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Jira Integration</h3>
              <p className="text-sm text-gray-500">
                {jiraStatus.connected ? 'Connected to Jira Cloud' : 'Connect your Jira workspace'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {jiraStatus.loading && (
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            )}
            <span className={`px-2 py-1 text-xs rounded-full ${
              jiraStatus.connected
                ? 'bg-green-100 text-green-800'
                : 'bg-gray-100 text-gray-800'
            }`}>
              {jiraStatus.connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Connection Status */}
        {!jiraStatus.connected && (
          <div className="mb-6">
            <button
              onClick={connectDesktopJira}
              disabled={jiraStatus.loading || oauthFlow.codeExchangeLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
            >
              {oauthFlow.codeExchangeLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Connecting...</span>
                </>
              ) : (
                <>
                  <span>Connect Jira</span>
                </>
              )}
            </button>

            {jiraStatus.error && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{jiraStatus.error}</p>
              </div>
            )}
          </div>
        )}

        {/* Connected State */}
        {jiraStatus.connected && (
          <div className="space-y-6">
            {/* User Info */}
            {jiraStatus.user && (
              <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                <img
                  src={jiraStatus.user.avatarUrls['32x32']}
                  alt={jiraStatus.user.displayName}
                  className="w-8 h-8 rounded-full"
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {jiraStatus.user.displayName}
                  </p>
                  <p className="text-xs text-gray-500">
                    {jiraStatus.user.emailAddress}
                  </p>
                </div>
              </div>
            )}

            {/* Projects */}
            {jiraStatus.projects.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-3">Projects</h4>
                <div className="grid grid-cols-1 gap-2">
                  {jiraStatus.projects.slice(0, 5).map((project) => (
                    <div
                      key={project.id}
                      className="flex items-center space-x-3 p-2 bg-white border border-gray
