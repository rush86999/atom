/**
 * ATOM Jira OAuth Test Page
 * Complete OAuth Flow Testing and Debugging
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect } from 'react';
import JiraOAuthDebugger from './JiraOAuthDebugger';

const JiraOAuthTestPage: React.FC = () => {
  const [showDebug, setShowDebug] = useState(true);
  const [oauthResult, setOAuthResult] = useState<any>(null);
  const [authCode, setAuthCode] = useState<string | null>(null);

  // Check URL parameters for OAuth callback
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');
      const error = urlParams.get('error');
      const errorDescription = urlParams.get('error_description');

      if (code) {
        setAuthCode(code);
        setOAuthResult({
          type: 'JIRA_OAUTH_SUCCESS',
          code,
          state,
          timestamp: new Date().toISOString()
        });

        // Send message to parent window (for popup flow)
        if (window.opener) {
          window.opener.postMessage({
            type: 'JIRA_OAUTH_SUCCESS',
            code,
            state
          }, window.location.origin);
        }
      } else if (error) {
        setOAuthResult({
          type: 'JIRA_OAUTH_ERROR',
          error,
          errorDescription,
          timestamp: new Date().toISOString()
        });

        // Send error to parent window
        if (window.opener) {
          window.opener.postMessage({
            type: 'JIRA_OAUTH_ERROR',
            error,
            errorDescription
          }, window.location.origin);
        }
      }
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            🎯 ATOM Jira OAuth Test Page
          </h1>
          <p className="text-gray-600">
            Comprehensive testing and debugging tool for Jira OAuth integration.
            This page helps identify and resolve OAuth configuration issues.
          </p>
        </div>

        {/* OAuth Callback Results */}
        {oauthResult && (
          <div className={`rounded-lg shadow-md p-6 mb-6 ${
            oauthResult.type === 'JIRA_OAUTH_SUCCESS' 
              ? 'bg-green-50 border-2 border-green-200' 
              : 'bg-red-50 border-2 border-red-200'
          }`}>
            <h2 className={`text-xl font-semibold mb-3 ${
              oauthResult.type === 'JIRA_OAUTH_SUCCESS' 
                ? 'text-green-800' 
                : 'text-red-800'
            }`}>
              {oauthResult.type === 'JIRA_OAUTH_SUCCESS' ? '✅ OAuth Success' : '❌ OAuth Error'}
            </h2>
            
            <div className="space-y-2">
              {oauthResult.type === 'JIRA_OAUTH_SUCCESS' ? (
                <>
                  <div className="text-sm">
                    <strong>Authorization Code:</strong> 
                    <code className="ml-2 px-2 py-1 bg-green-100 rounded text-xs">
                      {oauthResult.code?.substring(0, 20)}...
                    </code>
                  </div>
                  {oauthResult.state && (
                    <div className="text-sm">
                      <strong>State:</strong> 
                      <code className="ml-2 px-2 py-1 bg-green-100 rounded text-xs">
                        {oauthResult.state}
                      </code>
                    </div>
                  )}
                  <div className="text-sm text-green-700">
                    You can now use this authorization code to exchange for an access token.
                  </div>
                </>
              ) : (
                <>
                  <div className="text-sm">
                    <strong>Error:</strong> 
                    <code className="ml-2 px-2 py-1 bg-red-100 rounded text-xs">
                      {oauthResult.error}
                    </code>
                  </div>
                  {oauthResult.errorDescription && (
                    <div className="text-sm">
                      <strong>Description:</strong> {oauthResult.errorDescription}
                    </div>
                  )}
                  <div className="text-sm text-red-700">
                    Please check your OAuth configuration and try again.
                  </div>
                </>
              )}
              
              <div className="text-xs text-gray-500 mt-3">
                Timestamp: {oauthResult.timestamp}
              </div>
            </div>
          </div>
        )}

        {/* Manual OAuth Test Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">🔧 Manual OAuth Test</h2>
          
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 rounded">
              <h3 className="font-medium text-blue-800 mb-2">Quick Test Steps:</h3>
              <ol className="list-decimal list-inside text-sm text-blue-700 space-y-1">
                <li>Ensure your Jira OAuth app is properly configured</li>
                <li>Check that redirect URI matches: <code className="ml-1 px-1 bg-blue-100">{typeof window !== 'undefined' ? window.location.origin : 'https://your-domain.com'}/oauth/jira/callback</code></li>
                <li>Click "Generate Auth URL" below</li>
                <li>Complete authorization in Jira</li>
                <li>You'll be redirected back to this page with results</li>
              </ol>
            </div>

            <button
              onClick={() => {
                const clientId = process.env.NEXT_PUBLIC_JIRA_CLIENT_ID || process.env.JIRA_CLIENT_ID;
                const redirectUri = process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI || process.env.JIRA_REDIRECT_URI || `${typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'}/oauth/jira/callback`;
                const scopes = ['read:jira-work', 'read:issue-details:jira', 'read:comments:jira', 'read:attachments:jira'];
                const state = Math.random().toString(36).substring(2, 15);

                if (!clientId) {
                  alert('JIRA_CLIENT_ID not configured');
                  return;
                }

                const authUrl = new URL('https://auth.atlassian.com/authorize');
                authUrl.searchParams.append('client_id', clientId);
                authUrl.searchParams.append('redirect_uri', redirectUri);
                authUrl.searchParams.append('response_type', 'code');
                authUrl.searchParams.append('scope', scopes.join(' '));
                authUrl.searchParams.append('state', state);

                window.location.href = authUrl.toString();
              }}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              🚀 Generate Auth URL & Start OAuth
            </button>
          </div>
        </div>

        {/* Environment Check */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">⚙️ Environment Configuration</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-gray-50 rounded">
              <div className="text-sm font-medium text-gray-600">JIRA_CLIENT_ID</div>
              <div className={`text-xs font-mono break-all mt-1 ${
                process.env.JIRA_CLIENT_ID || process.env.NEXT_PUBLIC_JIRA_CLIENT_ID 
                  ? 'text-green-600' 
                  : 'text-red-600'
              }`}>
                {process.env.JIRA_CLIENT_ID || process.env.NEXT_PUBLIC_JIRA_CLIENT_ID 
                  ? `${(process.env.JIRA_CLIENT_ID || process.env.NEXT_PUBLIC_JIRA_CLIENT_ID)?.substring(0, 10)}... (Configured)`
                  : '❌ Not configured'
                }
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded">
              <div className="text-sm font-medium text-gray-600">JIRA_CLIENT_SECRET</div>
              <div className={`text-xs font-mono break-all mt-1 ${
                process.env.JIRA_CLIENT_SECRET 
                  ? 'text-green-600' 
                  : 'text-red-600'
              }`}>
                {process.env.JIRA_CLIENT_SECRET 
                  ? '***CONFIGURED***' 
                  : '❌ Not configured'
                }
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded">
              <div className="text-sm font-medium text-gray-600">JIRA_SERVER_URL</div>
              <div className={`text-xs font-mono break-all mt-1 ${
                process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL 
                  ? 'text-green-600' 
                  : 'text-red-600'
              }`}>
                {process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL 
                  ? process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL
                  : '❌ Not configured'
                }
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded">
              <div className="text-sm font-medium text-gray-600">JIRA_REDIRECT_URI</div>
              <div className={`text-xs font-mono break-all mt-1 ${
                process.env.JIRA_REDIRECT_URI || process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI 
                  ? 'text-green-600' 
                  : 'text-red-600'
              }`}>
                {process.env.JIRA_REDIRECT_URI || process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI 
                  ? process.env.JIRA_REDIRECT_URI || process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI
                  : typeof window !== 'undefined' 
                    ? `http://localhost:3000/oauth/jira/callback (Default)`
                    : '❌ Not configured'
                }
              </div>
            </div>
          </div>

          <div className="mt-4 p-3 bg-yellow-50 rounded">
            <div className="text-sm text-yellow-800">
              <strong>💡 Environment Setup:</strong>
              <br />
              • Browser environment: Use <code>NEXT_PUBLIC_</code> prefixed variables
              <br />
              • Server environment: Use regular variables (for token exchange)
              <br />
              • Make sure redirect URI exactly matches your Jira app configuration
              <br />
              • Client ID is safe to expose, but client secret should remain server-side
            </div>
          </div>
        </div>

        {/* OAuth Flow Diagram */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">🔄 OAuth Flow Diagram</h2>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">1</div>
              <div className="flex-grow">
                <div className="font-medium">User clicks "Authorize"</div>
                <div className="text-sm text-gray-600">Redirect to Atlassian authorization page</div>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">2</div>
              <div className="flex-grow">
                <div className="font-medium">User grants permission</div>
                <div className="text-sm text-gray-600">Atlassian redirects back with authorization code</div>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">3</div>
              <div className="flex-grow">
                <div className="font-medium">Exchange code for token</div>
                <div className="text-sm text-gray-600">Server makes POST request to token endpoint</div>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">4</div>
              <div className="flex-grow">
                <div className="font-medium">Receive access token</div>
                <div className="text-sm text-gray-600">Use token to make authenticated API calls</div>
              </div>
            </div>
          </div>
        </div>

        {/* Toggle Debugger */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800">🔍 Advanced Debugger</h2>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              {showDebug ? 'Hide' : 'Show'} Debugger
            </button>
          </div>
          
          {showDebug && <JiraOAuthDebugger />}
        </div>
      </div>
    </div>
  );
};

export default JiraOAuthTestPage;