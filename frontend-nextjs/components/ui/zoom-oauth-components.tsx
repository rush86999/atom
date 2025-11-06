/**
 * 🔐 Enhanced Zoom OAuth UI Components
 * Advanced OAuth flow components with enhanced security and user experience
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { 
  Shield, 
  CheckCircle, 
  AlertCircle, 
  Loader2, 
  RefreshCw,
  Eye,
  EyeOff,
  User,
  Settings,
  Clock,
  Activity,
  Lock,
  Unlock,
  Key,
  ExternalLink,
  Copy,
  Trash2,
  Users,
  Briefcase,
  GraduationCap,
  Building,
  Zap,
  Calendar,
  Video,
  Mic,
  MicOff,
  VideoOff,
  Monitor
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

// Enhanced OAuth Components
export const EnhancedZoomOAuthFlow = ({ 
  onOAuthStart, 
  onOAuthCallback, 
  isLoading, 
  oauthState,
  scopes,
  userRole 
}) => {
  const { toast } = useToast();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState(scopes || []);
  const [customRedirect, setCustomRedirect] = useState('');
  const [pkceEnabled, setPkceEnabled] = useState(true);
  const [stateId, setStateId] = useState('');
  const [csrfToken, setCsrfToken] = useState('');
  const [showSecurityInfo, setShowSecurityInfo] = useState(false);

  // Available OAuth scopes with descriptions
  const availableScopes = [
    { 
      id: 'user:read:admin', 
      name: 'Read User Info', 
      description: 'Read user information and profile data',
      category: 'user',
      icon: <User className="h-4 w-4" />,
      required: true
    },
    { 
      id: 'meeting:write:admin', 
      name: 'Manage Meetings', 
      description: 'Create, update, and delete meetings',
      category: 'meetings',
      icon: <Calendar className="h-4 w-4" />
    },
    { 
      id: 'meeting:read:admin', 
      name: 'Read Meetings', 
      description: 'Access meeting information and participants',
      category: 'meetings',
      icon: <Video className="h-4 w-4" />
    },
    { 
      id: 'recording:write:admin', 
      name: 'Manage Recordings', 
      description: 'Manage and delete recordings',
      category: 'recordings',
      icon: <Monitor className="h-4 w-4" />
    },
    { 
      id: 'recording:read:admin', 
      name: 'Access Recordings', 
      description: 'Access and download recordings',
      category: 'recordings',
      icon: <Eye className="h-4 w-4" />
    },
    { 
      id: 'webinar:write:admin', 
      name: 'Manage Webinars', 
      description: 'Create and manage webinars',
      category: 'webinars',
      icon: <Briefcase className="h-4 w-4" />
    },
    { 
      id: 'webinar:read:admin', 
      name: 'Read Webinars', 
      description: 'Access webinar information and data',
      category: 'webinars',
      icon: <Briefcase className="h-4 w-4" />
    },
    { 
      id: 'user:write:admin', 
      name: 'Manage Users', 
      description: 'Manage user accounts and settings',
      category: 'user',
      icon: <Settings className="h-4 w-4" />
    },
    { 
      id: 'report:read:admin', 
      name: 'Access Reports', 
      description: 'Access usage and activity reports',
      category: 'analytics',
      icon: <Activity className="h-4 w-4" />
    },
    { 
      id: 'dashboard:read:admin', 
      name: 'Access Dashboard', 
      description: 'Access analytics and dashboard data',
      category: 'analytics',
      icon: <Monitor className="h-4 w-4" />
    }
  ];

  // Scope categories
  const scopeCategories = [
    { id: 'user', name: 'User Management', icon: <User className="h-4 w-4" /> },
    { id: 'meetings', name: 'Meetings', icon: <Calendar className="h-4 w-4" /> },
    { id: 'recordings', name: 'Recordings', icon: <Monitor className="h-4 w-4" /> },
    { id: 'webinars', name: 'Webinars', icon: <Briefcase className="h-4 w-4" /> },
    { id: 'analytics', name: 'Analytics', icon: <Activity className="h-4 w-4" /> }
  ];

  useEffect(() => {
    if (scopes) {
      setSelectedScopes(scopes);
    }
  }, [scopes]);

  useEffect(() => {
    if (oauthState) {
      setStateId(oauthState.state_id || '');
      setCsrfToken(oauthState.csrf_token || '');
    }
  }, [oauthState]);

  const handleScopeToggle = (scopeId, checked) => {
    if (checked) {
      setSelectedScopes(prev => [...prev, scopeId]);
    } else {
      setSelectedScopes(prev => prev.filter(id => id !== scopeId));
    }
  };

  const handleCategoryToggle = (categoryId, checked) => {
    const categoryScopes = availableScopes
      .filter(scope => scope.category === categoryId)
      .map(scope => scope.id);

    if (checked) {
      setSelectedScopes(prev => [...new Set([...prev, ...categoryScopes])]);
    } else {
      setSelectedScopes(prev => 
        prev.filter(id => !categoryScopes.includes(id))
      );
    }
  };

  const isCategorySelected = (categoryId) => {
    const categoryScopes = availableScopes
      .filter(scope => scope.category === categoryId)
      .map(scope => scope.id);
    
    return categoryScopes.every(scope => selectedScopes.includes(scope));
  };

  const isCategoryPartiallySelected = (categoryId) => {
    const categoryScopes = availableScopes
      .filter(scope => scope.category === categoryId)
      .map(scope => scope.id);
    
    const selectedCount = categoryScopes.filter(scope => 
      selectedScopes.includes(scope)
    ).length;
    
    return selectedCount > 0 && selectedCount < categoryScopes.length;
  };

  const handleOAuthClick = async () => {
    if (selectedScopes.length === 0) {
      toast({
        title: "No Scopes Selected",
        description: "Please select at least one permission scope.",
        variant: "destructive",
      });
      return;
    }

    try {
      const metadata = {
        pkce_enabled: pkceEnabled,
        custom_redirect: customRedirect,
        advanced_settings: showAdvanced,
        selected_scopes_count: selectedScopes.length,
        request_timestamp: new Date().toISOString()
      };

      await onOAuthStart({
        scopes: selectedScopes,
        redirect_after_auth: customRedirect,
        pkce_enabled: pkceEnabled,
        metadata
      });
    } catch (error) {
      toast({
        title: "OAuth Failed",
        description: error.message || "Could not initiate OAuth flow.",
        variant: "destructive",
      });
    }
  };

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied to Clipboard",
      description: `${type} copied successfully.`,
    });
  };

  const getSecurityIcon = (enabled) => enabled ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center">
            <Shield className="h-5 w-5 mr-2" />
            Enhanced Zoom Integration
          </span>
          <div className="flex items-center space-x-2">
            {oauthState?.state_id && (
              <Badge variant="outline" className="text-green-600">
                <CheckCircle className="h-3 w-3 mr-1" />
                OAuth Ready
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSecurityInfo(!showSecurityInfo)}
            >
              {getSecurityIcon(showSecurityInfo)}
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Security Information */}
        {showSecurityInfo && (
          <Alert>
            <Shield className="h-4 w-4" />
            <AlertDescription>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span>Security Features:</span>
                  <div className="flex space-x-1">
                    <Badge variant="outline" className="text-xs">
                      CSRF Protection
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      PKCE {pkceEnabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      Token Encryption
                    </Badge>
                  </div>
                </div>
                {stateId && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">State ID:</span>
                      <div className="flex items-center space-x-1">
                        <code className="text-xs bg-gray-100 px-1 rounded">
                          {stateId.substring(0, 8)}...
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(stateId, 'State ID')}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">CSRF Token:</span>
                      <div className="flex items-center space-x-1">
                        <code className="text-xs bg-gray-100 px-1 rounded">
                          {csrfToken.substring(0, 8)}...
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(csrfToken, 'CSRF Token')}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="scopes" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="scopes">Permissions</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="advanced">Advanced</TabsTrigger>
          </TabsList>

          {/* Scopes Tab */}
          <TabsContent value="scopes" className="space-y-4">
            <div>
              <Label className="text-base font-medium">Permission Scopes</Label>
              <p className="text-sm text-muted-foreground mt-1">
                Select the permissions that ATOM will have access to in your Zoom account.
              </p>
            </div>

            {/* Category Selection */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Quick Selection</Label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {scopeCategories.map(category => (
                  <div key={category.id} className="flex items-center space-x-2 p-2 border rounded">
                    <Checkbox
                      id={`category-${category.id}`}
                      checked={isCategorySelected(category.id)}
                      onCheckedChange={(checked) => handleCategoryToggle(category.id, checked)}
                    />
                    <Label 
                      htmlFor={`category-${category.id}`}
                      className="flex items-center cursor-pointer text-sm"
                    >
                      {category.icon}
                      <span className="ml-1">{category.name}</span>
                    </Label>
                    {isCategoryPartiallySelected(category.id) && (
                      <div className="ml-auto w-2 h-2 bg-yellow-400 rounded-full" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Individual Scopes */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Detailed Permissions</Label>
              <ScrollArea className="h-64 border rounded p-3">
                <div className="space-y-3">
                  {availableScopes.map(scope => (
                    <div key={scope.id} className="flex items-start space-x-3 p-2 border rounded">
                      <Checkbox
                        id={`scope-${scope.id}`}
                        checked={selectedScopes.includes(scope.id)}
                        disabled={scope.required}
                        onCheckedChange={(checked) => handleScopeToggle(scope.id, checked)}
                      />
                      <div className="flex-1">
                        <Label 
                          htmlFor={`scope-${scope.id}`}
                          className={cn(
                            "flex items-center cursor-pointer text-sm font-medium",
                            scope.required && "text-blue-600"
                          )}
                        >
                          {scope.icon}
                          <span className="ml-1">{scope.name}</span>
                          {scope.required && (
                            <Badge variant="outline" className="ml-2 text-xs">
                              Required
                            </Badge>
                          )}
                        </Label>
                        <p className="text-xs text-muted-foreground mt-1">
                          {scope.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Selected Scopes Summary */}
            {selectedScopes.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">
                  Selected Scopes ({selectedScopes.length})
                </Label>
                <div className="flex flex-wrap gap-1">
                  {selectedScopes.map(scopeId => {
                    const scope = availableScopes.find(s => s.id === scopeId);
                    return (
                      <Badge key={scopeId} variant="outline" className="text-xs">
                        {scope?.icon}
                        <span className="ml-1">{scope?.name}</span>
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-4">
            <div className="space-y-4">
              <div>
                <Label className="text-base font-medium">Security Settings</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  Configure advanced security options for the OAuth flow.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="pkce-enabled">PKCE (Proof Key for Code Exchange)</Label>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="pkce-enabled"
                      checked={pkceEnabled}
                      onCheckedChange={setPkceEnabled}
                    />
                    <Label htmlFor="pkce-enabled" className="text-sm">
                      Enable PKCE for enhanced security
                    </Label>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    PKCE adds an additional layer of security to the OAuth flow.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Security Status</Label>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <Shield className="h-4 w-4 text-green-600" />
                      <span className="text-sm">CSRF Protection: Enabled</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Lock className="h-4 w-4 text-green-600" />
                      <span className="text-sm">Token Encryption: Enabled</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RefreshCw className="h-4 w-4 text-green-600" />
                      <span className="text-sm">Auto Refresh: Enabled</span>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-sm font-medium">OAuth Flow Information</Label>
                <div className="mt-2 space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-muted-foreground">Flow Type:</span>
                      <span>Authorization Code with PKCE</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Token Type:</span>
                      <span>Bearer</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">State TTL:</span>
                      <span>10 minutes</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Encryption:</span>
                      <span>FERNET (AES-256)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Advanced Tab */}
          <TabsContent value="advanced" className="space-y-4">
            <div className="space-y-4">
              <div>
                <Label className="text-base font-medium">Advanced Settings</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  Configure advanced options for OAuth customization.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <Label htmlFor="custom-redirect">Custom Redirect URI</Label>
                  <Input
                    id="custom-redirect"
                    type="url"
                    placeholder="https://yourapp.com/oauth/callback"
                    value={customRedirect}
                    onChange={(e) => setCustomRedirect(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Optional: Override the default redirect URI for this OAuth flow.
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="show-advanced"
                    checked={showAdvanced}
                    onCheckedChange={setShowAdvanced}
                  />
                  <Label htmlFor="show-advanced" className="text-sm">
                    Enable advanced debug options
                  </Label>
                </div>
              </div>

              {showAdvanced && (
                <div className="space-y-3 p-3 border rounded bg-gray-50">
                  <Label className="text-sm font-medium">Debug Information</Label>
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">OAuth Version:</span>
                      <span>2.0</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Environment:</span>
                      <span>Production</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Client ID:</span>
                      <span>Configured</span>
                    </div>
                    {oauthState?.state_id && (
                      <>
                        <div>
                          <span className="text-muted-foreground">State ID:</span>
                          <code className="ml-1 text-xs">{oauthState.state_id}</code>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Expires At:</span>
                          <span>{oauthState.expires_at}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* OAuth Authorization Button */}
        <div className="pt-4 border-t">
          <Button
            onClick={handleOAuthClick}
            className="w-full"
            disabled={isLoading || selectedScopes.length === 0}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Initializing OAuth...
              </>
            ) : (
              <>
                <Shield className="h-4 w-4 mr-2" />
                Authorize Zoom Integration
              </>
            )}
          </Button>

          <div className="mt-3 text-center">
            <p className="text-xs text-muted-foreground">
              By clicking "Authorize", you agree to let ATOM access your Zoom account 
              with the selected permissions. You can revoke access at any time.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const OAuthStatusIndicator = ({ 
  oauthStatus, 
  onRefresh, 
  onRevoke, 
  onSwitch,
  isLoading 
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [timeUntilExpiry, setTimeUntilExpiry] = useState(null);

  useEffect(() => {
    if (oauthStatus?.authenticated && oauthStatus?.expires_at) {
      const updateExpiry = () => {
        const now = new Date();
        const expiry = new Date(oauthStatus.expires_at);
        const diff = expiry - now;
        
        if (diff > 0) {
          const hours = Math.floor(diff / (1000 * 60 * 60));
          const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
          setTimeUntilExpiry(`${hours}h ${minutes}m`);
        } else {
          setTimeUntilExpiry('Expired');
        }
      };

      updateExpiry();
      const interval = setInterval(updateExpiry, 60000); // Update every minute
      return () => clearInterval(interval);
    }
  }, [oauthStatus]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'authenticated': return 'text-green-600';
      case 'unauthenticated': return 'text-red-600';
      case 'expiring': return 'text-yellow-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'authenticated': return <CheckCircle className="h-4 w-4" />;
      case 'unauthenticated': return <AlertCircle className="h-4 w-4" />;
      case 'expiring': return <AlertCircle className="h-4 w-4" />;
      default: return <Shield className="h-4 w-4" />;
    }
  };

  const getAccountTypeIcon = (type) => {
    switch (type) {
      case 1: return <User className="h-4 w-4" />;
      case 2: return <Briefcase className="h-4 w-4" />;
      case 3: return <Building className="h-4 w-4" />;
      default: return <User className="h-4 w-4" />;
    }
  };

  const getRoleBadge = (roleId) => {
    switch (roleId) {
      case 0: return <Badge variant="outline">Member</Badge>;
      case 1: return <Badge className="bg-blue-500 text-white">Admin</Badge>;
      case 3: return <Badge className="bg-purple-500 text-white">Owner</Badge>;
      default: return <Badge variant="outline">Unknown</Badge>;
    }
  };

  if (!oauthStatus) {
    return (
      <Alert>
        <Shield className="h-4 w-4" />
        <AlertDescription>
          Loading OAuth status...
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center">
            <Shield className="h-5 w-5 mr-2" />
            Zoom OAuth Status
          </span>
          <div className="flex items-center space-x-2">
            <Badge 
              variant="outline" 
              className={getStatusColor(oauthStatus.authenticated ? 'authenticated' : 'unauthenticated')}
            >
              {getStatusIcon(oauthStatus.authenticated ? 'authenticated' : 'unauthenticated')}
              <span className="ml-1">
                {oauthStatus.authenticated ? 'Connected' : 'Not Connected'}
              </span>
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {oauthStatus.authenticated ? (
          <>
            {/* Connection Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 border rounded">
                <User className="h-6 w-6 mx-auto mb-1 text-blue-600" />
                <div className="text-sm font-medium">{oauthStatus.display_name}</div>
                <div className="text-xs text-muted-foreground">{oauthStatus.email}</div>
              </div>
              
              <div className="text-center p-3 border rounded">
                <Briefcase className="h-6 w-6 mx-auto mb-1 text-green-600" />
                <div className="text-sm font-medium">
                  {getAccountTypeIcon(oauthStatus.account_type)}
                  <span className="ml-1">
                    {oauthStatus.account_type === 1 ? 'Basic' : 
                     oauthStatus.account_type === 2 ? 'Licensed' : 'On-Prem'}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">Account Type</div>
              </div>
              
              <div className="text-center p-3 border rounded">
                <Settings className="h-6 w-6 mx-auto mb-1 text-purple-600" />
                <div className="text-sm font-medium">
                  {getRoleBadge(oauthStatus.role_id)}
                </div>
                <div className="text-xs text-muted-foreground">Role</div>
              </div>
              
              <div className="text-center p-3 border rounded">
                <Clock className="h-6 w-6 mx-auto mb-1 text-orange-600" />
                <div className="text-sm font-medium">{timeUntilExpiry || 'Unknown'}</div>
                <div className="text-xs text-muted-foreground">Time to Expiry</div>
              </div>
            </div>

            {/* Detailed Information */}
            {showDetails && (
              <div className="space-y-4 pt-4 border-t">
                <div>
                  <Label className="text-sm font-medium">Connection Details</Label>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">User ID:</span>
                      <span className="ml-1">{oauthStatus.user_id}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Zoom User ID:</span>
                      <span className="ml-1">{oauthStatus.zoom_user_id}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Account ID:</span>
                      <span className="ml-1">{oauthStatus.account_id}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Last Used:</span>
                      <span className="ml-1">{oauthStatus.last_used_at}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Access Count:</span>
                      <span className="ml-1">{oauthStatus.access_count}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Expires At:</span>
                      <span className="ml-1">{oauthStatus.expires_at}</span>
                    </div>
                  </div>
                </div>

                <div>
                  <Label className="text-sm font-medium">Granted Permissions</Label>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {oauthStatus.scopes?.map(scope => (
                      <Badge key={scope} variant="outline" className="text-xs">
                        {scope.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="text-sm font-medium">Active OAuth States</Label>
                  <div className="mt-2 space-y-1">
                    {oauthStatus.active_oauth_states?.length > 0 ? (
                      oauthStatus.active_oauth_states.map(state => (
                        <div key={state.state_id} className="flex items-center justify-between p-2 border rounded text-xs">
                          <div>
                            <span className="font-medium">State:</span>
                            <code className="ml-1">{state.state_id.substring(0, 8)}...</code>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Status:</span>
                            <Badge variant="outline" className="ml-1 text-xs">
                              {state.state}
                            </Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Expires:</span>
                            <span className="ml-1">{state.expires_at}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-muted-foreground">No active OAuth states</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex space-x-2 pt-4 border-t">
              <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Refresh Status
              </Button>
              
              {onSwitch && (
                <Button variant="outline" onClick={onSwitch}>
                  <Users className="h-4 w-4 mr-2" />
                  Switch Account
                </Button>
              )}
              
              <Button variant="destructive" onClick={onRevoke}>
                <Shield className="h-4 w-4 mr-2" />
                Revoke Access
              </Button>
            </div>
          </>
        ) : (
          /* Not Authenticated State */
          <div className="text-center space-y-4">
            <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
              <Shield className="h-8 w-8 text-gray-400" />
            </div>
            
            <div>
              <h3 className="text-lg font-medium">Zoom Integration Not Connected</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Authorize ATOM to access your Zoom account for meeting management, 
                recordings, and more.
              </p>
            </div>

            <div className="text-left space-y-2">
              <div className="flex items-center space-x-2 text-sm">
                <AlertCircle className="h-4 w-4 text-yellow-600" />
                <span>Authentication required</span>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <RefreshCw className="h-4 w-4 text-blue-600" />
                <span>Secure OAuth 2.0 flow</span>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <Lock className="h-4 w-4 text-green-600" />
                <span>Enterprise-grade security</span>
              </div>
            </div>

            <Button onClick={onRefresh} disabled={isLoading}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Shield className="h-4 w-4 mr-2" />
              )}
              Connect to Zoom
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default {
  EnhancedZoomOAuthFlow,
  OAuthStatusIndicator
};