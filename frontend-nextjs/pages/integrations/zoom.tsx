/**
 * Zoom Integration Page
 * Complete Zoom integration with comprehensive meeting and video conferencing features
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
  Video, 
  Calendar, 
  Users, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Clock,
  Mic,
  MicOff,
  VideoOff,
  Monitor,
  MessageSquare,
  Shield,
  Cloud,
  FileText,
  Search,
  ChevronRight,
  Filter
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface ZoomMeeting {
  id: string;
  topic: string;
  type: number;
  start_time: string;
  duration: number;
  timezone: string;
  agenda?: string;
  password?: string;
  status: string;
  join_url: string;
  start_url: string;
  settings: {
    host_video: boolean;
    participant_video: boolean;
    cn_meeting: boolean;
    in_meeting: boolean;
    join_before_host: boolean;
    mute_upon_entry: boolean;
    watermark: boolean;
    use_pmi: boolean;
    approval_type: number;
    audio: string;
    auto_recording: string;
    enforce_login: boolean;
    waiting_room: boolean;
    allow_multiple_devices: boolean;
    close_registration: boolean;
    authentication_type: number;
  };
}

interface ZoomUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  display_name: string;
  type: number;
  role_name: string;
  pmi: number;
    use_pmi: boolean;
    vanity_url: string;
    personal_meeting_url: string;
    timezone: string;
    verified: number;
    dept: string;
    created_at: string;
    last_login_time: string;
    pic_url: string;
}

interface ZoomRecording {
  id: string;
  uuid: string;
  account_id: string;
  host_id: string;
  topic: string;
  type: number;
  start_time: string;
  timezone: string;
  duration: number;
  total_size: number;
  recording_count: number;
  password?: string;
  share_url: string;
  download_url?: string;
  recording_files: Array<{
    id: string;
    download_url: string;
    play_url: string;
    recording_type: string;
    file_type: string;
    file_size: number;
    recording_start: string;
    recording_end: string;
  }>;
}

interface ZoomWebinar {
  id: string;
  uuid: string;
  topic: string;
  type: number;
  start_time: string;
  duration: number;
  timezone: string;
  agenda?: string;
  password?: string;
  status: string;
  join_url: string;
  start_url: string;
  settings: {
    host_video: boolean;
    participant_video: boolean;
    panelists_video: boolean;
    practice_session: boolean;
    hd_video: boolean;
    on_demand: boolean;
    auto_recording: string;
    enforce_login: boolean;
    show_share_button: boolean;
    allow_multiple_devices: boolean;
  };
}

interface ZoomStatus {
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

export default function ZoomIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<ZoomStatus | null>(null);
  const [userInfo, setUserInfo] = useState<ZoomUser | null>(null);
  const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
  const [recordings, setRecordings] = useState<ZoomRecording[]>([]);
  const [webinars, setWebinars] = useState<ZoomWebinar[]>([]);
  const [meetingTopic, setMeetingTopic] = useState('');
  const [meetingDescription, setMeetingDescription] = useState('');
  const [meetingDate, setMeetingDate] = useState('');
  const [meetingTime, setMeetingTime] = useState('');
  const [meetingDuration, setMeetingDuration] = useState('60');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const ZOOM_ENHANCED_URL = `${API_BASE_URL}/api/integrations/zoom`;
  const ZOOM_OAUTH_URL = `${API_BASE_URL}/api/auth/zoom`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'meetings') {
      loadMeetings();
    } else if (activeTab === 'recordings') {
      loadRecordings();
    } else if (activeTab === 'webinars') {
      loadWebinars();
    } else if (activeTab === 'users') {
      loadUserInfo();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${ZOOM_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'zoom_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${ZOOM_ENHANCED_URL}/users/profile`, {
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
          description: `Successfully loaded profile for ${data.data.user.display_name}`,
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
        description: "Could not connect to Zoom service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMeetings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${ZOOM_ENHANCED_URL}/meetings/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
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
        description: "Could not connect to Zoom service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadRecordings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${ZOOM_ENHANCED_URL}/recordings/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setRecordings(data.data.recordings);
        toast({
          title: "Recordings loaded",
          description: `Loaded ${data.data.recordings.length} recordings`,
        });
      } else {
        toast({
          title: "Failed to load recordings",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load recordings:', error);
      toast({
        title: "Error loading recordings",
        description: "Could not connect to Zoom service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadWebinars = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${ZOOM_ENHANCED_URL}/webinars/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setWebinars(data.data.webinars);
        toast({
          title: "Webinars loaded",
          description: `Loaded ${data.data.webinars.length} webinars`,
        });
      } else {
        toast({
          title: "Failed to load webinars",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load webinars:', error);
      toast({
        title: "Error loading webinars",
        description: "Could not connect to Zoom service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createMeeting = async () => {
    if (!meetingTopic.trim() || !meetingDate || !meetingTime) return;
    
    setLoading(true);
    try {
      const startDateTime = new Date(`${meetingDate}T${meetingTime}:00`);
      
      const response = await fetch(`${ZOOM_ENHANCED_URL}/meetings/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          meeting: {
            topic: meetingTopic.trim(),
            agenda: meetingDescription.trim(),
            start_time: startDateTime.toISOString(),
            duration: parseInt(meetingDuration),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            type: 2, // Scheduled meeting
            settings: {
              host_video: true,
              participant_video: true,
              join_before_host: false,
              mute_upon_entry: true,
              auto_recording: 'cloud'
            }
          }
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setMeetingTopic('');
        setMeetingDescription('');
        setMeetingDate('');
        setMeetingTime('');
        setMeetingDuration('60');
        toast({
          title: "Meeting created",
          description: "Meeting scheduled successfully",
        });
        // Reload meetings
        setTimeout(() => loadMeetings(), 1000);
      } else {
        toast({
          title: "Failed to create meeting",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to create meeting:', error);
      toast({
        title: "Error creating meeting",
        description: "Could not connect to Zoom service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${ZOOM_OAUTH_URL}/authorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
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

  const getMeetingIcon = (meeting: ZoomMeeting) => {
    if (meeting.settings.host_video) {
      return <Video className="h-6 w-6 text-blue-500" />;
    } else {
      return <VideoOff className="h-6 w-6 text-gray-500" />;
    }
  };

  const getMeetingStatusColor = (status: string) => {
    switch (status) {
      case 'scheduled': return 'bg-blue-500';
      case 'started': return 'bg-green-500';
      case 'ended': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getUserAvatar = (user: ZoomUser) => {
    if (user.pic_url) {
      return <img src={user.pic_url} alt={user.display_name} className="w-8 h-8 rounded-full" />;
    } else {
      return <Users className="w-8 h-8 text-gray-500" />;
    }
  };

  const getRecordingIcon = (recording: ZoomRecording) => {
    if (recording.download_url) {
      return <Cloud className="h-6 w-6 text-blue-500" />;
    } else {
      return <FileText className="h-6 w-6 text-gray-500" />;
    }
  };

  const getWebinarIcon = (webinar: ZoomWebinar) => {
    if (webinar.settings.panelists_video) {
      return <Monitor className="h-6 w-6 text-purple-500" />;
    } else {
      return <Monitor className="h-6 w-6 text-gray-500" />;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center">
          <Video className="h-8 w-8 mr-3" />
          Zoom Integration
        </h1>
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
            Zoom integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-8">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="meetings" className="flex items-center">
            <Calendar className="h-4 w-4 mr-2" />
            Meetings
          </TabsTrigger>
          <TabsTrigger value="recordings" className="flex items-center">
            <Video className="h-4 w-4 mr-2" />
            Recordings
          </TabsTrigger>
          <TabsTrigger value="webinars" className="flex items-center">
            <Monitor className="h-4 w-4 mr-2" />
            Webinars
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="chats" className="flex items-center">
            <MessageSquare className="h-4 w-4 mr-2" />
            Chats
          </TabsTrigger>
          <TabsTrigger value="reports" className="flex items-center">
            <FileText className="h-4 w-4 mr-2" />
            Reports
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
                      {getUserAvatar(userInfo)}
                      <div>
                        <div className="font-medium">{userInfo.display_name}</div>
                        <div className="text-sm text-muted-foreground">{userInfo.email}</div>
                      </div>
                    </div>
                    <div>
                      <span className="font-medium">Type:</span> {userInfo.type === 1 ? 'Basic' : userInfo.type === 2 ? 'Licensed' : 'On-Prem'}
                    </div>
                    <div>
                      <span className="font-medium">Role:</span> {userInfo.role_name}
                    </div>
                    <div>
                      <span className="font-medium">Timezone:</span> {userInfo.timezone}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="meetings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calendar className="h-5 w-5 mr-2" />
                Zoom Meetings
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Meeting Creation */}
              <div className="space-y-2 mb-4 border rounded-lg p-3">
                <Label htmlFor="meetingTopic">Meeting Topic</Label>
                <Input
                  id="meetingTopic"
                  value={meetingTopic}
                  onChange={(e) => setMeetingTopic(e.target.value)}
                  placeholder="Enter meeting topic"
                  className="mb-2"
                />
                <Label htmlFor="meetingDescription">Description</Label>
                <Textarea
                  id="meetingDescription"
                  value={meetingDescription}
                  onChange={(e) => setMeetingDescription(e.target.value)}
                  placeholder="Enter meeting description"
                  className="mb-2"
                  rows={3}
                />
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <div>
                    <Label htmlFor="meetingDate">Date</Label>
                    <Input
                      id="meetingDate"
                      type="date"
                      value={meetingDate}
                      onChange={(e) => setMeetingDate(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="meetingTime">Time</Label>
                    <Input
                      id="meetingTime"
                      type="time"
                      value={meetingTime}
                      onChange={(e) => setMeetingTime(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="meetingDuration">Duration (min)</Label>
                    <Input
                      id="meetingDuration"
                      type="number"
                      value={meetingDuration}
                      onChange={(e) => setMeetingDuration(e.target.value)}
                      min="15"
                      max="480"
                    />
                  </div>
                </div>
                <Button 
                  onClick={createMeeting} 
                  disabled={loading || !meetingTopic.trim() || !meetingDate || !meetingTime}
                  className="w-full"
                >
                  {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                  Schedule Meeting
                </Button>
              </div>

              {/* Meetings List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {meetings.length > 0 ? (
                  meetings.map((meeting) => (
                    <div key={meeting.id} className="mb-3">
                      <div className="flex items-start space-x-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-gray-200">
                          {meeting.topic ? meeting.topic[0].toUpperCase() : '?'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium">{meeting.topic}</span>
                            <Badge variant="outline" className={`${getMeetingStatusColor(meeting.status)} text-white text-xs`}>
                              {meeting.status}
                            </Badge>
                          </div>
                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span>Start: {formatDateTime(meeting.start_time)}</span>
                            <span>Duration: {meeting.duration} min</span>
                            <div className="flex items-center space-x-1">
                              {meeting.settings.host_video && <Video className="h-3 w-3" />}
                              {meeting.settings.auto_recording && <Cloud className="h-3 w-3" />}
                            </div>
                          </div>
                        </div>
                      </div>
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

        <TabsContent value="recordings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Video className="h-5 w-5 mr-2" />
                Zoom Recordings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {recordings.length > 0 ? (
                  recordings.map((recording) => (
                    <div key={recording.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getRecordingIcon(recording)}
                          <h4 className="font-medium">{recording.topic}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge variant="outline" className="text-xs">
                            {recording.recording_count} files
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {Math.round(recording.total_size / 1024 / 1024)} MB
                          </Badge>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Recorded:</strong> {formatDateTime(recording.start_time)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Duration:</strong> {recording.duration} minutes
                      </div>
                      {recording.share_url && (
                        <Button variant="outline" size="sm" asChild>
                          <a href={recording.share_url} target="_blank" rel="noopener noreferrer">
                            View Recording
                          </a>
                        </Button>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No recordings found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadRecordings} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Recordings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="webinars" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Monitor className="h-5 w-5 mr-2" />
                Zoom Webinars
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {webinars.length > 0 ? (
                  webinars.map((webinar) => (
                    <div key={webinar.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getWebinarIcon(webinar)}
                          <h4 className="font-medium">{webinar.topic}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge variant="outline" className={`${getMeetingStatusColor(webinar.status)} text-white text-xs`}>
                            {webinar.status}
                          </Badge>
                          {webinar.settings.hd_video && (
                            <Badge variant="outline" className="text-xs">HD</Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Start:</strong> {formatDateTime(webinar.start_time)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Duration:</strong> {webinar.duration} minutes
                      </div>
                      {webinar.agenda && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Agenda:</strong> {webinar.agenda}
                        </div>
                      )}
                      {webinar.join_url && (
                        <Button variant="outline" size="sm" asChild>
                          <a href={webinar.join_url} target="_blank" rel="noopener noreferrer">
                            Join Webinar
                          </a>
                        </Button>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No webinars found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadWebinars} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Webinars
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Zoom Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <Users className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Users Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  Zoom user management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• User listing and profiles</li>
                  <li>• User role and permission management</li>
                  <li>• User activity tracking</li>
                  <li>• Bulk user operations</li>
                  <li>• User report generation</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="chats" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <MessageSquare className="h-5 w-5 mr-2" />
                Zoom Chats
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Chats Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  Zoom chat management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Chat message history</li>
                  <li>• Channel management</li>
                  <li>• File sharing in chats</li>
                  <li>• Chat analytics</li>
                  <li>• Message search and filtering</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reports" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <FileText className="h-5 w-5 mr-2" />
                Zoom Reports
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Reports Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  Zoom report generation is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Meeting usage reports</li>
                  <li>• Participant reports</li>
                  <li>• Recording reports</li>
                  <li>• Quality reports</li>
                  <li>• Custom report generation</li>
                </ul>
              </div>
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
                  Connect to Zoom
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Zoom OAuth to authorize ATOM access to your meetings and recordings.
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