/**
 * 👥 Zoom Account Switching UI Components
 * Multi-account management with enhanced user experience
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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Switch } from '@/components/ui/switch';
import { 
  Users, 
  Plus, 
  Trash2, 
  Settings, 
  ExternalLink, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Activity, 
  Briefcase, 
  Building, 
  GraduationCap, 
  Star, 
  Shield, 
  RefreshCw, 
  Edit, 
  Copy,
  Eye,
  EyeOff,
  Key,
  Lock,
  Unlock,
  History,
  BarChart3,
  Filter,
  Search,
  ChevronDown,
  ChevronRight,
  User,
  Crown
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

// Account Switching Components
export const ZoomAccountManager = ({ 
  accounts, 
  defaultAccount, 
  onSwitchAccount, 
  onAddAccount, 
  onRemoveAccount, 
  onEditAccount, 
  onRefresh,
  isLoading,
  userRole
}) => {
  const { toast } = useToast();
  const [selectedAccount, setSelectedAccount] = useState(defaultAccount?.account_id || '');
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [showAccountDetails, setShowAccountDetails] = useState({});
  const [switchHistory, setSwitchHistory] = useState([]);

  // Filter accounts based on search and type
  const filteredAccounts = accounts.filter(account => {
    const matchesSearch = account.account_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         account.account_email.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesFilter = filterType === 'all' || 
                         (filterType === 'primary' && account.is_primary) ||
                         (filterType === 'business' && account.account_type === 'business') ||
                         (filterType === 'enterprise' && account.account_type === 'enterprise') ||
                         (filterType === 'education' && account.account_type === 'education');
    
    return matchesSearch && matchesFilter;
  });

  // Account type configurations
  const accountTypeConfig = {
    free: { icon: <User className="h-4 w-4" />, color: 'bg-gray-100 text-gray-600', label: 'Free' },
    pro: { icon: <Briefcase className="h-4 w-4" />, color: 'bg-blue-100 text-blue-600', label: 'Pro' },
    business: { icon: <Building className="h-4 w-4" />, color: 'bg-green-100 text-green-600', label: 'Business' },
    enterprise: { icon: <Crown className="h-4 w-4" />, color: 'bg-purple-100 text-purple-600', label: 'Enterprise' },
    education: { icon: <GraduationCap className="h-4 w-4" />, color: 'bg-orange-100 text-orange-600', label: 'Education' }
  };

  const getAccountTypeConfig = (type) => {
    return accountTypeConfig[type] || accountTypeConfig.free;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-600';
      case 'inactive': return 'bg-gray-100 text-gray-600';
      case 'suspended': return 'bg-red-100 text-red-600';
      case 'pending': return 'bg-yellow-100 text-yellow-600';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active': return <CheckCircle className="h-3 w-3" />;
      case 'inactive': return <AlertCircle className="h-3 w-3" />;
      case 'suspended': return <AlertCircle className="h-3 w-3" />;
      case 'pending': return <Clock className="h-3 w-3" />;
      default: return <AlertCircle className="h-3 w-3" />;
    }
  };

  const handleAccountSwitch = async (accountId) => {
    if (accountId === defaultAccount?.account_id) {
      return; // Already the default account
    }

    try {
      const result = await onSwitchAccount(accountId);
      
      if (result?.success) {
        setSelectedAccount(accountId);
        toast({
          title: "Account Switched",
          description: `Successfully switched to ${result.account_name || 'new account'}.`,
        });
        
        // Refresh accounts list
        await onRefresh();
      } else {
        toast({
          title: "Switch Failed",
          description: result?.error || "Failed to switch account.",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Switch Failed",
        description: error.message || "Failed to switch account.",
        variant: "destructive",
      });
    }
  };

  const handleAccountRemove = async (accountId) => {
    const account = accounts.find(a => a.account_id === accountId);
    
    if (account.is_primary) {
      toast({
        title: "Cannot Remove",
        description: "Primary account cannot be removed. Please switch to another account first.",
        variant: "destructive",
      });
      return;
    }

    try {
      const success = await onRemoveAccount(accountId);
      
      if (success) {
        toast({
          title: "Account Removed",
          description: `Successfully removed ${account.account_name}.`,
        });
        
        // Clear selection if removed account was selected
        if (selectedAccount === accountId) {
          setSelectedAccount('');
        }
        
        // Refresh accounts list
        await onRefresh();
      } else {
        toast({
          title: "Removal Failed",
          description: "Failed to remove account.",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Removal Failed",
        description: error.message || "Failed to remove account.",
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

  const getLastUsedText = (lastUsedAt) => {
    if (!lastUsedAt) return 'Never';
    
    const now = new Date();
    const lastUsed = new Date(lastUsedAt);
    const diffMs = now - lastUsed;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    return `${diffDays} days ago`;
  };

  const formatAccessCount = (count) => {
    if (count < 1000) return count.toString();
    if (count < 1000000) return `${(count / 1000).toFixed(1)}K`;
    return `${(count / 1000000).toFixed(1)}M`;
  };

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center">
            <Users className="h-6 w-6 mr-2" />
            Zoom Account Management
          </h2>
          <p className="text-muted-foreground">
            Manage multiple Zoom accounts and switch between them seamlessly
          </p>
        </div>
        
        <div className="flex space-x-2">
          <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
            {isLoading ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Refresh
          </Button>
          
          <Button onClick={() => setShowAddAccount(!showAddAccount)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Account
          </Button>
        </div>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  type="text"
                  placeholder="Search accounts by name or email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            
            <div className="flex space-x-2">
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Accounts</SelectItem>
                  <SelectItem value="primary">Primary Only</SelectItem>
                  <SelectItem value="business">Business</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                  <SelectItem value="education">Education</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Account Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <Users className="h-8 w-8 mx-auto mb-2 text-blue-600" />
            <div className="text-2xl font-bold">{accounts.length}</div>
            <div className="text-sm text-muted-foreground">Total Accounts</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-600" />
            <div className="text-2xl font-bold">
              {accounts.filter(a => a.account_status === 'active').length}
            </div>
            <div className="text-sm text-muted-foreground">Active</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <Star className="h-8 w-8 mx-auto mb-2 text-yellow-600" />
            <div className="text-2xl font-bold">
              {accounts.filter(a => a.is_primary).length}
            </div>
            <div className="text-sm text-muted-foreground">Primary</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <Activity className="h-8 w-8 mx-auto mb-2 text-purple-600" />
            <div className="text-2xl font-bold">
              {formatAccessCount(accounts.reduce((sum, a) => sum + a.access_count, 0))}
            </div>
            <div className="text-sm text-muted-foreground">Total Access</div>
          </CardContent>
        </Card>
      </div>

      {/* Add Account Form */}
      {showAddAccount && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center">
                <Plus className="h-5 w-5 mr-2" />
                Add New Account
              </span>
              <Button variant="ghost" size="sm" onClick={() => setShowAddAccount(false)}>
                <EyeOff className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Add a new Zoom account by completing OAuth authorization. Each account will be 
              securely isolated with its own permissions and tokens.
            </p>
            
            <div className="flex justify-center">
              <Button onClick={onAddAccount} disabled={isLoading}>
                {isLoading ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Shield className="h-4 w-4 mr-2" />
                )}
                Start OAuth for New Account
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Accounts List */}
      <div className="space-y-4">
        {filteredAccounts.length === 0 ? (
          <Card>
            <CardContent className="pt-6 text-center">
              <Users className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-medium mb-2">No Accounts Found</h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery || filterType !== 'all' 
                  ? 'No accounts match your search criteria.' 
                  : 'No Zoom accounts have been added yet.'}
              </p>
              
              {!searchQuery && filterType === 'all' && (
                <Button onClick={() => setShowAddAccount(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Your First Account
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          filteredAccounts.map(account => {
            const typeConfig = getAccountTypeConfig(account.account_type);
            const isDefault = defaultAccount?.account_id === account.account_id;
            
            return (
              <Card key={account.account_id} className={cn(
                "transition-all duration-200",
                isDefault && "ring-2 ring-blue-500 ring-offset-2"
              )}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Avatar className="h-12 w-12">
                        <AvatarImage src={`https://ui-avatars.com/api/?name=${encodeURIComponent(account.account_name)}&background=random`} />
                        <AvatarFallback>
                          {account.account_name.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      
                      <div>
                        <div className="flex items-center space-x-2">
                          <CardTitle className="text-lg">{account.account_name}</CardTitle>
                          
                          {isDefault && (
                            <Badge className="bg-blue-500 text-white">
                              <Star className="h-3 w-3 mr-1" />
                              Default
                            </Badge>
                          )}
                          
                          {account.is_primary && (
                            <Badge variant="outline" className="text-blue-600">
                              <Crown className="h-3 w-3 mr-1" />
                              Primary
                            </Badge>
                          )}
                        </div>
                        
                        <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                          <span>{account.account_email}</span>
                          <Separator orientation="vertical" className="h-4" />
                          <span>{account.zoom_role_name}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Badge className={getStatusColor(account.account_status)}>
                        {getStatusIcon(account.account_status)}
                        <span className="ml-1 capitalize">{account.account_status}</span>
                      </Badge>
                      
                      <Badge className={typeConfig.color}>
                        {typeConfig.icon}
                        <span className="ml-1">{typeConfig.label}</span>
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-4">
                  {/* Account Details */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Account ID:</span>
                      <div className="flex items-center space-x-1">
                        <code className="text-xs bg-gray-100 px-1 rounded">
                          {account.zoom_account_id.substring(0, 8)}...
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(account.zoom_account_id, 'Account ID')}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    
                    <div>
                      <span className="text-muted-foreground">User ID:</span>
                      <div className="flex items-center space-x-1">
                        <code className="text-xs bg-gray-100 px-1 rounded">
                          {account.zoom_user_id.substring(0, 8)}...
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(account.zoom_user_id, 'User ID')}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    
                    <div>
                      <span className="text-muted-foreground">Last Used:</span>
                      <div>{getLastUsedText(account.last_used_at)}</div>
                    </div>
                    
                    <div>
                      <span className="text-muted-foreground">Access Count:</span>
                      <div>{formatAccessCount(account.access_count)}</div>
                    </div>
                  </div>

                  {/* Permissions */}
                  {account.permissions && account.permissions.length > 0 && (
                    <div>
                      <span className="text-sm font-medium">Permissions</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {account.permissions.slice(0, 5).map(permission => (
                          <Badge key={permission} variant="outline" className="text-xs">
                            {permission.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </Badge>
                        ))}
                        {account.permissions.length > 5 && (
                          <Badge variant="outline" className="text-xs">
                            +{account.permissions.length - 5} more
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Account Details Toggle */}
                  <div className="flex items-center justify-between">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowAccountDetails(prev => ({
                        ...prev,
                        [account.account_id]: !prev[account.account_id]
                      }))}
                    >
                      {showAccountDetails[account.account_id] ? (
                        <EyeOff className="h-4 w-4 mr-1" />
                      ) : (
                        <Eye className="h-4 w-4 mr-1" />
                      )}
                      {showAccountDetails[account.account_id] ? 'Hide Details' : 'Show Details'}
                    </Button>
                    
                    <div className="text-xs text-muted-foreground">
                      Created {new Date(account.created_at).toLocaleDateString()}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {showAccountDetails[account.account_id] && (
                    <div className="pt-4 border-t space-y-3">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">User Type:</span>
                          <div>{account.zoom_user_type === 1 ? 'Basic' : account.zoom_user_type === 2 ? 'Licensed' : 'On-Prem'}</div>
                        </div>
                        
                        <div>
                          <span className="text-muted-foreground">Account Created:</span>
                          <div>{new Date(account.created_at).toLocaleDateString()}</div>
                        </div>
                        
                        <div>
                          <span className="text-muted-foreground">Last Used:</span>
                          <div>{account.last_used_at ? new Date(account.last_used_at).toLocaleString() : 'Never'}</div>
                        </div>
                        
                        <div>
                          <span className="text-muted-foreground">Access Count:</span>
                          <div>{account.access_count.toLocaleString()}</div>
                        </div>
                      </div>

                      {account.metadata && Object.keys(account.metadata).length > 0 && (
                        <div>
                          <span className="text-sm font-medium">Metadata</span>
                          <div className="mt-1 p-2 bg-gray-50 rounded text-xs">
                            <pre className="whitespace-pre-wrap">
                              {JSON.stringify(account.metadata, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
                
                <CardFooter className="pt-3">
                  <div className="flex w-full justify-between items-center">
                    <div className="flex space-x-2">
                      <Button
                        variant={isDefault ? "default" : "outline"}
                        onClick={() => handleAccountSwitch(account.account_id)}
                        disabled={isDefault || isLoading}
                      >
                        {isDefault ? (
                          <>
                            <CheckCircle className="h-4 w-4 mr-1" />
                            Current Account
                          </>
                        ) : (
                          <>
                            <RefreshCw className="h-4 w-4 mr-1" />
                            Switch to Account
                          </>
                        )}
                      </Button>
                      
                      <Button variant="outline" size="sm" onClick={() => onEditAccount(account)}>
                        <Edit className="h-4 w-4" />
                      </Button>
                      
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => copyToClipboard(account.account_email, 'Email Address')}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    
                    {!account.is_primary && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleAccountRemove(account.account_id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Remove
                      </Button>
                    )}
                  </div>
                </CardFooter>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
};

export const AccountSwitchHistory = ({ 
  switchHistory, 
  onLoadMore,
  isLoading,
  hasMore 
}) => {
  const [showDetails, setShowDetails] = useState({});

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatReason = (reason) => {
    if (!reason) return 'User initiated';
    
    // Capitalize first letter
    return reason.charAt(0).toUpperCase() + reason.slice(1);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <History className="h-5 w-5 mr-2" />
          Account Switch History
        </CardTitle>
      </CardHeader>
      <CardContent>
        {switchHistory.length === 0 ? (
          <div className="text-center py-8">
            <History className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <h3 className="text-lg font-medium mb-2">No Switch History</h3>
            <p className="text-muted-foreground">
              Account switches will appear here once you start using multiple accounts.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {switchHistory.map((switchEvent, index) => (
              <div key={index} className="flex items-start space-x-3 p-3 border rounded">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <RefreshCw className="h-4 w-4 text-blue-600" />
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">
                      Switched to Account {switchEvent.current_account_id?.substring(0, 8)}...
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatDate(switchEvent.switch_time)}
                    </div>
                  </div>
                  
                  <div className="text-sm text-muted-foreground">
                    {switchEvent.previous_account_id ? (
                      <>
                        From {switchEvent.previous_account_id.substring(0, 8)}... to {switchEvent.current_account_id.substring(0, 8)}...
                      </>
                    ) : (
                      <>First account selection: {switchEvent.current_account_id.substring(0, 8)}...</>
                    )}
                  </div>
                  
                  <div className="text-sm">
                    Reason: {formatReason(switchEvent.switch_reason)}
                  </div>
                  
                  {switchEvent.ip_address && (
                    <div className="text-xs text-muted-foreground">
                      IP: {switchEvent.ip_address} • User Agent: {switchEvent.user_agent?.substring(0, 50)}...
                    </div>
                  )}
                </div>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDetails(prev => ({
                    ...prev,
                    [index]: !prev[index]
                  }))}
                >
                  {showDetails[index] ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                </Button>
              </div>
            ))}
            
            {hasMore && (
              <div className="text-center pt-4">
                <Button variant="outline" onClick={onLoadMore} disabled={isLoading}>
                  {isLoading ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    'Load More'
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default {
  ZoomAccountManager,
  AccountSwitchHistory
};