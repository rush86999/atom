/**
 * ATOM Jira Complete OAuth Flow Implementation
 * Frontend component for complete Jira OAuth integration
 */

import React, { useState, useEffect, useCallback } from 'react';
import { JiraResources, JiraProject, JiraIssue, JiraIntegrationStatus } from '../types/jira';

interface JiraOAuthFlowProps {
  onIntegrationComplete?: (status: JiraIntegrationStatus) => void;
  onError?: (error: string) => void;
  onResourcesDiscovered?: (resources: JiraResources[]) => void;
  className?: string;
}

export const JiraOAuthFlow: React.FC<JiraOAuthFlowProps> = ({
  onIntegrationComplete,
  onError,
  onResourcesDiscovered,
  className = ''
}) => {
  const [oauthState, setOAuthState] = useState({
    status: 'idle' as 'idle' | 'loading' | 'success' | 'error',
    step: '' as string,
    authUrl: '',
    resources: [] as JiraResources[],
    selectedResource: null as JiraResources | null,
    projects: [] as JiraProject[],
    issues: [] as JiraIssue[]
  });

  const [userData, setUserData] = useState({
    userId: 'user_' + Date.now(),
    cloudId: '',
    accessToken: '',
    refreshToken: ''
  });

  // Base API configuration
  const apiConfig = {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
    endpoints: {
      startOAuth: '/api/auth/jira/start',
      getResources: '/api/auth/jira/resources',
      getProjects: '/api/auth/jira/{cloud_id}/projects',
      revoke: '/api/auth/jira/{cloud_id}'
    }
  };

  // Build API URL
  const buildApiUrl = (endpoint: string, params: Record<string, string> = {}): string => {
    let url = `${apiConfig.baseUrl}${endpoint}`;
    
    // Replace path parameters
    Object.keys(params).forEach(key => {
      url = url.replace(`{${key}}`, params[key]);
    });
    
    // Add query parameters
    const searchParams = new URLSearchParams();
    Object.keys(params).forEach(key => {
      if (!endpoint.includes(`{${key}}`)) {
        searchParams.append(key, params[key]);
      }
    });
    
    if (searchParams.toString()) {
      url += (url.includes('?') ? '&' : '?') + searchParams.toString();
    }
    
    return url;
  };

  // Start OAuth flow
  const startOAuthFlow = useCallback(async () => {
    try {
      setOAuthState(prev => ({
        ...prev,
        status: 'loading',
        step: 'Starting OAuth flow...'
      }));

      // Step 1: Get OAuth URL
      console.log('🔗 Getting OAuth authorization URL...');
      const startUrl = buildApiUrl(apiConfig.endpoints.startOAuth);
      const response = await fetch(`${startUrl}?user_id=${userData.userId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`OAuth start failed: ${response.status} - ${response.statusText}`);
      }

      const authData = await response.json();
      console.log('✅ OAuth URL received:', authData);

      setOAuthState(prev => ({
        ...prev,
        step: 'Redirecting to authorization...',
        authUrl: authData.auth_url
      }));

      // Step 2: Redirect to authorization
      window.location.href = authData.auth_url;

    } catch (error) {
      console.error('❌ OAuth flow error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      setOAuthState(prev => ({
        ...prev,
        status: 'error',
        step: `OAuth flow failed: ${errorMessage}`
      }));

      if (onError) {
        onError(errorMessage);
      }
    }
  }, [userData.userId, onError]);

  // Handle OAuth callback
  const handleOAuthCallback = useCallback(async (code: string, state: string) => {
    try {
      setOAuthState(prev => ({
        ...prev,
        status: 'loading',
        step: 'Processing OAuth callback...'
      }));

      console.log('📩 Processing OAuth callback...');
      
      // The callback is handled by the backend, which will:
      // 1. Exchange code for tokens
      // 2. Get accessible resources
      // 3. Store encrypted tokens
      // 4. Redirect to success/error page

      // We just need to show a loading state while backend processes
      setOAuthState(prev => ({
        ...prev,
        step: 'Exchanging authorization code for tokens...'
      }));

    } catch (error) {
      console.error('❌ OAuth callback error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Callback processing failed';
      
      setOAuthState(prev => ({
        ...prev,
        status: 'error',
        step: errorMessage
      }));

      if (onError) {
        onError(errorMessage);
      }
    }
  }, [onError]);

  // Load discovered resources
  const loadResources = useCallback(async () => {
    try {
      setOAuthState(prev => ({
        ...prev,
        status: 'loading',
        step: 'Loading accessible Jira resources...'
      }));

      console.log('🌐 Loading Jira resources...');
      
      const resourcesUrl = buildApiUrl(apiConfig.endpoints.getResources);
      const response = await fetch(`${resourcesUrl}?user_id=${userData.userId}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load resources: ${response.status} - ${response.statusText}`);
      }

      const resourcesData = await response.json();
      console.log('✅ Resources loaded:', resourcesData);

      setOAuthState(prev => ({
        ...prev,
        step: 'Resources loaded successfully',
        resources: resourcesData.resources
      }));

      if (onResourcesDiscovered) {
        onResourcesDiscovered(resourcesData.resources);
      }

      // Auto-select first resource if available
      if (resourcesData.resources.length > 0) {
        handleResourceSelect(resourcesData.resources[0]);
      }

    } catch (error) {
      console.error('❌ Resource loading error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Resource loading failed';
      
      setOAuthState(prev => ({
        ...prev,
        status: 'error',
        step: errorMessage
      }));

      if (onError) {
        onError(errorMessage);
      }
    }
  }, [userData.userId, onResourcesDiscovered, onError]);

  // Handle resource selection
  const handleResourceSelect = useCallback(async (resource: JiraResources) => {
    try {
      setOAuthState(prev => ({
        ...prev,
        status: 'loading',
        step: `Loading projects from ${resource.name}...`,
        selectedResource: resource
      }));

      console.log('🏢 Loading projects from:', resource.cloud_id);

      // Load projects for this resource
      const projectsUrl = buildApiUrl(apiConfig.endpoints.getProjects, {
        cloud_id: resource.cloud_id,
        user_id: userData.userId
      });

      const response = await fetch(projectsUrl, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load projects: ${response.status} - ${response.statusText}`);
      }

      const projectsData = await response.json();
      console.log('✅ Projects loaded:', projectsData);

      // Parse discovery data
      const discovery = resource.discovery || {};
      const projects = discovery.projects || [];
      const issues = discovery.issues || [];

      setOAuthState(prev => ({
        ...prev,
        step: 'Projects and issues loaded successfully',
        projects: projects,
        issues: issues
      }));

      // Report completion
      const integrationStatus: JiraIntegrationStatus = {
        connected: true,
        resourceId: resource.cloud_id,
        resourceName: resource.name,
        projectCount: projects.length,
        issueCount: issues.length,
        lastSync: new Date().toISOString(),
        status: 'active'
      };

      if (onIntegrationComplete) {
        onIntegrationComplete(integrationStatus);
      }

      // Set final success state
      setOAuthState(prev => ({
        ...prev,
        status: 'success',
        step: 'Integration completed successfully'
      }));

    } catch (error) {
      console.error('❌ Project loading error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Project loading failed';
      
      setOAuthState(prev => ({
        ...prev,
        status: 'error',
        step: errorMessage
      }));

      if (onError) {
        onError(errorMessage);
      }
    }
  }, [userData.userId, onIntegrationComplete, onError]);

  // Check URL parameters for OAuth callback
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');
      const error = urlParams.get('error');

      if (code && state) {
        // OAuth callback received
        handleOAuthCallback(code, state);
      } else if (error) {
        // OAuth error
        const errorDescription = urlParams.get('description');
        const errorMessage = `OAuth error: ${error} - ${errorDescription || 'Unknown error'}`;
        
        setOAuthState(prev => ({
          ...prev,
          status: 'error',
          step: errorMessage
        }));

        if (onError) {
          onError(errorMessage);
        }
      }
    }
  }, [handleOAuthCallback, onError]);

  // Auto-load resources if user comes back from success
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const success = urlParams.get('success');
      
      if (success === 'true') {
        // User successfully completed OAuth, load resources
        setTimeout(() => {
          loadResources();
        }, 1000); // Brief delay to allow backend processing
      }
    }
  }, [loadResources]);

  // Render status based on current state
  const renderStatus = () => {
    switch (oauthState.status) {
      case 'idle':
        return (
          <div className="text-center py-12">
            <div className="mb-6">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🎯</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">Connect to Jira</h3>
              <p className="text-gray-600 mb-6">
                Authorize ATOM to access your Jira workspace and discover projects
              </p>
            </div>
            
            <button
              onClick={startOAuthFlow}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              🚀 Connect to Jira
            </button>
          </div>
        );

      case 'loading':
        return (
          <div className="text-center py-12">
            <div className="mb-6">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4 animate-spin">
                <span className="text-2xl">⚙️</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">Processing OAuth Flow</h3>
              <p className="text-gray-600">{oauthState.step}</p>
            </div>
            
            {/* Progress indicators */}
            <div className="max-w-md mx-auto">
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-gray-700">Start OAuth flow</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-gray-700">User authorization</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
                  <span className="text-sm text-gray-700">Exchange code for tokens</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
                  <span className="text-sm text-gray-700">Discover resources</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
                  <span className="text-sm text-gray-700">Load projects and issues</span>
                </div>
              </div>
            </div>
          </div>
        );

      case 'success':
        return (
          <div className="text-center py-12">
            <div className="mb-6">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">✅</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">Jira Integration Successful</h3>
              <p className="text-gray-600 mb-6">
                {oauthState.step}
              </p>
            </div>

            {/* Show discovered data */}
            {oauthState.resources.length > 0 && (
              <div className="mb-6">
                <h4 className="font-semibold text-gray-800 mb-3">Discovered Resources</h4>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {oauthState.resources.map((resource, index) => (
                    <div
                      key={index}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        oauthState.selectedResource?.cloud_id === resource.cloud_id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => handleResourceSelect(resource)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-blue-100 rounded flex items-center justify-center">
                            <span className="text-sm">🏢</span>
                          </div>
                          <div>
                            <div className="font-medium text-gray-800">{resource.name}</div>
                            <div className="text-sm text-gray-500">{resource.cloud_id}</div>
                          </div>
                        </div>
                        <div className="text-sm text-gray-500">
                          {resource.scopes?.length || 0} scopes
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Show projects and issues */}
            {oauthState.projects.length > 0 && (
              <div className="mb-6">
                <h4 className="font-semibold text-gray-800 mb-3">
                  Projects ({oauthState.projects.length})
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {oauthState.projects.slice(0, 6).map((project, index) => (
                    <div key={index} className="p-3 border border-gray-200 rounded-lg">
                      <div className="font-medium text-gray-800">{project.name}</div>
                      <div className="text-sm text-gray-500">{project.key}</div>
                    </div>
                  ))}
                  {oauthState.projects.length > 6 && (
                    <div className="p-3 border border-gray-200 rounded-lg text-center">
                      <div className="font-medium text-gray-600">
                        +{oauthState.projects.length - 6} more
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {oauthState.issues.length > 0 && (
              <div className="mb-6">
                <h4 className="font-semibold text-gray-800 mb-3">
                  Recent Issues ({oauthState.issues.length})
                </h4>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {oauthState.issues.slice(0, 5).map((issue, index) => (
                    <div key={index} className="p-3 border border-gray-200 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-gray-800">{issue.key}</div>
                          <div className="text-sm text-gray-600">{issue.summary}</div>
                        </div>
                        <div className="text-sm text-gray-500">
                          {issue.status}
                        </div>
                      </div>
                    </div>
                  ))}
                  {oauthState.issues.length > 5 && (
                    <div className="text-center text-sm text-gray-500 py-2">
                      +{oauthState.issues.length - 5} more issues
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex justify-center space-x-3">
              <button
                onClick={loadResources}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                🔄 Refresh Resources
              </button>
              <button
                onClick={() => {
                  setOAuthState({
                    status: 'idle',
                    step: '',
                    authUrl: '',
                    resources: [],
                    selectedResource: null,
                    projects: [],
                    issues: []
                  });
                }}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                🔄 Reconnect
              </button>
            </div>
          </div>
        );

      case 'error':
        return (
          <div className="text-center py-12">
            <div className="mb-6">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">❌</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">OAuth Integration Failed</h3>
              <p className="text-gray-600 mb-4">{oauthState.step}</p>
              
              {/* Error details */}
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-left">
                <h4 className="font-semibold text-red-800 mb-2">Error Details</h4>
                <p className="text-sm text-red-700">{oauthState.step}</p>
              </div>

              {/* Troubleshooting */}
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 text-left">
                <h4 className="font-semibold text-yellow-800 mb-2">Troubleshooting Steps</h4>
                <ol className="text-sm text-yellow-700 list-decimal list-inside space-y-1">
                  <li>Check that Jira OAuth app is properly configured</li>
                  <li>Verify redirect URI matches your app configuration</li>
                  <li>Ensure you have permission to access the Jira workspace</li>
                  <li>Check network connectivity and firewall settings</li>
                  <li>Try refreshing the page and starting OAuth flow again</li>
                </ol>
              </div>
            </div>

            <div className="flex justify-center space-x-3">
              <button
                onClick={startOAuthFlow}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                🔄 Try Again
              </button>
              <button
                onClick={() => {
                  setOAuthState({
                    status: 'idle',
                    step: '',
                    authUrl: '',
                    resources: [],
                    selectedResource: null,
                    projects: [],
                    issues: []
                  });
                }}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                🔄 Reset
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className={`w-full max-w-4xl mx-auto p-6 ${className}`}>
      <div className="bg-white rounded-lg shadow-lg">
        {/* Header */}
        <div className="border-b border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Jira OAuth Integration</h2>
              <p className="text-gray-600">Complete OAuth flow for Jira workspace access</p>
            </div>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${
                oauthState.status === 'success' ? 'bg-green-500' :
                oauthState.status === 'loading' ? 'bg-blue-500 animate-pulse' :
                oauthState.status === 'error' ? 'bg-red-500' :
                'bg-gray-300'
              }`}></div>
              <span className="text-sm text-gray-600 capitalize">
                {oauthState.status}
              </span>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="p-6">
          {renderStatus()}
        </div>
      </div>
    </div>
  );
};

export default JiraOAuthFlow;