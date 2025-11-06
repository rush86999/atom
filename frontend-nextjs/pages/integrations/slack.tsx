/**
 * Slack Integration Page
 * Complete Slack integration with comprehensive messaging and collaboration features
 */

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Loader2, 
  MessageSquare, 
  Hash, 
  Users, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Send,
  Paperclip,
  Clock,
  Eye,
  User
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface SlackChannel {
  id: string;
  name: string;
  is_channel: boolean;
  is_group: boolean;
  is_im: boolean;
  is_private: boolean;
  is_archived: boolean;
  name_normalized: string;
  num_members: number;
  topic: string;
  purpose: string;
  created: number;
}

interface SlackMessage {
  ts: string;
  text: string;
  user: string;
  channel: string;
  thread_ts: string;
  username: string;
  bot_id: string;
  files: any[];
  reactions: any[];
  pinned_to: string[];
  message_type: string;
  subtype: string;
  blocks: any[];
  attachments: any[];
  team: string;
  edited: any;
  last_read: string;
}

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email: string;
  image_24: string;
  image_48: string;
  image_72: string;
  image_192: string;
  title: string;
  phone: string;
  team_id: string;
  deleted: boolean;
  status: string;
  is_bot: boolean;
  is_admin: boolean;
  is_owner: boolean;
  has_files: boolean;
  timezone: string;
}

interface SlackStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'error' | 'unavailable';
  timestamp: string;
  components: {
    service?: { status: string; message: string };
    configuration?: { status: string; client_id_configured: boolean; client_secret_configured: boolean };
    database?: { status: string; message: string };
    api?: { status: string; rate_limit_remaining: number; rate_limit_reset: number };
  };
}

export default function SlackIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<SlackStatus | null>(null);
  const [userInfo, setUserInfo] = useState<SlackUser | null>(null);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [users, setUsers] = useState<SlackUser[]>([]);
  const [selectedChannel, setSelectedChannel] = useState('');
  const [messageText, setMessageText] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const SLACK_ENHANCED_URL = `${API_BASE_URL}/api/slack/enhanced`;
  const SLACK_OAUTH_URL = `${API_BASE_URL}/api/auth/slack`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'channels') {
      loadChannels();
    } else if (activeTab === 'messages') {
      loadMessages();
    } else if (activeTab === 'users') {
      loadUsers();
    }
  }, [activeTab, selectedChannel]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'slack_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/users/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUserInfo(data.data.user);
        toast({
          title: "User info loaded",
          description: `Successfully loaded profile for ${data.data.user.name}`,
        });
      } else {
        toast({
          title: "Failed to load user info",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
      toast({
        title: "Error loading user info",
        description: "Could not connect to Slack service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadChannels = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/channels/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          types: 'public_channel,private_channel',
          exclude_archived: true,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setChannels(data.data.channels);
        toast({
          title: "Channels loaded",
          description: `Loaded ${data.data.channels.length} channels`,
        });
      } else {
        toast({
          title: "Failed to load channels",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load channels:', error);
      toast({
        title: "Error loading channels",
        description: "Could not connect to Slack service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async () => {
    if (!selectedChannel) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/messages/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          channel: selectedChannel,
          limit: 50,
          include_all_threads: true
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setMessages(data.data.messages);
        toast({
          title: "Messages loaded",
          description: `Loaded ${data.data.messages.length} messages from ${selectedChannel}`,
        });
      } else {
        toast({
          title: "Failed to load messages",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load messages:', error);
      toast({
        title: "Error loading messages",
        description: "Could not connect to Slack service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/users/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          presence: true,
          limit: 200
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUsers(data.data.users);
        toast({
          title: "Users loaded",
          description: `Loaded ${data.data.users.length} users`,
        });
      } else {
        toast({
          title: "Failed to load users",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load users:', error);
      toast({
        title: "Error loading users",
        description: "Could not connect to Slack service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!messageText.trim() || !selectedChannel) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${SLACK_ENHANCED_URL}/messages/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          channel: selectedChannel,
          text: messageText.trim(),
          parse: 'full'
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setMessageText('');
        toast({
          title: "Message sent",
          description: "Message sent successfully",
        });
        // Reload messages
        setTimeout(() => loadMessages(), 1000);
      } else {
        toast({
          title: "Failed to send message",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      toast({
        title: "Error sending message",
        description: "Could not connect to Slack service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${SLACK_OAUTH_URL}/authorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Redirect to OAuth URL
        window.location.href = data.oauth_url;
      } else {
        toast({
          title: "OAuth failed",
          description: data.error || "Could not initiate OAuth flow",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('OAuth initiation failed:', error);
      toast({
        title: "OAuth error",
        description: "Could not initiate OAuth flow",
        variant: "destructive",
      });
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(parseFloat(timestamp) * 1000).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'error': return 'bg-red-500';
      case 'unavailable': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="h-4 w-4" />;
      case 'degraded': return <AlertCircle className="h-4 w-4" />;
      case 'error': return <AlertCircle className="h-4 w-4" />;
      case 'unavailable': return <AlertCircle className="h-4 w-4" />;
      default: return <AlertCircle className="h-4 w-4" />;
    }
  };

  const getChannelIcon = (channel: SlackChannel) => {
    if (channel.is_private) return <Hash className="h-4 w-4 text-yellow-500" />;
    if (channel.is_group) return <Users className="h-4 w-4 text-blue-500" />;
    if (channel.is_im) return <MessageSquare className="h-4 w-4 text-green-500" />;
    return <Hash className="h-4 w-4 text-purple-500" />;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Slack Integration</h1>
        <div className="flex items-center space-x-2">
          {status && (
            <Badge variant="outline" className={`${getStatusColor(status.status)} text-white`}>
              {getStatusIcon(status.status)}
              <span className="ml-1">{status.status}</span>
            </Badge>
          )}
          <Button onClick={loadStatus} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Status Alert */}
      {status && status.status !== 'healthy' && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Slack integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="channels" className="flex items-center">
            <Hash className="h-4 w-4 mr-2" />
            Channels
          </TabsTrigger>
          <TabsTrigger value="messages" className="flex items-center">
            <MessageSquare className="h-4 w-4 mr-2" />
            Messages
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="oauth" className="flex items-center">
            <Search className="h-4 w-4 mr-2" />
            OAuth
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Service Status */}
            <Card>
              <CardHeader>
                <CardTitle>Service Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {status ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span>Service</span>
                      <Badge variant={status.components.service?.status === 'available' ? 'default' : 'destructive'}>
                        {status.components.service?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Configuration</span>
                      <Badge variant={status.components.configuration?.status === 'configured' ? 'default' : 'destructive'}>
                        {status.components.configuration?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Database</span>
                      <Badge variant={status.components.database?.status === 'connected' ? 'default' : 'destructive'}>
                        {status.components.database?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>API</span>
                      <Badge variant={status.components.api?.status === 'connected' ? 'default' : 'destructive'}>
                        {status.components.api?.status}
                      </Badge>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    <p className="text-sm text-muted-foreground mt-2">Loading status...</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* User Info */}
            <Card>
              <CardHeader>
                <CardTitle>User Profile</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="userId">User ID</Label>
                  <Input
                    id="userId"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="Enter user ID"
                  />
                </div>
                <Button 
                  onClick={loadUserInfo} 
                  disabled={loading || !userId}
                  className="w-full"
                >
                  {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                  Load Profile
                </Button>
                
                {userInfo && (
                  <div className="space-y-2 pt-4 border-t">
                    <div className="flex items-center space-x-3">
                      {userInfo.image_48 && (
                        <img 
                          src={userInfo.image_48} 
                          alt={userInfo.name}
                          className="w-12 h-12 rounded-full"
                        />
                      )}
                      <div>
                        <div className="font-medium">{userInfo.real_name || userInfo.name}</div>
                        <div className="text-sm text-muted-foreground">@{userInfo.name}</div>
                      </div>
                    </div>
                    {userInfo.email && (
                      <div>
                        <span className="font-medium">Email:</span> {userInfo.email}
                      </div>
                    )}
                    {userInfo.title && (
                      <div>
                        <span className="font-medium">Title:</span> {userInfo.title}
                      </div>
                    )}
                    {userInfo.status && (
                      <div>
                        <span className="font-medium">Status:</span> {userInfo.status}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="channels" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Hash className="h-5 w-5 mr-2" />
                Slack Channels
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {channels.length > 0 ? (
                  channels.map((channel) => (
                    <div key={channel.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getChannelIcon(channel)}
                          <h4 className="font-medium">{channel.name}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          {channel.is_private && <Badge variant="outline" className="text-xs">Private</Badge>}
                          {channel.is_archived && <Badge variant="destructive" className="text-xs">Archived</Badge>}
                          <span className="text-sm text-muted-foreground">{channel.num_members} members</span>
                        </div>
                      </div>
                      {channel.topic && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Topic:</strong> {channel.topic}
                        </div>
                      )}
                      {channel.purpose && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Purpose:</strong> {channel.purpose}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No channels found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadChannels} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Channels
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="messages" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <MessageSquare className="h-5 w-5 mr-2" />
                Messages
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Channel Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="channelSelect">Select Channel</Label>
                <Select value={selectedChannel} onValueChange={setSelectedChannel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a channel" />
                  </SelectTrigger>
                  <SelectContent>
                    {channels.map((channel) => (
                      <SelectItem key={channel.id} value={channel.id}>
                        <div className="flex items-center space-x-2">
                          {getChannelIcon(channel)}
                          <span>{channel.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Message Input */}
              {selectedChannel && (
                <div className="space-y-2 mb-4">
                  <Label htmlFor="messageInput">Message</Label>
                  <div className="flex space-x-2">
                    <Textarea
                      id="messageInput"
                      value={messageText}
                      onChange={(e) => setMessageText(e.target.value)}
                      placeholder="Type your message..."
                      className="flex-1"
                      rows={3}
                    />
                    <Button 
                      onClick={sendMessage} 
                      disabled={loading || !messageText.trim()}
                      className="mt-6"
                    >
                      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              )}

              {/* Messages List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {messages.length > 0 ? (
                  messages.map((message) => (
                    <div key={message.ts} className="mb-3">
                      <div className="flex items-start space-x-2">
                        <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-sm">
                          {message.username ? message.username[0].toUpperCase() : '?'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium text-sm">{message.username || 'Unknown'}</span>
                            <span className="text-xs text-muted-foreground">
                              {formatTimestamp(message.ts)}
                            </span>
                          </div>
                          <div className="text-sm">{message.text}</div>
                          {message.files && message.files.length > 0 && (
                            <div className="flex items-center space-x-2 mt-1">
                              <Paperclip className="h-3 w-3" />
                              <span className="text-xs text-muted-foreground">
                                {message.files.length} file(s)
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No messages found. Select a channel to view messages."
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Slack Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {users.length > 0 ? (
                  users.map((user) => (
                    <div key={user.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        <img 
                          src={user.image_48} 
                          alt={user.name}
                          className="w-10 h-10 rounded-full"
                        />
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium">{user.real_name || user.name}</h4>
                            <span className="text-sm text-muted-foreground">@{user.name}</span>
                            {user.is_bot && <Badge variant="outline" className="text-xs">Bot</Badge>}
                            {user.is_admin && <Badge variant="default" className="text-xs">Admin</Badge>}
                          </div>
                          {user.email && (
                            <div className="text-sm text-muted-foreground">{user.email}</div>
                          )}
                          {user.title && (
                            <div className="text-sm text-muted-foreground">{user.title}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No users found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadUsers} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Users
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="oauth" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>OAuth Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="oauthUserId">User ID</Label>
                  <Input
                    id="oauthUserId"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="Enter user ID for OAuth"
                  />
                </div>
                <Button 
                  onClick={initiateOAuth} 
                  disabled={!userId}
                  className="w-full"
                >
                  <Search className="h-4 w-4 mr-2" />
                  Connect to Slack
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Slack OAuth to authorize ATOM access to your workspace.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>OAuth Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {status?.components.oauth ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span>Status</span>
                      <Badge variant="outline">
                        {status.components.oauth.status}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {status.components.oauth.message}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    OAuth status not available
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}