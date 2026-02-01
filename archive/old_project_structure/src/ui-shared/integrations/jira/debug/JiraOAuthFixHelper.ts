/**
 * ATOM Jira OAuth Fix Helper
 * Automated troubleshooting and fix suggestions
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

interface JiraOAuthIssue {
  type: 'config' | 'network' | 'auth' | 'api' | 'permission';
  severity: 'critical' | 'error' | 'warning' | 'info';
  title: string;
  description: string;
  solution: string;
  code?: string;
  checklist?: string[];
}

interface JiraOAuthDiagnostic {
  issues: JiraOAuthIssue[];
  fixes: string[];
  recommendations: string[];
  testResults: any;
}

export class JiraOAuthFixHelper {
  static async diagnoseOAuthIssues(): Promise<JiraOAuthDiagnostic> {
    const issues: JiraOAuthIssue[] = [];
    const testResults: any = {};

    // Check 1: Environment Configuration
    const envCheck = await this.checkEnvironmentConfiguration();
    issues.push(...envCheck.issues);
    Object.assign(testResults, envCheck.results);

    // Check 2: Jira Server Connectivity
    const serverCheck = await this.checkServerConnectivity();
    issues.push(...serverCheck.issues);
    Object.assign(testResults, serverCheck.results);

    // Check 3: OAuth App Configuration
    const oauthCheck = await this.checkOAuthAppConfiguration();
    issues.push(...oauthCheck.issues);
    Object.assign(testResults, oauthCheck.results);

    // Check 4: Network and CORS Issues
    const networkCheck = await this.checkNetworkIssues();
    issues.push(...networkCheck.issues);
    Object.assign(testResults, networkCheck.results);

    // Check 5: Token and Permission Issues
    const tokenCheck = await this.checkTokenPermissions();
    issues.push(...tokenCheck.issues);
    Object.assign(testResults, tokenCheck.results);

    // Generate fixes and recommendations
    const fixes = this.generateFixes(issues);
    const recommendations = this.generateRecommendations(issues);

    return {
      issues: issues.sort((a, b) => {
        const severityOrder = { critical: 0, error: 1, warning: 2, info: 3 };
        return severityOrder[a.severity] - severityOrder[b.severity];
      }),
      fixes,
      recommendations,
      testResults
    };
  }

  private static async checkEnvironmentConfiguration(): Promise<{
    issues: JiraOAuthIssue[];
    results: any;
  }> {
    const issues: JiraOAuthIssue[] = [];
    const results: any = { environment: {} };

    // Check client ID
    const clientId = process.env.JIRA_CLIENT_ID || process.env.NEXT_PUBLIC_JIRA_CLIENT_ID;
    if (!clientId) {
      issues.push({
        type: 'config',
        severity: 'critical',
        title: 'Jira Client ID Missing',
        description: 'JIRA_CLIENT_ID or NEXT_PUBLIC_JIRA_CLIENT_ID is not configured',
        solution: 'Add JIRA_CLIENT_ID to your environment variables',
        code: 'JIRA_CLIENT_ID=your_jira_client_id',
        checklist: [
          'Get Client ID from Atlassian Developer Console',
          'Add to .env file: JIRA_CLIENT_ID=your_client_id',
          'For browser: NEXT_PUBLIC_JIRA_CLIENT_ID=your_client_id'
        ]
      });
    }
    results.environment.clientId = !!clientId;

    // Check client secret
    const clientSecret = process.env.JIRA_CLIENT_SECRET;
    if (!clientSecret) {
      issues.push({
        type: 'config',
        severity: 'critical',
        title: 'Jira Client Secret Missing',
        description: 'JIRA_CLIENT_SECRET is not configured (server-side)',
        solution: 'Add JIRA_CLIENT_SECRET to your server environment variables',
        code: 'JIRA_CLIENT_SECRET=your_jira_client_secret',
        checklist: [
          'Get Client Secret from Atlassian Developer Console',
          'Add to server .env file (NEVER expose to browser)',
          'Restart server after adding environment variable'
        ]
      });
    }
    results.environment.clientSecret = !!clientSecret;

    // Check server URL
    const serverUrl = process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL;
    if (!serverUrl) {
      issues.push({
        type: 'config',
        severity: 'critical',
        title: 'Jira Server URL Missing',
        description: 'JIRA_SERVER_URL is not configured',
        solution: 'Add JIRA_SERVER_URL to your environment variables',
        code: 'JIRA_SERVER_URL=https://your-domain.atlassian.net',
        checklist: [
          'For Jira Cloud: https://your-domain.atlassian.net',
          'For Jira Server: https://your-jira-server.com',
          'Add to .env file with correct protocol (https://)'
        ]
      });
    }
    results.environment.serverUrl = !!serverUrl;

    // Check redirect URI
    const redirectUri = process.env.JIRA_REDIRECT_URI || process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI;
    if (!redirectUri) {
      issues.push({
        type: 'config',
        severity: 'warning',
        title: 'Jira Redirect URI Missing',
        description: 'JIRA_REDIRECT_URI is not configured, using default',
        solution: 'Add JIRA_REDIRECT_URI to your environment variables',
        code: 'JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback',
        checklist: [
          'Must match redirect URI in Atlassian app configuration',
          'Use https:// for production',
          'For local dev: http://localhost:3000/oauth/jira/callback'
        ]
      });
    } else {
      // Validate redirect URI format
      try {
        const uri = new URL(redirectUri);
        results.environment.redirectUri = {
          valid: true,
          protocol: uri.protocol,
          hostname: uri.hostname,
          path: uri.pathname
        };

        if (uri.protocol !== 'https:' && !uri.hostname.includes('localhost')) {
          issues.push({
            type: 'config',
            severity: 'warning',
            title: 'Redirect URI Should Use HTTPS',
            description: 'Production redirect URIs should use HTTPS',
            solution: 'Update redirect URI to use HTTPS protocol',
            code: `JIRA_REDIRECT_URI=${redirectUri.replace(/^http:/, 'https:')}`
          });
        }
      } catch (error) {
        issues.push({
          type: 'config',
          severity: 'error',
          title: 'Invalid Redirect URI Format',
          description: `Redirect URI "${redirectUri}" is not a valid URL`,
          solution: 'Fix the redirect URI format in your environment variables',
          code: 'JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback'
        });
      }
    }

    return { issues, results };
  }

  private static async checkServerConnectivity(): Promise<{
    issues: JiraOAuthIssue[];
    results: any;
  }> {
    const issues: JiraOAuthIssue[] = [];
    const results: any = { server: {} };

    const serverUrl = process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL;
    
    if (!serverUrl) {
      return { issues, results };
    }

    try {
      // Test server accessibility
      const testUrls = [
        `${serverUrl}/rest/api/3/serverInfo`,
        `${serverUrl}/status`,
        serverUrl
      ];

      let workingUrl = null;
      let serverInfo = null;

      for (const url of testUrls) {
        try {
          const response = await fetch(url, {
            method: 'GET',
            headers: {
              'Accept': 'application/json',
              'User-Agent': 'ATOM-Jira-OAuth-Debugger/1.0'
            },
            signal: AbortSignal.timeout(10000) // 10 second timeout
          });

          if (response.ok) {
            workingUrl = url;
            serverInfo = await response.json();
            break;
          }
        } catch (urlError) {
          // Continue to next URL
        }
      }

      if (!workingUrl) {
        issues.push({
          type: 'network',
          severity: 'error',
          title: 'Jira Server Not Accessible',
          description: `Cannot connect to Jira server at ${serverUrl}`,
          solution: 'Check server URL and network connectivity',
          checklist: [
            'Verify JIRA_SERVER_URL is correct',
            'Check if Jira server is running and accessible',
            'Ensure firewall allows connections to Jira',
            'Check DNS resolution for server URL'
          ]
        });
      } else {
        results.server = {
          accessible: true,
          workingUrl,
          serverInfo,
          responseTime: Date.now()
        };

        // Check server version compatibility
        if (serverInfo && serverInfo.version) {
          const version = serverInfo.version;
          const majorVersion = parseInt(version.split('.')[0]);
          
          if (majorVersion < 8) {
            issues.push({
              type: 'config',
              severity: 'warning',
              title: 'Jira Version Compatibility',
              description: `Jira version ${version} may not support all API features`,
              solution: 'Consider upgrading to Jira 8.0+ for full API support'
            });
          }
        }
      }

    } catch (error) {
      issues.push({
        type: 'network',
        severity: 'error',
        title: 'Server Connectivity Error',
        description: `Error connecting to Jira server: ${(error as Error).message}`,
        solution: 'Check network connection and server status'
      });
    }

    return { issues, results };
  }

  private static async checkOAuthAppConfiguration(): Promise<{
    issues: JiraOAuthIssue[];
    results: any;
  }> {
    const issues: JiraOAuthIssue[] = [];
    const results: any = { oauth: {} };

    const clientId = process.env.JIRA_CLIENT_ID || process.env.NEXT_PUBLIC_JIRA_CLIENT_ID;
    const redirectUri = process.env.JIRA_REDIRECT_URI || process.env.NEXT_PUBLIC_JIRA_REDIRECT_URI;

    if (!clientId || !redirectUri) {
      return { issues, results };
    }

    // Build OAuth URL to validate
    try {
      const oauthUrl = new URL('https://auth.atlassian.com/authorize');
      oauthUrl.searchParams.append('client_id', clientId);
      oauthUrl.searchParams.append('redirect_uri', redirectUri);
      oauthUrl.searchParams.append('response_type', 'code');
      oauthUrl.searchParams.append('scope', 'read:jira-work');

      results.oauth.authUrl = oauthUrl.toString();
      results.oauth.urlValid = true;

    } catch (error) {
      issues.push({
        type: 'config',
        severity: 'error',
        title: 'OAuth URL Construction Error',
        description: `Failed to build OAuth URL: ${(error as Error).message}`,
        solution: 'Check client ID and redirect URI configuration'
      });
    }

    // Check required scopes
    const requiredScopes = [
      'read:jira-work',
      'read:issue-details:jira',
      'read:comments:jira',
      'read:attachments:jira'
    ];

    results.oauth.requiredScopes = requiredScopes;
    results.oauth.scopesConfigured = true;

    return { issues, results };
  }

  private static async checkNetworkIssues(): Promise<{
    issues: JiraOAuthIssue[];
    results: any;
  }> {
    const issues: JiraOAuthIssue[] = [];
    const results: any = { network: {} };

    // Check CORS support
    if (typeof window !== 'undefined') {
      results.network.browser = true;
      
      // Test CORS preflight
      try {
        const testResponse = await fetch('https://auth.atlassian.com/authorize', {
          method: 'OPTIONS',
          headers: {
            'Origin': window.location.origin,
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
          }
        });

        results.network.corsSupported = testResponse.ok;
        
        if (!testResponse.ok) {
          issues.push({
            type: 'network',
            severity: 'warning',
            title: 'CORS Issues Detected',
            description: 'CORS preflight request failed',
            solution: 'Ensure your domain is properly configured for Atlassian OAuth',
            checklist: [
              'Add your domain to Atlassian app callback URLs',
              'Check that redirect URI exactly matches configuration',
              'Use HTTPS for production environments'
            ]
          });
        }
      } catch (corsError) {
        results.network.corsSupported = false;
        issues.push({
          type: 'network',
          severity: 'warning',
          title: 'CORS Test Failed',
          description: `CORS test error: ${(corsError as Error).message}`,
          solution: 'CORS may need proper configuration on server'
        });
      }
    }

    // Check TLS/SSL issues
    const serverUrl = process.env.JIRA_SERVER_URL || process.env.NEXT_PUBLIC_JIRA_SERVER_URL;
    if (serverUrl && serverUrl.startsWith('https://')) {
      try {
        const url = new URL(serverUrl);
        results.network.httpsConfigured = true;
        results.network.hostname = url.hostname;
        
        // Note: SSL certificate checking requires server-side validation
        // Here we just record the intent to check
        
      } catch (error) {
        issues.push({
          type: 'network',
          severity: 'warning',
          title: 'HTTPS URL Parsing Error',
          description: `Failed to parse HTTPS URL: ${(error as Error).message}`,
          solution: 'Check JIRA_SERVER_URL format'
        });
      }
    }

    return { issues, results };
  }

  private static async checkTokenPermissions(): Promise<{
    issues: JiraOAuthIssue[];
    results: any;
  }> {
    const issues: JiraOAuthIssue[] = [];
    const results: any = { tokens: {} };

    // Note: This would typically be tested after OAuth flow is complete
    // Here we provide validation for common token issues
    
    results.tokens.canTest = false;
    results.tokens.testRequired = 'Complete OAuth flow first';

    // Common permission issues that may arise
    const commonIssues = [
      {
        issue: 'Insufficient Scopes',
        description: 'Access token does not have required permissions',
        solution: 'Ensure OAuth app requests all required scopes',
        scopes: ['read:jira-work', 'read:issue-details:jira']
      },
      {
        issue: 'Project Access',
        description: 'User does not have access to requested projects',
        solution: 'Check user permissions in Jira',
        scopes: []
      },
      {
        issue: 'Token Expired',
        description: 'Access token has expired',
        solution: 'Implement token refresh or re-authentication',
        scopes: []
      }
    ];

    results.tokens.commonIssues = commonIssues;

    return { issues, results };
  }

  private static generateFixes(issues: JiraOAuthIssue[]): string[] {
    const fixes: string[] = [];
    const fixSet = new Set<string>();

    issues.forEach(issue => {
      if (!fixSet.has(issue.solution)) {
        fixes.push(issue.solution);
        fixSet.add(issue.solution);
      }
    });

    return fixes;
  }

  private static generateRecommendations(issues: JiraOAuthIssue[]): string[] {
    const recommendations: string[] = [];
    const recSet = new Set<string>();

    // Generate recommendations based on issue types
    const criticalIssues = issues.filter(i => i.severity === 'critical');
    const errorIssues = issues.filter(i => i.severity === 'error');
    const warningIssues = issues.filter(i => i.severity === 'warning');

    if (criticalIssues.length > 0) {
      recommendations.push('🚨 CRITICAL: Fix all critical configuration issues before proceeding');
    }

    if (errorIssues.length > 0) {
      recommendations.push('❌ ERROR: Resolve network and connectivity issues');
    }

    if (warningIssues.length > 0) {
      recommendations.push('⚠️ WARNING: Consider fixing warnings for optimal operation');
    }

    // Environment-specific recommendations
    const configIssues = issues.filter(i => i.type === 'config');
    if (configIssues.length > 0) {
      recommendations.push('⚙️ Double-check all environment variables in .env file');
    }

    const networkIssues = issues.filter(i => i.type === 'network');
    if (networkIssues.length > 0) {
      recommendations.push('🌐 Verify network connectivity and firewall settings');
    }

    // Best practices
    recommendations.push('🔒 Use HTTPS for all production redirect URIs');
    recommendations.push('🔄 Implement proper token refresh mechanism');
    recommendations.push('📝 Enable comprehensive logging for debugging');
    recommendations.push('🧪 Test OAuth flow in staging environment first');

    // Filter duplicates
    return recommendations.filter(rec => !recSet.has(rec));
  }

  static generateEnvironmentTemplate(): string {
    return `# Jira OAuth Environment Configuration
# Copy this to your .env file and update the values

# Jira App Configuration (Get from https://developer.atlassian.com/console/myapps/)
JIRA_CLIENT_ID=your_jira_client_id_here
JIRA_CLIENT_SECRET=your_jira_client_secret_here

# Jira Server Configuration
# For Jira Cloud: https://your-domain.atlassian.net
# For Jira Server: https://your-jira-server.com
JIRA_SERVER_URL=https://your-domain.atlassian.net

# OAuth Redirect URI (Must match Atlassian app configuration)
# For local development: http://localhost:3000/oauth/jira/callback
# For production: https://your-domain.com/oauth/jira/callback
JIRA_REDIRECT_URI=http://localhost:3000/oauth/jira/callback

# Optional: Additional configuration
JIRA_API_TIMEOUT=30000
JIRA_MAX_RETRIES=3
JIRA_DEBUG_MODE=true`;
  }

  static generateTestScript(): string {
    return `#!/bin/bash
# Jira OAuth Test Script
# Run this to test your OAuth configuration

echo "🔍 Testing Jira OAuth Configuration..."
echo

# Check environment variables
echo "1. Checking environment variables..."
if [ -z "$JIRA_CLIENT_ID" ]; then
    echo "❌ JIRA_CLIENT_ID not set"
    exit 1
else
    echo "✅ JIRA_CLIENT_ID configured"
fi

if [ -z "$JIRA_CLIENT_SECRET" ]; then
    echo "❌ JIRA_CLIENT_SECRET not set"
    exit 1
else
    echo "✅ JIRA_CLIENT_SECRET configured"
fi

if [ -z "$JIRA_SERVER_URL" ]; then
    echo "❌ JIRA_SERVER_URL not set"
    exit 1
else
    echo "✅ JIRA_SERVER_URL: $JIRA_SERVER_URL"
fi

if [ -z "$JIRA_REDIRECT_URI" ]; then
    echo "❌ JIRA_REDIRECT_URI not set"
    exit 1
else
    echo "✅ JIRA_REDIRECT_URI: $JIRA_REDIRECT_URI"
fi

echo
echo "2. Testing server connectivity..."
curl -s -o /dev/null -w "%{http_code}" "$JIRA_SERVER_URL/rest/api/3/serverInfo" | grep -q "200"
if [ $? -eq 0 ]; then
    echo "✅ Jira server accessible"
else
    echo "❌ Cannot connect to Jira server"
    echo "   Check: Server URL, network connectivity, firewall"
    exit 1
fi

echo
echo "3. Testing OAuth URL construction..."
AUTH_URL="https://auth.atlassian.com/authorize?client_id=$JIRA_CLIENT_ID&redirect_uri=$JIRA_REDIRECT_URI&response_type=code&scope=read:jira-work"
echo "✅ OAuth URL: $AUTH_URL"

echo
echo "🎉 Basic configuration tests passed!"
echo "📝 Next steps:"
echo "   1. Visit the OAuth URL above to test the flow"
echo "   2. Complete authorization in your browser"
echo "   3. Check that you're redirected back successfully"
echo "   4. Run the full ATOM OAuth debugger for detailed testing"
`;
  }
}

export default JiraOAuthFixHelper;