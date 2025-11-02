/**
 * ATOM Jira OAuth Debug Usage Example
 * How to use the debugging tools in your application
 */

import React from 'react';
import { JiraOAuthDebugger, JiraOAuthTestPage, JiraOAuthFixHelper } from './src/ui-shared/integrations/jira/debug';

// Example 1: Using the Debug Component
export const JiraOAuthDebugExample: React.FC = () => {
  return (
    <div className="p-6">
      <h1>Jira OAuth Debug Example</h1>
      <p>This demonstrates how to use the Jira OAuth debugging tools.</p>
      
      {/* Basic Debugger Component */}
      <div className="mb-8">
        <h2>Basic OAuth Debugger</h2>
        <JiraOAuthDebugger />
      </div>
    </div>
  );
};

// Example 2: Full Test Page
export const JiraOAuthTestExample: React.FC = () => {
  return (
    <JiraOAuthTestPage />
  );
};

// Example 3: Diagnostic Tool Usage
export const JiraDiagnosticExample: React.FC = () => {
  const [diagnostic, setDiagnostic] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(false);

  const runDiagnostic = async () => {
    setLoading(true);
    try {
      const result = await JiraOAuthFixHelper.diagnoseOAuthIssues();
      setDiagnostic(result);
      
      console.log('🔍 Jira OAuth Diagnostic Results:');
      console.log('Issues:', result.issues);
      console.log('Fixes:', result.fixes);
      console.log('Recommendations:', result.recommendations);
      console.log('Test Results:', result.testResults);
      
    } catch (error) {
      console.error('Diagnostic failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <h1>Jira OAuth Diagnostic Tool</h1>
      
      <button
        onClick={runDiagnostic}
        disabled={loading}
        className="px-4 py-2 bg-blue-500 text-white rounded disabled:bg-gray-300"
      >
        {loading ? 'Running Diagnostic...' : '🔍 Run Diagnostic'}
      </button>

      {diagnostic && (
        <div className="mt-6 space-y-4">
          {/* Issues Display */}
          <div className="bg-white border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-3">Issues Found ({diagnostic.issues.length})</h2>
            <div className="space-y-2">
              {diagnostic.issues.map((issue: any, index: number) => (
                <div key={index} className={`p-3 rounded border ${
                  issue.severity === 'critical' ? 'bg-red-50 border-red-200' :
                  issue.severity === 'error' ? 'bg-red-50 border-red-200' :
                  issue.severity === 'warning' ? 'bg-yellow-50 border-yellow-200' :
                  'bg-blue-50 border-blue-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{issue.title}</span>
                    <span className={`text-sm px-2 py-1 rounded ${
                      issue.severity === 'critical' ? 'bg-red-100 text-red-800' :
                      issue.severity === 'error' ? 'bg-red-100 text-red-800' :
                      issue.severity === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {issue.severity}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mt-1">{issue.description}</div>
                  <div className="text-sm text-gray-700 mt-2">Solution: {issue.solution}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Fixes Display */}
          <div className="bg-white border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-3">Recommended Fixes</h2>
            <ul className="list-disc list-inside space-y-1">
              {diagnostic.fixes.map((fix: string, index: number) => (
                <li key={index} className="text-sm">{fix}</li>
              ))}
            </ul>
          </div>

          {/* Recommendations Display */}
          <div className="bg-white border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-3">General Recommendations</h2>
            <ul className="list-disc list-inside space-y-1">
              {diagnostic.recommendations.map((rec: string, index: number) => (
                <li key={index} className="text-sm">{rec}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

// Example 4: Environment Template Generator
export const EnvironmentTemplateExample: React.FC = () => {
  const generateTemplate = () => {
    const template = JiraOAuthFixHelper.generateEnvironmentTemplate();
    
    // Download as file
    const blob = new Blob([template], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env.jira.template';
    a.click();
    URL.revokeObjectURL(url);
  };

  const generateTestScript = () => {
    const script = JiraOAuthFixHelper.generateTestScript();
    
    // Download as file
    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'debug-jira-oauth.sh';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6">
      <h1>Jira OAuth Configuration Tools</h1>
      
      <div className="space-y-4">
        <div className="bg-gray-50 p-4 rounded">
          <h2 className="font-semibold mb-2">Environment Template</h2>
          <p className="text-sm text-gray-600 mb-3">
            Generate a .env template with all required Jira OAuth variables.
          </p>
          <button
            onClick={generateTemplate}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          >
            📄 Download .env Template
          </button>
        </div>

        <div className="bg-gray-50 p-4 rounded">
          <h2 className="font-semibold mb-2">Test Script</h2>
          <p className="text-sm text-gray-600 mb-3">
            Download a shell script to test your Jira OAuth configuration.
          </p>
          <button
            onClick={generateTestScript}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            🐚 Download Test Script
          </button>
        </div>
      </div>
    </div>
  );
};

// Example 5: In-App Integration
export const InAppDebugIntegration: React.FC = () => {
  const [showDebug, setShowDebug] = React.useState(false);
  const [oauthState, setOAuthState] = React.useState<any>(null);

  React.useEffect(() => {
    // Listen for OAuth callback messages
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'JIRA_OAUTH_SUCCESS') {
        setOAuthState({
          type: 'success',
          code: event.data.code,
          state: event.data.state
        });
        setShowDebug(false);
      } else if (event.data.type === 'JIRA_OAUTH_ERROR') {
        setOAuthState({
          type: 'error',
          error: event.data.error,
          errorDescription: event.data.errorDescription
        });
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const startOAuthFlow = () => {
    // Open OAuth in popup
    const popup = window.open(
      '/oauth/jira/test',
      'jira-oauth',
      'width=600,height=600,scrollbars=yes,resizable=yes'
    );
  };

  return (
    <div className="p-6">
      <h1>Jira OAuth Integration</h1>
      
      {/* OAuth Status */}
      <div className="mb-6">
        <h2>OAuth Status</h2>
        {oauthState ? (
          <div className={`p-4 rounded ${
            oauthState.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            <div className="font-semibold">
              {oauthState.type === 'success' ? '✅ OAuth Successful' : '❌ OAuth Failed'}
            </div>
            {oauthState.type === 'success' ? (
              <div className="text-sm mt-1">
                Authorization Code: {oauthState.code?.substring(0, 20)}...
              </div>
            ) : (
              <div className="text-sm mt-1">
                Error: {oauthState.error}
                {oauthState.errorDescription && ` - ${oauthState.errorDescription}`}
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 bg-gray-50 text-gray-600 rounded">
            OAuth not attempted yet
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="mb-6">
        <h2>Actions</h2>
        <div className="flex gap-3">
          <button
            onClick={startOAuthFlow}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            🚀 Start OAuth Flow
          </button>
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            {showDebug ? 'Hide' : 'Show'} Debug Tools
          </button>
        </div>
      </div>

      {/* Debug Tools */}
      {showDebug && (
        <div className="mb-6">
          <h2>Debug Tools</h2>
          <JiraOAuthDebugger />
        </div>
      )}
    </div>
  );
};

// Export all examples
export {
  JiraOAuthDebugExample,
  JiraOAuthTestExample,
  JiraDiagnosticExample,
  EnvironmentTemplateExample,
  InAppDebugIntegration
};

export default {
  JiraOAuthDebugExample,
  JiraOAuthTestExample,
  JiraDiagnosticExample,
  EnvironmentTemplateExample,
  InAppDebugIntegration
};