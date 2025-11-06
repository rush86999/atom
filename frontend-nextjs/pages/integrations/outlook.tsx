/**
 * Outlook Integration Page
 * Complete Microsoft Outlook integration with enhanced features
 */

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Mail, Calendar, Users, Search, Settings, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface OutlookUser {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle?: string;
  officeLocation?: string;
  businessPhones: string[];
  mobilePhone?: string;
}

interface OutlookEmail {
  id: string;
  subject: string;
  from_address: {
    emailAddress: {
      address: string;
      name?: string;
    };
  };
  to_addresses: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
  }>;
  body: string;
  bodyContentType: 'text' | 'html';
  receivedDateTime: string;
  isRead: boolean;
  hasAttachments: boolean;
  importance: 'low' | 'normal' | 'high';
  conversationId?: string;
  webLink?: string;
}

interface OutlookEvent {
  id: string;
  subject: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location?: {
    displayName: string;
  };
  attendees?: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
    type: 'required' | 'optional' | 'resource';
  }>;
  isAllDay: boolean;
  sensitivity: 'normal' | 'personal' | 'private' | 'confidential';
  showAs: 'free' | 'tentative' | 'busy' | 'oof';
}

interface OutlookFolder {
  id: string;
  displayName: string;
  parentFolderId: string;
  unreadItemCount: number;
  totalItemCount: number;
  folderType: string;
}

interface OutlookStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'error' | 'unavailable';
  timestamp: string;
  components: {
    service?: { status: string; message: string };
    configuration?: { status: string; client_id_configured: boolean; client_secret_configured: boolean; tenant_id_configured: boolean };
    database?: { status: string; message: string };
  };
}

export default function OutlookIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<OutlookStatus | null>(null);
  const [userInfo, setUserInfo] = useState<OutlookUser | null>(null);
  const [emails, setEmails] = useState<OutlookEmail[]>([]);
  const [events, setEvents] = useState<OutlookEvent[]>([]);
  const [folders, setFolders] = useState<OutlookFolder[]>([]);
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const OUTLOOK_ENHANCED_URL = `${API_BASE_URL}/api/outlook/enhanced`;
  const OUTLOOK_OAUTH_URL = `${API_BASE_URL}/api/auth/outlook-new`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'emails') {
      loadEmails();
    } else if (activeTab === 'calendar') {
      loadEvents();
    } else if (activeTab === 'folders') {
      loadFolders();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${OUTLOOK_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'outlook_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${OUTLOOK_ENHANCED_URL}/user/profile/enhanced?user_id=${userId}`);
      const data = await response.json();
      
      if (data.ok) {
        setUserInfo(data.data.profile);
        toast({
          title: "User info loaded",
          description: `Successfully loaded profile for ${data.data.profile.displayName}`,
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
        description: "Could not connect to Outlook service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadEmails = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${OUTLOOK_ENHANCED_URL}/emails/enhanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          folder: 'inbox',
          max_results: 20,
          order_by: 'receivedDateTime DESC'
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setEmails(data.data.emails);
        toast({
          title: "Emails loaded",
          description: `Loaded ${data.data.emails.length} emails from inbox`,
        });
      } else {
        toast({
          title: "Failed to load emails",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load emails:', error);
      toast({
        title: "Error loading emails",
        description: "Could not connect to Outlook service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadEvents = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${OUTLOOK_ENHANCED_URL}/calendar/events/upcoming?user_id=${userId}&days=7`);
      const data = await response.json();
      
      if (data.ok) {
        setEvents(data.data.events);
        toast({
          title: "Calendar events loaded",
          description: `Loaded ${data.data.events.length} upcoming events`,
        });
      } else {
        toast({
          title: "Failed to load events",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load events:', error);
      toast({
        title: "Error loading events",
        description: "Could not connect to Outlook service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadFolders = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${OUTLOOK_ENHANCED_URL}/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setFolders(data.data.folders);
        toast({
          title: "Folders loaded",
          description: `Loaded ${data.data.folders.length} email folders`,
        });
      } else {
        toast({
          title: "Failed to load folders",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load folders:', error);
      toast({
        title: "Error loading folders",
        description: "Could not connect to Outlook service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${OUTLOOK_OAUTH_URL}/authorize?user_id=${userId}`);
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

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Outlook Integration</h1>
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
            Outlook integration is {status.status}. 
            {status.components.configuration?.status === 'incomplete' && 
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
          <TabsTrigger value="emails" className="flex items-center">
            <Mail className="h-4 w-4 mr-2" />
            Emails
          </TabsTrigger>
          <TabsTrigger value="calendar" className="flex items-center">
            <Calendar className="h-4 w-4 mr-2" />
            Calendar
          </TabsTrigger>
          <TabsTrigger value="folders" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Folders
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
                    <div>
                      <span className="font-medium">Name:</span> {userInfo.displayName}
                    </div>
                    <div>
                      <span className="font-medium">Email:</span> {userInfo.mail}
                    </div>
                    {userInfo.jobTitle && (
                      <div>
                        <span className="font-medium">Title:</span> {userInfo.jobTitle}
                      </div>
                    )}
                    {userInfo.officeLocation && (
                      <div>
                        <span className="font-medium">Office:</span> {userInfo.officeLocation}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="emails" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Mail className="h-5 w-5 mr-2" />
                Recent Emails
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {emails.length > 0 ? (
                  emails.map((email) => (
                    <div key={email.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium truncate">{email.subject}</h4>
                        <Badge variant={email.isRead ? 'outline' : 'default'}>
                          {email.isRead ? 'Read' : 'Unread'}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        From: {email.from_address.emailAddress.name || email.from_address.emailAddress.address}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {formatDateTime(email.receivedDateTime)}
                      </div>
                      {email.hasAttachments && (
                        <Badge variant="outline" className="text-xs">
                          Has attachments
                        </Badge>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No emails found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadEmails} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Emails
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="calendar" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calendar className="h-5 w-5 mr-2" />
                Upcoming Events (Next 7 Days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {events.length > 0 ? (
                  events.map((event) => (
                    <div key={event.id} className="p-3 border rounded-lg space-y-2">
                      <h4 className="font-medium">{event.subject}</h4>
                      {event.location && (
                        <div className="text-sm text-muted-foreground">
                          📍 {event.location.displayName}
                        </div>
                      )}
                      <div className="text-sm text-muted-foreground">
                        🕐 {formatDateTime(event.start.dateTime)} - {formatDateTime(event.end.dateTime)}
                      </div>
                      {event.attendees && event.attendees.length > 0 && (
                        <div className="text-sm text-muted-foreground">
                          👥 {event.attendees.length} attendees
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No upcoming events"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadEvents} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Events
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="folders" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Email Folders
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {folders.length > 0 ? (
                  folders.map((folder) => (
                    <div key={folder.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{folder.displayName}</h4>
                        <Badge variant="outline">{folder.folderType}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {folder.totalItemCount} total items, {folder.unreadItemCount} unread
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No folders found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadFolders} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Folders
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
                  Connect to Outlook
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Microsoft OAuth to authorize ATOM access to your Outlook account.
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