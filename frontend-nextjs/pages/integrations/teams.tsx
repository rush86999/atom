/**
 * Microsoft Teams Integration Page
 * Complete Teams integration with comprehensive messaging and collaboration features
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
  Users, 
  Calendar, 
  FileText, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Send,
  Video,
  Phone,
  Mail,
  Folder,
  Clock,
  Eye,
  User
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface TeamsChannel {
  id: string;
  displayName: string;
  description: string;
  email: string;
  webUrl: string;
  membershipType: string;
  tenantId: string;
  isFavoriteByDefault: boolean;
  teamId: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
}

interface TeamsMessage {
  id: string;
  subject: string;
  body: string;
  summary: string;
  importance: string;
  locale: string;
  fromUser: string;
  fromEmail: string;
  conversationId: string;
  threadId: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  attachments: any[];
  mentions: any[];
  reactions: any[];
}

interface TeamsUser {
  id: string;
  displayName: string;
  givenName: string;
  surname: string;
  mail: string;
  userPrincipalName: string;
  jobTitle: string;
  officeLocation: string;
  businessPhones: string[];
  mobilePhone: string;
  photoAvailable: boolean;
  accountEnabled: boolean;
  userType: string;
}

interface TeamsMeeting {
  id: string;
  subject: string;
  body: string;
  startDateTime: string;
  endDateTime: string;
  location: string;
  attendees: any[];
  importance: string;
  isOnlineMeeting: boolean;
  onlineMeetingUrl: string;
  joinWebUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
}

interface TeamsFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  fileType: string;
  webUrl: string;
  createdBy: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  parentReference: any;
  shared: any;
}

interface TeamsStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'error' | 'unavailable';
  timestamp: string;
  components: {
    service?: { status: string; message: string };
    configuration?: { status: string; client_id_configured: boolean };
    database?: { status: string; message: string };
    api?: { status: string; rate_limit_remaining: number };
  };
}

export default function TeamsIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<TeamsStatus | null>(null);
  const [userInfo, setUserInfo] = useState<TeamsUser | null>(null);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [messages, setMessages] = useState<TeamsMessage[]>([]);
  const [users, setUsers] = useState<TeamsUser[]>([]);
  const [meetings, setMeetings] = useState<TeamsMeeting[]>([]);
  const [files, setFiles] = useState<TeamsFile[]>([]);
  const [selectedChannel, setSelectedChannel] = useState('');
  const [messageText, setMessageText] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const TEAMS_ENHANCED_URL = `${API_BASE_URL}/api/integrations/teams`;
  const TEAMS_OAUTH_URL = `${API_BASE_URL}/api/auth/teams`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'channels') {
      loadChannels();
    } else if (activeTab === 'messages') {
      loadMessages();
    } else if (activeTab === 'users') {
      loadUsers();
    } else if (activeTab === 'meetings') {
      loadMeetings();
    } else if (activeTab === 'files') {
      loadFiles();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'teams_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/users/profile`, {
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
          description: `Successfully loaded profile for ${data.data.user.displayName}`,
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
        description: "Could not connect to Teams service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadChannels = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/teams/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setChannels(data.data.teams);
        toast({
          title: "Teams channels loaded",
          description: `Loaded ${data.data.teams.length} channels`,
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
        description: "Could not connect to Teams service",
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
      const response = await fetch(`${TEAMS_ENHANCED_URL}/messages/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          channel_id: selectedChannel,
          limit: 50
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
        description: "Could not connect to Teams service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/users/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
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
        description: "Could not connect to Teams service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMeetings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/meetings/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setMeetings(data.data.meetings);
        toast({
          title: "Meetings loaded",
          description: `Loaded ${data.data.meetings.length} meetings`,
        });
      } else {
        toast({
          title: "Failed to load meetings",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load meetings:', error);
      toast({
        title: "Error loading meetings",
        description: "Could not connect to Teams service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadFiles = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TEAMS_ENHANCED_URL}/files/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setFiles(data.data.files);
        toast({
          title: "Files loaded",
          description: `Loaded ${data.data.files.length} files`,
        });
      } else {
        toast({
          title: "Failed to load files",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load files:', error);
      toast({
        title: "Error loading files",
        description: "Could not connect to Teams service",
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
      const response = await fetch(`${TEAMS_ENHANCED_URL}/messages/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          channel_id: selectedChannel,
          message: messageText.trim()
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
        description: "Could not connect to Teams service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${TEAMS_OAUTH_URL}/authorize`, {
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

  const formatDateTime = (dateTime: string) => {
    return new Date(dateTime).toLocaleString();
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

  const getChannelIcon = (channel: TeamsChannel) => {
    switch (channel.membershipType) {
      case 'private': return <Users className="h-4 w-4 text-yellow-500" />;
      case 'shared': return <Folder className="h-4 w-4 text-blue-500" />;
      case 'standard': return <MessageSquare className="h-4 w-4 text-green-500" />;
      default: return <MessageSquare className="h-4 w-4 text-purple-500" />;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Microsoft Teams Integration</h1>
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
            Teams integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="channels" className="flex items-center">
            <MessageSquare className="h-4 w-4 mr-2" />
            Channels
          </TabsTrigger>
          <TabsTrigger value="messages" className="flex items-center">
            <Mail className="h-4 w-4 mr-2" />
            Messages
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="meetings" className="flex items-center">
            <Calendar className="h-4 w-4 mr-2" />
            Meetings
          </TabsTrigger>
          <TabsTrigger value="files" className="flex items-center">
            <FileText className="h-4 w-4 mr-2" />
            Files
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
                      {userInfo.photoAvailable && (
                        <div className="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center">
                          <User className="w-6 h-6" />
                        </div>
                      )}
                      <div>
                        <div className="font-medium">{userInfo.displayName}</div>
                        <div className="text-sm text-muted-foreground">{userInfo.userPrincipalName}</div>
                      </div>
                    </div>
                    {userInfo.jobTitle && (
                      <div>
                        <span className="font-medium">Title:</span> {userInfo.jobTitle}
                      </div>
                    )}
                    {userInfo.mail && (
                      <div>
                        <span className="font-medium">Email:</span> {userInfo.mail}
                      </div>
                    )}
                    {userInfo.officeLocation && (
                      <div>
                        <span className="font-medium">Location:</span> {userInfo.officeLocation}
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
                <MessageSquare className="h-5 w-5 mr-2" />
                Teams Channels
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
                          <h4 className="font-medium">{channel.displayName}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          {channel.membershipType === 'private' && <Badge variant="outline" className="text-xs">Private</Badge>}
                          {channel.isFavoriteByDefault && <Badge variant="default" className="text-xs">Favorite</Badge>}
                        </div>
                      </div>
                      {channel.description && (
                        <div className="text-sm text-muted-foreground">
                          {channel.description}
                        </div>
                      )}
                      <div className="text-sm text-muted-foreground">
                        <strong>Email:</strong> {channel.email}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Created:</strong> {formatDateTime(channel.createdDateTime)}
                      </div>
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
                <Mail className="h-5 w-5 mr-2" />
                Teams Messages
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
                          <span>{channel.displayName}</span>
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
                    <div key={message.id} className="mb-3">
                      <div className="flex items-start space-x-2">
                        <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-sm">
                          {message.fromUser ? message.fromUser[0].toUpperCase() : '?'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium text-sm">{message.fromUser}</span>
                            <span className="text-xs text-muted-foreground">
                              {formatDateTime(message.createdDateTime)}
                            </span>
                            {message.importance === 'high' && <Badge variant="destructive" className="text-xs">Important</Badge>}
                          </div>
                          <div className="text-sm">{message.body}</div>
                          {message.attachments && message.attachments.length > 0 && (
                            <div className="flex items-center space-x-2 mt-1">
                              <FileText className="h-3 w-3" />
                              <span className="text-xs text-muted-foreground">
                                {message.attachments.length} attachment(s)
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
                Teams Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {users.length > 0 ? (
                  users.map((user) => (
                    <div key={user.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
                          {user.photoAvailable ? <Eye className="w-5 h-5" /> : <User className="w-5 h-5" />}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium">{user.displayName}</h4>
                            <span className="text-sm text-muted-foreground">({user.userPrincipalName})</span>
                          </div>
                          {user.jobTitle && (
                            <div className="text-sm text-muted-foreground">{user.jobTitle}</div>
                          )}
                        </div>
                      </div>
                      {user.mail && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Email:</strong> {user.mail}
                        </div>
                      )}
                      {user.officeLocation && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Location:</strong> {user.officeLocation}
                        </div>
                      )}
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

        <TabsContent value="meetings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calendar className="h-5 w-5 mr-2" />
                Teams Meetings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {meetings.length > 0 ? (
                  meetings.map((meeting) => (
                    <div key={meeting.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{meeting.subject}</h4>
                        {meeting.isOnlineMeeting && <Badge variant="outline" className="text-xs">Online</Badge>}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Start:</strong> {formatDateTime(meeting.startDateTime)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>End:</strong> {formatDateTime(meeting.endDateTime)}
                      </div>
                      {meeting.location && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Location:</strong> {meeting.location}
                        </div>
                      )}
                      {meeting.isOnlineMeeting && meeting.joinWebUrl && (
                        <div className="flex items-center space-x-2 mt-2">
                          <Video className="h-3 w-3" />
                          <a 
                            href={meeting.joinWebUrl} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-sm text-blue-500 hover:underline"
                          >
                            Join Meeting
                          </a>
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No meetings found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadMeetings} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Meetings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="files" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <FileText className="h-5 w-5 mr-2" />
                Teams Files
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {files.length > 0 ? (
                  files.map((file) => (
                    <div key={file.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <FileText className="h-4 w-4 text-blue-500" />
                          <h4 className="font-medium">{file.name}</h4>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          {formatFileSize(file.size)}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Type:</strong> {file.mimeType}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Created:</strong> {formatDateTime(file.createdDateTime)}
                      </div>
                      {file.webUrl && (
                        <div className="flex items-center space-x-2 mt-2">
                          <Eye className="h-3 w-3" />
                          <a 
                            href={file.webUrl} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-sm text-blue-500 hover:underline"
                          >
                            View File
                          </a>
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No files found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadFiles} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Files
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
                  Connect to Teams
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Microsoft OAuth to authorize ATOM access to your Teams workspace.
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