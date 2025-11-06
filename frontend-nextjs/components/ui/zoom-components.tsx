/**
 * Zoom Enhanced UI Components
 * Enterprise-grade React components for Zoom integration
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
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
  Filter,
  MoreVertical,
  Download,
  Play,
  Share2,
  Eye,
  EyeOff,
  Copy,
  ExternalLink
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Enhanced Zoom Components
export const ZoomHealthIndicator = ({ status, components, metrics }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'error': return 'bg-red-500';
      case 'unavailable': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="h-4 w-4" />;
      case 'degraded': return <AlertCircle className="h-4 w-4" />;
      case 'error': return <AlertCircle className="h-4 w-4" />;
      case 'unavailable': return <AlertCircle className="h-4 w-4" />;
      default: return <AlertCircle className="h-4 w-4" />;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center">
            <Video className="h-5 w-5 mr-2" />
            Zoom Integration Status
          </span>
          <div className="flex items-center space-x-2">
            <Badge className={`${getStatusColor(status)} text-white`}>
              {getStatusIcon(status)}
              <span className="ml-1">{status}</span>
            </Badge>
            {status === 'healthy' && (
              <Badge variant="outline" className="text-green-600">
                <Shield className="h-3 w-3 mr-1" />
                Enterprise Ready
              </Badge>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(components).map(([key, component]) => (
            <div key={key} className="text-center p-3 border rounded-lg">
              <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${getStatusColor(component.status)}`} />
              <div className="text-sm font-medium capitalize">{key}</div>
              <div className="text-xs text-muted-foreground">{component.status}</div>
            </div>
          ))}
        </div>
        
        {metrics && (
          <div className="pt-4 border-t">
            <div className="text-sm font-medium mb-2">Performance Metrics</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Response Time:</span>
                <span className="ml-1">{metrics.response_time_ms}ms</span>
              </div>
              <div>
                <span className="text-muted-foreground">Cache:</span>
                <span className="ml-1 capitalize">{metrics.cache_status}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Uptime:</span>
                <span className="ml-1">{metrics.uptime_percentage}%</span>
              </div>
              <div>
                <span className="text-muted-foreground">Last Check:</span>
                <span className="ml-1">{new Date(metrics.last_health_check).toLocaleTimeString()}</span>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export const ZoomMeetingCard = ({ meeting, onJoin, onEdit, onDelete, userRole }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [copiedJoinUrl, setCopiedJoinUrl] = useState(false);

  const handleCopyJoinUrl = async () => {
    try {
      await navigator.clipboard.writeText(meeting.join_url);
      setCopiedJoinUrl(true);
      setTimeout(() => setCopiedJoinUrl(false), 2000);
    } catch (err) {
      console.error('Failed to copy join URL:', err);
    }
  };

  const getMeetingTypeIcon = (type) => {
    switch (type) {
      case 1: return <Users className="h-4 w-4" />; // Instant
      case 2: return <Calendar className="h-4 w-4" />; // Scheduled
      case 3: return <Calendar className="h-4 w-4" />; // Recurring
      case 4: return <Calendar className="h-4 w-4" />; // Recurring fixed
      case 8: return <Cloud className="h-4 w-4" />; // PMI
      default: return <Video className="h-4 w-4" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'waiting': return 'bg-yellow-500';
      case 'started': return 'bg-green-500';
      case 'ended': return 'bg-gray-500';
      default: return 'bg-blue-500';
    }
  };

  const isMeetingLive = () => {
    const now = new Date();
    const meetingTime = new Date(meeting.start_time);
    const endTime = new Date(meetingTime.getTime() + meeting.duration * 60000);
    return meeting.status === 'started' || (now >= meetingTime && now <= endTime);
  };

  return (
    <Card className={`w-full ${isMeetingLive() ? 'border-green-500 bg-green-50' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getStatusColor(meeting.status)} text-white`}>
              {getMeetingTypeIcon(meeting.type)}
            </div>
            <div>
              <CardTitle className="text-lg">{meeting.topic}</CardTitle>
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <span>{meeting.duration} min</span>
                <span>•</span>
                <span>{meeting.timezone}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-1">
            {isMeetingLive() && (
              <Badge className="bg-green-500 text-white animate-pulse">
                <div className="w-2 h-2 rounded-full bg-white mr-1" />
                Live Now
              </Badge>
            )}
            <Button variant="ghost" size="sm">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Start Time:</span>
            <span className="ml-1">{new Date(meeting.start_time).toLocaleString()}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Host:</span>
            <span className="ml-1">{meeting.host_email}</span>
          </div>
        </div>

        {meeting.agenda && (
          <div>
            <span className="text-sm font-medium">Agenda:</span>
            <p className="text-sm text-muted-foreground mt-1">{meeting.agenda}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {meeting.settings.host_video && (
            <Badge variant="outline" className="text-xs">
              <Video className="h-3 w-3 mr-1" />
              Host Video
            </Badge>
          )}
          {meeting.settings.participant_video && (
            <Badge variant="outline" className="text-xs">
              <Users className="h-3 w-3 mr-1" />
              Participant Video
            </Badge>
          )}
          {meeting.settings.mute_upon_entry && (
            <Badge variant="outline" className="text-xs">
              <MicOff className="h-3 w-3 mr-1" />
              Mute on Entry
            </Badge>
          )}
          {meeting.settings.waiting_room && (
            <Badge variant="outline" className="text-xs">
              <Clock className="h-3 w-3 mr-1" />
              Waiting Room
            </Badge>
          )}
          {meeting.settings.auto_recording && (
            <Badge variant="outline" className="text-xs">
              <Cloud className="h-3 w-3 mr-1" />
              Auto Record
            </Badge>
          )}
        </div>

        {meeting.password && (
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">Password:</span>
            <Input
              type={showPassword ? "text" : "password"}
              value={meeting.password}
              readOnly
              className="w-24 h-8 text-xs"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </Button>
          </div>
        )}
      </CardContent>
      <CardFooter className="pt-3">
        <div className="flex w-full justify-between items-center">
          <div className="flex space-x-2">
            {isMeetingLive() && (
              <Button onClick={() => onJoin(meeting)} className="bg-green-600 hover:bg-green-700">
                <Video className="h-4 w-4 mr-1" />
                Join Now
              </Button>
            )}
            <Button variant="outline" onClick={handleCopyJoinUrl}>
              {copiedJoinUrl ? <CheckCircle className="h-4 w-4 mr-1" /> : <Copy className="h-4 w-4 mr-1" />}
              {copiedJoinUrl ? 'Copied!' : 'Copy Link'}
            </Button>
            <Button variant="outline" asChild>
              <a href={meeting.join_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 mr-1" />
                Open
              </a>
            </Button>
          </div>
          {(userRole === 'host' || userRole === 'admin') && (
            <div className="flex space-x-1">
              <Button variant="ghost" size="sm" onClick={() => onEdit(meeting)}>
                <Edit className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => onDelete(meeting)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </CardFooter>
    </Card>
  );
};

export const ZoomMeetingScheduler = ({ onCreate, isLoading }) => {
  const [formData, setFormData] = useState({
    topic: '',
    agenda: '',
    start_time: '',
    duration: '60',
    timezone: '',
    password: '',
    settings: {
      host_video: true,
      participant_video: true,
      join_before_host: false,
      mute_upon_entry: true,
      auto_recording: 'cloud',
      waiting_room: false,
      require_password: false
    }
  });

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSettingChange = (setting, value) => {
    setFormData(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        [setting]: value
      }
    }));
  };

  const generatePassword = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let password = '';
    for (let i = 0; i < 8; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    handleInputChange('password', password);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validation
    if (!formData.topic.trim()) {
      return;
    }
    
    if (!formData.start_time) {
      return;
    }
    
    const meetingData = {
      ...formData,
      duration: parseInt(formData.duration),
      start_time: new Date(formData.start_time).toISOString()
    };
    
    // Remove password if not required
    if (!formData.settings.require_password) {
      delete meetingData.password;
    }
    
    onCreate(meetingData);
  };

  const timezones = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Paris',
    'Asia/Tokyo',
    'Asia/Shanghai'
  ];

  const durations = [
    { label: '15 minutes', value: '15' },
    { label: '30 minutes', value: '30' },
    { label: '45 minutes', value: '45' },
    { label: '1 hour', value: '60' },
    { label: '1.5 hours', value: '90' },
    { label: '2 hours', value: '120' },
    { label: '3 hours', value: '180' },
    { label: '4 hours', value: '240' }
  ];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <Calendar className="h-5 w-5 mr-2" />
          Schedule Meeting
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="topic">Meeting Topic *</Label>
            <Input
              id="topic"
              placeholder="Enter meeting topic"
              value={formData.topic}
              onChange={(e) => handleInputChange('topic', e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="agenda">Agenda</Label>
            <Textarea
              id="agenda"
              placeholder="Enter meeting agenda (optional)"
              value={formData.agenda}
              onChange={(e) => handleInputChange('agenda', e.target.value)}
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start_time">Start Time *</Label>
              <Input
                id="start_time"
                type="datetime-local"
                value={formData.start_time}
                onChange={(e) => handleInputChange('start_time', e.target.value)}
                min={new Date().toISOString().slice(0, 16)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="duration">Duration</Label>
              <Select value={formData.duration} onValueChange={(value) => handleInputChange('duration', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select duration" />
                </SelectTrigger>
                <SelectContent>
                  {durations.map((duration) => (
                    <SelectItem key={duration.value} value={duration.value}>
                      {duration.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <Select value={formData.timezone} onValueChange={(value) => handleInputChange('timezone', value)}>
              <SelectTrigger>
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {timezones.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <div className="space-y-4">
            <Label>Meeting Settings</Label>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="host_video"
                  checked={formData.settings.host_video}
                  onCheckedChange={(checked) => handleSettingChange('host_video', checked)}
                />
                <Label htmlFor="host_video" className="text-sm">Host Video On</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="participant_video"
                  checked={formData.settings.participant_video}
                  onCheckedChange={(checked) => handleSettingChange('participant_video', checked)}
                />
                <Label htmlFor="participant_video" className="text-sm">Participant Video On</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="join_before_host"
                  checked={formData.settings.join_before_host}
                  onCheckedChange={(checked) => handleSettingChange('join_before_host', checked)}
                />
                <Label htmlFor="join_before_host" className="text-sm">Join Before Host</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="mute_upon_entry"
                  checked={formData.settings.mute_upon_entry}
                  onCheckedChange={(checked) => handleSettingChange('mute_upon_entry', checked)}
                />
                <Label htmlFor="mute_upon_entry" className="text-sm">Mute on Entry</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="waiting_room"
                  checked={formData.settings.waiting_room}
                  onCheckedChange={(checked) => handleSettingChange('waiting_room', checked)}
                />
                <Label htmlFor="waiting_room" className="text-sm">Waiting Room</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="auto_recording"
                  checked={formData.settings.auto_recording !== 'none'}
                  onCheckedChange={(checked) => handleSettingChange('auto_recording', checked ? 'cloud' : 'none')}
                />
                <Label htmlFor="auto_recording" className="text-sm">Auto Recording</Label>
              </div>
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Switch
                id="require_password"
                checked={formData.settings.require_password}
                onCheckedChange={(checked) => handleSettingChange('require_password', checked)}
              />
              <Label htmlFor="require_password">Require Meeting Password</Label>
            </div>
            
            {formData.settings.require_password && (
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input
                    id="password"
                    type="text"
                    placeholder="Enter meeting password"
                    value={formData.password}
                    onChange={(e) => handleInputChange('password', e.target.value)}
                    maxLength={10}
                  />
                </div>
                <Button type="button" variant="outline" onClick={generatePassword}>
                  Generate
                </Button>
              </div>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Scheduling...
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Schedule Meeting
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export const ZoomRecordingCard = ({ recording, onPlay, onDownload, onShare, onDelete }) => {
  const [showFullFiles, setShowFullFiles] = useState(false);
  
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
      return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
  };

  const getRecordingTypeIcon = (type) => {
    switch (type) {
      case 'shared_screen_with_speaker_view': return <Monitor className="h-4 w-4" />;
      case 'active_speaker': return <Users className="h-4 w-4" />;
      case 'gallery_view': return <Users className="h-4 w-4" />;
      case 'audio_only': return <FileText className="h-4 w-4" />;
      default: return <Video className="h-4 w-4" />;
    }
  };

  const recordingFiles = showFullFiles ? recording.recording_files : recording.recording_files.slice(0, 3);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{recording.topic}</CardTitle>
            <div className="flex items-center space-x-2 text-sm text-muted-foreground mt-1">
              <span>{formatDuration(recording.duration)}</span>
              <span>•</span>
              <span>{new Date(recording.start_time).toLocaleString()}</span>
              <span>•</span>
              <span>{formatFileSize(recording.total_size)}</span>
            </div>
          </div>
          <div className="flex items-center space-x-1">
            {recording.share_url && (
              <Button variant="outline" size="sm" onClick={() => onShare(recording)}>
                <Share2 className="h-4 w-4" />
              </Button>
            )}
            <Button variant="ghost" size="sm">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Recording Files ({recording.recording_count})</span>
            {recording.recording_count > 3 && (
              <Button variant="ghost" size="sm" onClick={() => setShowFullFiles(!showFullFiles)}>
                {showFullFiles ? 'Show Less' : `Show ${recording.recording_count - 3} More`}
              </Button>
            )}
          </div>
          
          <div className="space-y-2">
            {recordingFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className="flex items-center justify-center w-8 h-8 bg-blue-100 rounded">
                    {getRecordingTypeIcon(file.recording_type)}
                  </div>
                  <div>
                    <div className="text-sm font-medium">
                      {file.recording_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatFileSize(file.file_size)} • {new Date(file.recording_start).toLocaleString()}
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-1">
                  {file.play_url && (
                    <Button variant="outline" size="sm" onClick={() => onPlay(file)}>
                      <Play className="h-3 w-3" />
                    </Button>
                  )}
                  {file.download_url && (
                    <Button variant="outline" size="sm" onClick={() => onDownload(file)}>
                      <Download className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {recording.password && (
          <div className="flex items-center space-x-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
            <Shield className="h-4 w-4 text-yellow-600" />
            <span className="text-sm text-yellow-800">Password Protected</span>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex justify-between">
        <div className="flex space-x-2">
          {recording.share_url && (
            <Button variant="outline" asChild>
              <a href={recording.share_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 mr-1" />
                View Recording
              </a>
            </Button>
          )}
        </div>
        
        <Button variant="ghost" size="sm" onClick={() => onDelete(recording)}>
          <Trash2 className="h-4 w-4 mr-1" />
          Delete
        </Button>
      </CardFooter>
    </Card>
  );
};

export const ZoomOAuthFlow = ({ onOAuthStart, isLoading }) => {
  const { toast } = useToast();
  
  const handleOAuthClick = async () => {
    try {
      await onOAuthStart();
    } catch (error) {
      toast({
        title: "OAuth Failed",
        description: error.message || "Could not initiate OAuth flow",
        variant: "destructive",
      });
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <Shield className="h-5 w-5 mr-2" />
          Connect to Zoom
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
            <Video className="h-8 w-8 text-blue-600" />
          </div>
          
          <div>
            <h3 className="text-lg font-medium">Authorize Zoom Integration</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Connect your Zoom account to access meetings, recordings, and webinars
            </p>
          </div>

          <div className="text-left space-y-2">
            <div className="flex items-center space-x-2 text-sm">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>Secure OAuth 2.0 authentication</span>
            </div>
            <div className="flex items-center space-x-2 text-sm">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>Manage meetings and recordings</span>
            </div>
            <div className="flex items-center space-x-2 text-sm">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>Access webinars and reports</span>
            </div>
            <div className="flex items-center space-x-2 text-sm">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>Real-time synchronization</span>
            </div>
          </div>

          <Alert>
            <Shield className="h-4 w-4" />
            <AlertDescription>
              ATOM requests access to: read and manage meetings, access recordings, 
              manage webinars, and view reports. Your credentials are encrypted and stored securely.
            </AlertDescription>
          </Alert>

          <Button onClick={handleOAuthClick} className="w-full" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Shield className="h-4 w-4 mr-2" />
                Connect to Zoom
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export const ZoomSearchFilter = ({ onSearch, onFilter, searchQuery, filters }) => {
  const [localQuery, setLocalQuery] = useState(searchQuery || '');
  const [showFilters, setShowFilters] = useState(false);
  
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    onSearch(localQuery);
  };

  const handleFilterChange = (key, value) => {
    onFilter(key, value);
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Search & Filter</CardTitle>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="h-4 w-4 mr-1" />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSearchSubmit}>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              type="text"
              placeholder="Search meetings, recordings, webinars..."
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              className="pl-10"
            />
            <Button type="submit" className="absolute right-1 top-1/2 transform -translate-y-1/2">
              Search
            </Button>
          </div>
        </form>

        {showFilters && (
          <div className="space-y-4 pt-4 border-t">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>Date Range</Label>
                <Select value={filters.dateRange} onValueChange={(value) => handleFilterChange('dateRange', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">This Week</SelectItem>
                    <SelectItem value="month">This Month</SelectItem>
                    <SelectItem value="quarter">This Quarter</SelectItem>
                    <SelectItem value="year">This Year</SelectItem>
                    <SelectItem value="custom">Custom Range</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Meeting Type</Label>
                <Select value={filters.meetingType} onValueChange={(value) => handleFilterChange('meetingType', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="live">Live</SelectItem>
                    <SelectItem value="ended">Ended</SelectItem>
                    <SelectItem value="webinar">Webinar</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={filters.status} onValueChange={(value) => handleFilterChange('status', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="waiting">Waiting</SelectItem>
                    <SelectItem value="started">Started</SelectItem>
                    <SelectItem value="ended">Ended</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Sort By</Label>
                <Select value={filters.sortBy} onValueChange={(value) => handleFilterChange('sortBy', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="start_time_desc">Start Time (Newest)</SelectItem>
                    <SelectItem value="start_time_asc">Start Time (Oldest)</SelectItem>
                    <SelectItem value="topic_asc">Topic (A-Z)</SelectItem>
                    <SelectItem value="topic_desc">Topic (Z-A)</SelectItem>
                    <SelectItem value="duration_desc">Duration (Longest)</SelectItem>
                    <SelectItem value="duration_asc">Duration (Shortest)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex space-x-2">
              <Button variant="outline" onClick={() => {
                setLocalQuery('');
                handleFilterChange('dateRange', 'all');
                handleFilterChange('meetingType', 'all');
                handleFilterChange('status', 'all');
                handleFilterChange('sortBy', 'start_time_desc');
              }}>
                Clear Filters
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default {
  ZoomHealthIndicator,
  ZoomMeetingCard,
  ZoomMeetingScheduler,
  ZoomRecordingCard,
  ZoomOAuthFlow,
  ZoomSearchFilter
};