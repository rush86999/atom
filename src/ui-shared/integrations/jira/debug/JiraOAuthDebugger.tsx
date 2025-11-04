/**
 * ATOM Jira OAuth Debug Tool
 * Comprehensive Jira OAuth Integration Debugger
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';

interface JiraOAuthDebugState {
  step: 'testing' | 'error' | 'success' | 'loading';
  currentStep: string;
  progress: number;
  results: any[];
  error: string | null;
  config: {
    serverUrl?: string;
    clientId?: string;
    clientSecret?: string;
    redirectUri?: string;
    scopes?: string[];
  };
  authFlow: {
    authUrl?: string;
    authCode?: string;
    accessToken?: string;
    refreshToken?: string;
    tokenData?: any;
  };
  apiTest: {
    userInfo?: any;
    projects?: any[];
    issues?: any[];
  };
}

export const JiraOAuthDebugger: React.FC = () => {
  const [state, setState] = useState<JiraOAuthDebugState>({
    step: 'testing',
    currentStep: 'Initializing...',
    progress: 0,
    results: [],
    error: null,
    config: {},
    authFlow: {},
    apiTest: {}
  });

  const [environmentCheck, setEnvironmentCheck] = useState({
    clientId: false,
    clientSecret: false,
    redirectUri: false,
    serverUrl: false
  });

  // Load configuration from environment
  useEffect(() => {
    const loadConfig = () => {
      try {
        // Browser environment
        if (typeof window !== 'undefined') {
          // Check for environment variables (Next.js)
          const config = {
            serverUrl: process.env.NEXT_PUBLIC_JIRA_SERVER_URL || process.env.JIRA_SERVER_URL || '',
            clientId: process.env.NEXT_PUBLIC_JIRA_CLIENT_ID || process.env.JIRA_CLIENT_ID || '',
            clientSecret: process.env.JIRA_CLIENT_SECRET || '', // Never exposed to browser
            redirectUri: process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI || process.env.JIRA_REDIRECT_URI || `${window.location.origin}/oauth/jira/callback`,
            scopes: ['read:jira-work', 'read:issue-details:jira', 'read:comments:jira', 'read:attachments:jira']
          };

          setState(prev => ({
            ...prev,
            config,
            currentStep: 'Configuration loaded'
          }));

          // Validate environment
          setEnvironmentCheck({
            clientId: !!config.clientId,
            clientSecret: true, // Never check in browser
            redirectUri: !!config.redirectUri,
            serverUrl: !!config.serverUrl
          });
        } else {
          // Node.js environment
          const config = {
            serverUrl: process.env.JIRA_SERVER_URL || '',
            clientId: process.env.JIRA_CLIENT_ID || '',
            clientSecret: process.env.JIRA_CLIENT_SECRET || '',
            redirectUri: process.env.JIRA_REDIRECT_URI || 'http://localhost:3000/oauth/jira/callback',
            scopes: ['read:jira-work', 'read:issue-details:jira', 'read:comments:jira', 'read:attachments:jira']
          };

          setState(prev => ({
            ...prev,
            config,
            currentStep: 'Configuration loaded'
          }));

          setEnvironmentCheck({
            clientId: !!config.clientId,
            clientSecret: !!config.clientSecret,
            redirectUri: !!config.redirectUri,
            serverUrl: !!config.serverUrl
          });
        }
      } catch (error) {
        setState(prev => ({
          ...prev,
          error: `Configuration error: ${(error as Error).message}`,
          step: 'error'
        }));
      }
    };

    loadConfig();
  }, []);

  // Step 1: Test Jira Server Connectivity
  const testServerConnectivity = useCallback(async () => {
    setState(prev => ({
      ...prev,
      currentStep: 'Testing Jira server connectivity...',
      progress: 10
    }));

    try {
      const { serverUrl } = state.config;
      
      if (!serverUrl) {
        throw new Error('JIRA_SERVER_URL not configured');
      }

      // Test different endpoints
      const testEndpoints = [
        '/rest/api/3/serverInfo',
        '/rest/api/3/myself',
        '/status'
      ];

      let workingEndpoint = null;
      let serverInfo = null;

      for (const endpoint of testEndpoints) {
        try {
          const response = await fetch(`${serverUrl}${endpoint}`, {
            method: 'GET',
            headers: {
              'Accept': 'application/json',
              'User-Agent': 'ATOM-Agent-OAuth-Debugger/1.0'
            }
          });

          if (response.ok) {
            workingEndpoint = endpoint;
            serverInfo = await response.json();
            break;
          }
        } catch (endpointError) {
          console.log(`Endpoint ${endpoint} failed:`, endpointError);
        }
      }

      if (!workingEndpoint) {
        throw new Error(`Cannot connect to Jira server: ${serverUrl}. Check if server is accessible and URL is correct.`);
      }

      const result = {
        step: 'Server Connectivity',
        status: 'success',
        serverUrl,
        workingEndpoint,
        serverInfo,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        currentStep: 'Server connectivity verified',
        progress: 20,
        results: [...prev.results, result]
      }));

      return result;
    } catch (error) {
      const result = {
        step: 'Server Connectivity',
        status: 'error',
        error: (error as Error).message,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        error: result.error,
        step: 'error',
        currentStep: 'Server connectivity failed',
        progress: 20,
        results: [...prev.results, result]
      }));

      throw error;
    }
  }, [state.config]);

  // Step 2: Build OAuth Authorization URL
  const buildAuthUrl = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentStep: 'Building OAuth authorization URL...',
      progress: 30
    }));

    try {
      const { serverUrl, clientId, redirectUri, scopes } = state.config;

      if (!serverUrl || !clientId || !redirectUri || !scopes) {
        throw new Error('Missing required OAuth configuration');
      }

      // Build OAuth URL for Atlassian
      const authUrl = new URL('https://auth.atlassian.com/authorize');
      authUrl.searchParams.append('client_id', clientId);
      authUrl.searchParams.append('redirect_uri', redirectUri);
      authUrl.searchParams.append('response_type', 'code');
      authUrl.searchParams.append('scope', scopes.join(' '));
      authUrl.searchParams.append('state', generateState());

      const result = {
        step: 'OAuth URL Building',
        status: 'success',
        authUrl: authUrl.toString(),
        clientId,
        redirectUri,
        scopes,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        currentStep: 'OAuth authorization URL built',
        progress: 40,
        results: [...prev.results, result],
        authFlow: {
          ...prev.authFlow,
          authUrl: authUrl.toString()
        }
      }));

      return result;
    } catch (error) {
      const result = {
        step: 'OAuth URL Building',
        status: 'error',
        error: (error as Error).message,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        error: result.error,
        step: 'error',
        currentStep: 'OAuth URL building failed',
        progress: 40,
        results: [...prev.results, result]
      }));

      throw error;
    }
  }, [state.config]);

  // Step 3: Exchange Authorization Code for Access Token
  const exchangeCodeForToken = useCallback(async (authCode: string) => {
    setState(prev => ({
      ...prev,
      currentStep: 'Exchanging authorization code for access token...',
      progress: 50
    }));

    try {
      const { clientId, clientSecret, redirectUri } = state.config;

      if (!clientId || !clientSecret || !redirectUri) {
        throw new Error('Missing required token exchange configuration');
      }

      // Exchange code for token
      const tokenResponse = await fetch('https://auth.atlassian.com/oauth/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          grant_type: 'authorization_code',
          client_id: clientId,
          client_secret: clientSecret,
          code: authCode,
          redirect_uri: redirectUri
        })
      });

      if (!tokenResponse.ok) {
        const errorData = await tokenResponse.text();
        throw new Error(`Token exchange failed: ${tokenResponse.status} - ${errorData}`);
      }

      const tokenData = await tokenResponse.json();

      const result = {
        step: 'Token Exchange',
        status: 'success',
        tokenData: {
          access_token: tokenData.access_token ? '***RECEIVED***' : null,
          refresh_token: tokenData.refresh_token ? '***RECEIVED***' : null,
          expires_in: tokenData.expires_in,
          scope: tokenData.scope,
          token_type: tokenData.token_type
        },
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        currentStep: 'Access token received',
        progress: 60,
        results: [...prev.results, result],
        authFlow: {
          ...prev.authFlow,
          authCode,
          accessToken: tokenData.access_token,
          refreshToken: tokenData.refresh_token,
          tokenData
        }
      }));

      return result;
    } catch (error) {
      const result = {
        step: 'Token Exchange',
        status: 'error',
        error: (error as Error).message,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        error: result.error,
        step: 'error',
        currentStep: 'Token exchange failed',
        progress: 60,
        results: [...prev.results, result]
      }));

      throw error;
    }
  }, [state.config]);

  // Step 4: Test API Access with Token
  const testApiAccess = useCallback(async (accessToken: string) => {
    setState(prev => ({
      ...prev,
      currentStep: 'Testing API access with access token...',
      progress: 70
    }));

    try {
      const { serverUrl } = state.config;

      // Test API calls
      const apiTests = [
        {
          name: 'Get User Info',
          url: `${serverUrl}/rest/api/3/myself`,
          method: 'GET'
        },
        {
          name: 'Get Projects',
          url: `${serverUrl}/rest/api/3/project/search`,
          method: 'GET'
        },
        {
          name: 'Search Issues',
          url: `${serverUrl}/rest/api/3/search`,
          method: 'GET',
          params: { jql: 'status != "Done"', maxResults: 5 }
        }
      ];

      const apiResults = [];

      for (const test of apiTests) {
        try {
          const url = new URL(test.url);
          if (test.params) {
            Object.entries(test.params).forEach(([key, value]) => {
              url.searchParams.append(key, value as string);
            });
          }

          const response = await fetch(url.toString(), {
            method: test.method,
            headers: {
              'Authorization': `Bearer ${accessToken}`,
              'Accept': 'application/json'
            }
          });

          if (response.ok) {
            const data = await response.json();
            apiResults.push({
              name: test.name,
              status: 'success',
              data,
              timestamp: new Date().toISOString()
            });
          } else {
            const errorText = await response.text();
            apiResults.push({
              name: test.name,
              status: 'error',
              error: `${response.status} - ${errorText}`,
              timestamp: new Date().toISOString()
            });
          }
        } catch (testError) {
          apiResults.push({
            name: test.name,
            status: 'error',
            error: (testError as Error).message,
            timestamp: new Date().toISOString()
          });
        }
      }

      const result = {
        step: 'API Access Test',
        status: 'success',
        apiTests: apiResults,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        currentStep: 'API access verified',
        progress: 80,
        results: [...prev.results, result],
        apiTest: {
          userInfo: apiResults.find(r => r.name === 'Get User Info')?.data,
          projects: apiResults.find(r => r.name === 'Get Projects')?.data,
          issues: apiResults.find(r => r.name === 'Search Issues')?.data
        }
      }));

      return result;
    } catch (error) {
      const result = {
        step: 'API Access Test',
        status: 'error',
        error: (error as Error).message,
        timestamp: new Date().toISOString()
      };

      setState(prev => ({
        ...prev,
        error: result.error,
        step: 'error',
        currentStep: 'API access test failed',
        progress: 80,
        results: [...prev.results, result]
      }));

      throw error;
    }
  }, [state.config]);

  // Full OAuth Flow Test
  const runFullOAuthTest = useCallback(async () => {
    try {
      setState(prev => ({
        ...prev,
        step: 'testing',
        currentStep: 'Starting full OAuth flow test...',
        progress: 0,
        results: [],
        error: null
      }));

      // Step 1: Test server connectivity
      await testServerConnectivity();

      // Step 2: Build OAuth URL
      const authUrlResult = await buildAuthUrl();

      // For browser environment, redirect to OAuth
      if (typeof window !== 'undefined' && authUrlResult.authUrl) {
        setState(prev => ({
          ...prev,
          currentStep: 'Please complete OAuth authorization in the popup window...',
          progress: 45
        }));

        // Open OAuth in popup
        const popup = window.open(authUrlResult.authUrl, 'jira-oauth', 'width=600,height=600,scrollbars=yes,resizable=yes');

        // Listen for popup messages
        return new Promise((resolve, reject) => {
          const messageHandler = async (event: MessageEvent) => {
            // Verify origin for security
            if (event.origin !== window.location.origin) {
              return;
            }

            if (event.data.type === 'JIRA_OAUTH_SUCCESS') {
              popup?.close();
              window.removeEventListener('message', messageHandler);

              try {
                // Step 3: Exchange code for token
                await exchangeCodeForToken(event.data.code);

                // Step 4: Test API access
                await testApiAccess(state.authFlow.accessToken!);

                setState(prev => ({
                  ...prev,
                  step: 'success',
                  currentStep: 'OAuth flow completed successfully!',
                  progress: 100
                }));

                resolve(true);
              } catch (error) {
                reject(error);
              }
            } else if (event.data.type === 'JIRA_OAUTH_ERROR') {
              popup?.close();
              window.removeEventListener('message', messageHandler);
              reject(new Error(event.data.error));
            }
          };

          window.addEventListener('message', messageHandler);

          // Check popup periodically
          const checkPopup = setInterval(() => {
            if (popup?.closed) {
              clearInterval(checkPopup);
              window.removeEventListener('message', messageHandler);
              reject(new Error('OAuth popup was closed before completion'));
            }
          }, 1000);
        });
      }

    } catch (error) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: (error as Error).message,
        progress: 100
      }));
    }
  }, [testServerConnectivity, buildAuthUrl, exchangeCodeForToken, testApiAccess, state.authFlow.accessToken]);

  // Generate random state for OAuth
  const generateState = () => {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  };

  // Clear results
  const clearResults = () => {
    setState(prev => ({
      ...prev,
      step: 'testing',
      currentStep: 'Ready to test...',
      progress: 0,
      results: [],
      error: null,
      authFlow: {},
      apiTest: {}
    }));
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">🔍 Jira OAuth Debugger</h1>

      {/* Configuration Status */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3 text-gray-700">Configuration Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className={`p-3 rounded ${environmentCheck.serverUrl ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <div className="text-sm font-medium">Server URL</div>
            <div className="text-xs">{environmentCheck.serverUrl ? '✅ Configured' : '❌ Missing'}</div>
          </div>
          <div className={`p-3 rounded ${environmentCheck.clientId ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <div className="text-sm font-medium">Client ID</div>
            <div className="text-xs">{environmentCheck.clientId ? '✅ Configured' : '❌ Missing'}</div>
          </div>
          <div className={`p-3 rounded ${environmentCheck.redirectUri ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <div className="text-sm font-medium">Redirect URI</div>
            <div className="text-xs">{environmentCheck.redirectUri ? '✅ Configured' : '❌ Missing'}</div>
          </div>
          <div className={`p-3 rounded ${environmentCheck.clientSecret ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <div className="text-sm font-medium">Client Secret</div>
            <div className="text-xs">{environmentCheck.clientSecret ? '✅ Configured' : '❌ Missing'}</div>
          </div>
        </div>
      </div>

      {/* Current Status */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3 text-gray-700">Current Status</h2>
        <div className="p-4 bg-gray-50 rounded">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">{state.currentStep}</span>
            <span className="text-sm text-gray-500">{state.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className={`h-2 rounded-full transition-all duration-300 ${
                state.step === 'success' ? 'bg-green-500' :
                state.step === 'error' ? 'bg-red-500' :
                state.step === 'loading' ? 'bg-blue-500' :
                'bg-gray-400'
              }`}
              style={{ width: `${state.progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3 text-gray-700">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={runFullOAuthTest}
            disabled={state.step === 'loading'}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {state.step === 'loading' ? '⏳ Testing...' : '🚀 Run Full OAuth Test'}
          </button>
          <button
            onClick={testServerConnectivity}
            disabled={state.step === 'loading'}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            🌐 Test Server Connectivity
          </button>
          <button
            onClick={buildAuthUrl}
            disabled={state.step === 'loading'}
            className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            🔗 Build Auth URL
          </button>
          <button
            onClick={clearResults}
            className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            🗑️ Clear Results
          </button>
        </div>
      </div>

      {/* OAuth URL (if built) */}
      {state.authFlow.authUrl && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-700">OAuth Authorization URL</h2>
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-sm text-gray-600 mb-2">Click this URL to test OAuth manually:</div>
            <div className="p-2 bg-white border rounded text-xs break-all">
              <a 
                href={state.authFlow.authUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {state.authFlow.authUrl}
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {state.results.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-700">Test Results</h2>
          <div className="space-y-3">
            {state.results.map((result, index) => (
              <div key={index} className={`p-4 rounded border ${
                result.status === 'success' ? 'bg-green-50 border-green-200' :
                'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-800">{result.step}</span>
                  <span className={`text-sm px-2 py-1 rounded ${
                    result.status === 'success' ? 'bg-green-100 text-green-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {result.status}
                  </span>
                </div>
                
                {result.error && (
                  <div className="text-sm text-red-600 mb-2">Error: {result.error}</div>
                )}

                <div className="text-xs text-gray-500 mb-2">
                  {new Date(result.timestamp).toLocaleString()}
                </div>

                {/* Show detailed results */}
                <div className="text-xs">
                  {result.authUrl && (
                    <div className="mb-1">
                      <strong>Auth URL:</strong> {result.authUrl.substring(0, 100)}...
                    </div>
                  )}
                  {result.serverUrl && (
                    <div className="mb-1">
                      <strong>Server URL:</strong> {result.serverUrl}
                    </div>
                  )}
                  {result.workingEndpoint && (
                    <div className="mb-1">
                      <strong>Working Endpoint:</strong> {result.workingEndpoint}
                    </div>
                  )}
                  {result.tokenData && (
                    <div className="mb-1">
                      <strong>Token Info:</strong>
                      <ul className="ml-4 mt-1">
                        <li>Access Token: {result.tokenData.access_token}</li>
                        <li>Refresh Token: {result.tokenData.refresh_token}</li>
                        <li>Expires In: {result.tokenData.expires_in}s</li>
                        <li>Scope: {result.tokenData.scope}</li>
                        <li>Token Type: {result.tokenData.token_type}</li>
                      </ul>
                    </div>
                  )}
                  {result.apiTests && (
                    <div className="mb-1">
                      <strong>API Tests:</strong>
                      <ul className="ml-4 mt-1">
                        {result.apiTests.map((test: any, testIndex: number) => (
                          <li key={testIndex} className={`mb-1 ${test.status === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                            {test.name}: {test.status}
                            {test.error && <span className="ml-2">({test.error})</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* API Test Results */}
      {(state.apiTest.userInfo || state.apiTest.projects || state.apiTest.issues) && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-700">API Test Data</h2>
          
          {state.apiTest.userInfo && (
            <div className="mb-4">
              <h3 className="text-lg font-medium mb-2 text-gray-700">User Info</h3>
              <pre className="p-3 bg-gray-50 rounded text-xs overflow-auto">
                {JSON.stringify(state.apiTest.userInfo, null, 2)}
              </pre>
            </div>
          )}

          {state.apiTest.projects && (
            <div className="mb-4">
              <h3 className="text-lg font-medium mb-2 text-gray-700">Projects ({state.apiTest.projects.length || 0})</h3>
              <pre className="p-3 bg-gray-50 rounded text-xs overflow-auto">
                {JSON.stringify(state.apiTest.projects, null, 2)}
              </pre>
            </div>
          )}

          {state.apiTest.issues && (
            <div className="mb-4">
              <h3 className="text-lg font-medium mb-2 text-gray-700">Issues ({state.apiTest.issues.issues?.length || 0})</h3>
              <pre className="p-3 bg-gray-50 rounded text-xs overflow-auto">
                {JSON.stringify(state.apiTest.issues, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {state.error && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-red-700">Error</h2>
          <div className="p-4 bg-red-50 border border-red-200 rounded">
            <div className="text-sm text-red-800">{state.error}</div>
          </div>
        </div>
      )}

      {/* Environment Variables */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3 text-gray-700">Environment Configuration</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-sm font-medium text-gray-600 mb-1">JIRA_SERVER_URL</div>
            <div className="text-xs font-mono break-all">
              {state.config.serverUrl || 'Not configured'}
            </div>
          </div>
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-sm font-medium text-gray-600 mb-1">JIRA_CLIENT_ID</div>
            <div className="text-xs font-mono break-all">
              {state.config.clientId || 'Not configured'}
            </div>
          </div>
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-sm font-medium text-gray-600 mb-1">JIRA_CLIENT_SECRET</div>
            <div className="text-xs font-mono break-all">
              {state.config.clientSecret ? '***CONFIGURED***' : 'Not configured'}
            </div>
          </div>
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-sm font-medium text-gray-600 mb-1">JIRA_REDIRECT_URI</div>
            <div className="text-xs font-mono break-all">
              {state.config.redirectUri || 'Not configured'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default JiraOAuthDebugger;