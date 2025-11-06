/**
 * 🔄 Zoom Real-Time UI Components
 * Real-time WebSocket components for live Zoom integration
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Switch } from '@/components/ui/switch';
import { 
  Activity, 
  Users, 
  Video, 
  Mic, 
  MicOff, 
  VideoOff, 
  Monitor, 
  MonitorOff,
  ScreenShare,
  ScreenShareOff,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Clock,
  Wifi,
  WifiOff,
  Eye,
  EyeOff,
  Play,
  Pause,
  Square,
  Circle,
  RefreshCw,
  Settings,
  Bell,
  BellOff,
  Volume2,
  VolumeX,
  Globe,
  Lock,
  Unlock,
  Key,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Zap,
  Radio,
  RadioIcon,
  Signal,
  SignalHigh,
  SignalLow,
  SignalZero,
  Loader2,
  CheckCircle,
  AlertCircle,
  XCircle,
  Info,
  TrendingUp,
  TrendingDown,
  BarChart3,
  LineChart,
  PieChart,
  Calendar,
  User,
  Crown,
  Shield,
  Star,
  Heart,
  Download,
  Upload,
  Camera,
  CameraOff,
  Phone,
  PhoneOff,
  MessageCircle,
  HelpCircle,
  Coffee,
  Smile,
  Frown,
  Meh
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

// WebSocket Hook
export const useZoomWebSocket = ({ 
  userId, 
  accountId, 
  meetingId = null, 
  eventTypes = null 
}) => {
  const [socket, setSocket] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastMessage, setLastMessage] = useState(null);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const { toast } = useToast();
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
    };
  }, []);

  const connect = useCallback(() => {
    try {
      // Construct WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = process.env.NEXT_PUBLIC_WEBSOCKET_HOST || 'localhost';
      const port = process.env.NEXT_PUBLIC_WEBSOCKET_PORT || '8765';
      
      const wsUrl = `${protocol}//${host}:${port}/${userId}/${accountId}`;
      
      // Create WebSocket connection
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnectionStatus('connected');
        setReconnectAttempts(0);
        setError(null);
        
        // Send initial subscription message
        const subscriptionMessage = {
          type: 'subscribe',
          meetings: meetingId ? [meetingId] : [],
          events: eventTypes || [
            'meeting_started', 'meeting_ended', 'participant_joined', 
            'participant_left', 'participant_status_changed',
            'recording_started', 'recording_stopped', 'chat_message',
            'reaction_added', 'reaction_removed', 'screen_share_started',
            'screen_share_stopped', 'poll_started', 'poll_ended'
          ]
        };
        ws.send(JSON.stringify(subscriptionMessage));
        
        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000); // Ping every 30 seconds
        
        toast({
          title: "Connected to Zoom Real-Time",
          description: "You will now receive live updates.",
        });
      };
      
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        // Handle pong response
        if (message.type === 'pong') {
          return;
        }
        
        setLastMessage(message);
        setMessages(prev => [...prev.slice(-99), message]); // Keep last 100 messages
        
        // Handle special message types
        if (message.type === 'subscription_confirmed') {
          console.log('Subscription confirmed:', message.data);
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.message);
          setError(message.message);
        }
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event);
        setConnectionStatus('disconnected');
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Auto-reconnect if not intentionally closed
        if (event.code !== 1000 && reconnectAttempts < 5) {
          setConnectionStatus('reconnecting');
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts(prev => prev + 1);
            connect();
          }, Math.pow(2, reconnectAttempts) * 1000); // Exponential backoff
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error occurred');
        setConnectionStatus('error');
      };
      
      setSocket(ws);
      
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setError('Failed to establish connection');
      setConnectionStatus('error');
    }
  }, [userId, accountId, meetingId, eventTypes, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (socket) {
      socket.close(1000, 'User disconnected');
      setSocket(null);
      setConnectionStatus('disconnected');
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
  }, [socket]);

  const sendMessage = useCallback((message) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, [socket]);

  return {
    socket,
    connectionStatus,
    lastMessage,
    messages,
    error,
    reconnectAttempts,
    connect,
    disconnect,
    sendMessage
  };
};

// Real-Time Meeting Status Component
export const ZoomMeetingStatus = ({ 
  meetingId, 
  userId, 
  accountId, 
  onMeetingEvent 
}) => {
  const { socket, connectionStatus, messages } = useZoomWebSocket({ 
    userId, 
    accountId, 
    meetingId 
  });
  
  const [meetingState, setMeetingState] = useState({
    status: 'waiting',
    topic: '',
    host_id: '',
    start_time: null,
    participants: [],
    recording_status: 'none',
    settings: {}
  });
  
  const [participantStatus, setParticipantStatus] = useState({});
  const [connectionStats, setConnectionStats] = useState({
    latency: 0,
    messagesReceived: 0,
    lastMessageTime: null
  });

  useEffect(() => {
    // Process incoming messages
    messages.forEach(message => {
      if (message.meeting_id === meetingId) {
        handleRealTimeMessage(message);
      }
    });
  }, [messages, meetingId]);

  const handleRealTimeMessage = (message) => {
    const { event_type, data } = message;
    
    // Update meeting state
    if (['meeting_started', 'meeting_ended', 'meeting_settings_changed'].includes(event_type)) {
      setMeetingState(prev => ({
        ...prev,
        ...data,
        last_updated: new Date().toISOString()
      }));
    }
    
    // Update participant status
    if (['participant_joined', 'participant_left', 'participant_status_changed'].includes(event_type)) {
      setParticipantStatus(prev => {
        const participantId = data.participant?.id || data.user_id;
        return {
          ...prev,
          [participantId]: {
            ...prev[participantId],
            ...data.participant,
            status: event_type,
            last_updated: new Date().toISOString()
          }
        };
      });
    }
    
    // Update connection stats
    setConnectionStats(prev => ({
      ...prev,
      messagesReceived: prev.messagesReceived + 1,
      lastMessageTime: new Date().toISOString(),
      latency: data.latency || prev.latency
    }));
    
    // Call callback if provided
    if (onMeetingEvent) {
      onMeetingEvent(event_type, data, message);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'started': return 'bg-green-100 text-green-600';
      case 'ended': return 'bg-gray-100 text-gray-600';
      case 'waiting': return 'bg-yellow-100 text-yellow-600';
      case 'in_breakout_room': return 'bg-blue-100 text-blue-600';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'started': return <Play className="h-4 w-4" />;
      case 'ended': return <Square className="h-4 w-4" />;
      case 'waiting': return <Clock className="h-4 w-4" />;
      case 'in_breakout_room': return <Users className="h-4 w-4" />;
      default: return <Clock className="h-4 w-4" />;
    }
  };

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <Wifi className="h-4 w-4 text-green-600" />;
      case 'disconnected': return <WifiOff className="h-4 w-4 text-red-600" />;
      case 'reconnecting': return <RefreshCw className="h-4 w-4 text-yellow-600 animate-spin" />;
      case 'error': return <AlertCircle className="h-4 w-4 text-red-600" />;
      default: return <WifiOff className="h-4 w-4 text-gray-600" />;
    }
  };

  const getParticipantStatusIcon = (participant) => {
    if (participant.audio_status?.muted !== false) return <MicOff className="h-3 w-3" />;
    return <Mic className="h-3 w-3" />;
  };

  const getParticipantVideoIcon = (participant) => {
    if (participant.video_status?.video_on !== true) return <VideoOff className="h-3 w-3" />;
    return <Video className="h-3 w-3" />;
  };

  const getParticipantScreenIcon = (participant) => {
    if (participant.screen_share_status?.sharing !== true) return <MonitorOff className="h-3 w-3" />;
    return <Monitor className="h-3 w-3" />;
  };

  return (
    <div className="space-y-4">
      {/* Connection Status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center justify-between text-sm">
            <span className="flex items-center">
              {getConnectionIcon()}
              <span className="ml-2">Real-Time Connection</span>
            </span>
            <Badge variant={connectionStatus === 'connected' ? 'default' : 'secondary'}>
              {connectionStatus}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Latency:</span>
              <div className="font-medium">{connectionStats.latency}ms</div>
            </div>
            <div>
              <span className="text-muted-foreground">Messages:</span>
              <div className="font-medium">{connectionStats.messagesReceived}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Last Update:</span>
              <div className="font-medium text-xs">
                {connectionStats.lastMessageTime ? 
                  new Date(connectionStats.lastMessageTime).toLocaleTimeString() : 
                  'Never'
                }
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Meeting Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center">
              <Video className="h-5 w-5 mr-2" />
              Meeting Status
            </span>
            <Badge className={getStatusColor(meetingState.status)}>
              {getStatusIcon(meetingState.status)}
              <span className="ml-1 capitalize">{meetingState.status}</span>
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm font-medium">Topic</Label>
            <div className="mt-1">{meetingState.topic || 'Untitled Meeting'}</div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-sm font-medium">Host</Label>
              <div className="mt-1">{meetingState.host_id || 'Unknown'}</div>
            </div>
            <div>
              <Label className="text-sm font-medium">Recording</Label>
              <div className="mt-1 capitalize">{meetingState.recording_status}</div>
            </div>
          </div>
          
          {meetingState.start_time && (
            <div>
              <Label className="text-sm font-medium">Started At</Label>
              <div className="mt-1">
                {new Date(meetingState.start_time).toLocaleString()}
              </div>
            </div>
          )}
          
          <div>
            <Label className="text-sm font-medium">
              Participants ({Object.keys(participantStatus).length})
            </Label>
            <div className="mt-2 space-y-2">
              {Object.values(participantStatus).map((participant) => (
                <div key={participant.id || participant.user_id} className="flex items-center justify-between p-2 border rounded">
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={participant.avatar_url} />
                      <AvatarFallback>
                        {(participant.name || participant.display_name || 'U').charAt(0).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    
                    <div>
                      <div className="font-medium text-sm">
                        {participant.name || participant.display_name || 'Unknown User'}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {participant.email || participant.id || participant.user_id}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {getParticipantStatusIcon(participant)}
                    {getParticipantVideoIcon(participant)}
                    {getParticipantScreenIcon(participant)}
                    
                    {participant.is_host && (
                      <Badge variant="outline" className="text-xs">
                        <Crown className="h-3 w-3 mr-1" />
                        Host
                      </Badge>
                    )}
                    
                    {participant.is_co_host && (
                      <Badge variant="outline" className="text-xs">
                        <Shield className="h-3 w-3 mr-1" />
                        Co-Host
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Real-Time Event Log Component
export const ZoomRealTimeEventLog = ({ 
  userId, 
  accountId, 
  meetingId = null, 
  maxEvents = 50 
}) => {
  const { socket, connectionStatus, messages } = useZoomWebSocket({ 
    userId, 
    accountId, 
    meetingId,
    eventTypes: ['all']
  });
  
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef(null);

  useEffect(() => {
    // Process incoming messages
    const newEvents = messages
      .filter(message => !meetingId || message.meeting_id === meetingId)
      .map(message => ({
        id: message.timestamp + '_' + Math.random(),
        timestamp: message.timestamp,
        event_type: message.event_type,
        data: message.data,
        meeting_id: message.meeting_id,
        user_id: message.user_id
      }));
    
    setEvents(prev => [...newEvents, ...prev].slice(0, maxEvents));
  }, [messages, meetingId, maxEvents]);

  useEffect(() => {
    // Auto-scroll to bottom
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const getEventIcon = (eventType) => {
    switch (eventType) {
      case 'meeting_started': return <Play className="h-4 w-4 text-green-600" />;
      case 'meeting_ended': return <Square className="h-4 w-4 text-red-600" />;
      case 'participant_joined': return <User className="h-4 w-4 text-blue-600" />;
      case 'participant_left': return <XCircle className="h-4 w-4 text-gray-600" />;
      case 'recording_started': return <Circle className="h-4 w-4 text-red-600" />;
      case 'recording_stopped': return <Square className="h-4 w-4 text-red-600" />;
      case 'chat_message': return <MessageSquare className="h-4 w-4 text-purple-600" />;
      case 'reaction_added': return <ThumbsUp className="h-4 w-4 text-yellow-600" />;
      case 'reaction_removed': return <ThumbsDown className="h-4 w-4 text-gray-600" />;
      case 'screen_share_started': return <ScreenShare className="h-4 w-4 text-orange-600" />;
      case 'screen_share_stopped': return <ScreenShareOff className="h-4 w-4 text-gray-600" />;
      case 'poll_started': return <BarChart3 className="h-4 w-4 text-indigo-600" />;
      case 'poll_ended': return <BarChart3 className="h-4 w-4 text-gray-600" />;
      default: return <Info className="h-4 w-4 text-gray-600" />;
    }
  };

  const getEventColor = (eventType) => {
    switch (eventType) {
      case 'meeting_started': return 'text-green-600';
      case 'meeting_ended': return 'text-red-600';
      case 'participant_joined': return 'text-blue-600';
      case 'participant_left': return 'text-gray-600';
      case 'recording_started': return 'text-red-600';
      case 'recording_stopped': return 'text-red-600';
      case 'chat_message': return 'text-purple-600';
      case 'reaction_added': return 'text-yellow-600';
      case 'reaction_removed': return 'text-gray-600';
      case 'screen_share_started': return 'text-orange-600';
      case 'screen_share_stopped': return 'text-gray-600';
      case 'poll_started': return 'text-indigo-600';
      case 'poll_ended': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  const formatEventMessage = (event) => {
    const { event_type, data } = event;
    
    switch (event_type) {
      case 'meeting_started':
        return `Meeting "${data.topic}" started by ${data.host_name}`;
      case 'meeting_ended':
        return `Meeting "${data.topic}" ended`;
      case 'participant_joined':
        return `${data.participant?.name || data.user_id} joined the meeting`;
      case 'participant_left':
        return `${data.participant?.name || data.user_id} left the meeting`;
      case 'recording_started':
        return `Recording started`;
      case 'recording_stopped':
        return `Recording stopped`;
      case 'chat_message':
        return `${data.sender_name}: ${data.message}`;
      case 'reaction_added':
        return `${data.user_name} reacted with ${data.emoji}`;
      case 'reaction_removed':
        return `${data.user_name} removed reaction`;
      case 'screen_share_started':
        return `${data.user_name} started screen sharing`;
      case 'screen_share_stopped':
        return `${data.user_name} stopped screen sharing`;
      case 'poll_started':
        return `Poll "${data.poll_title}" started`;
      case 'poll_ended':
        return `Poll "${data.poll_title}" ended`;
      default:
        return `${event_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`;
    }
  };

  const filteredEvents = events.filter(event => {
    if (filter === 'all') return true;
    if (filter === 'meetings') return event.event_type.includes('meeting');
    if (filter === 'participants') return event.event_type.includes('participant');
    if (filter === 'recordings') return event.event_type.includes('recording');
    if (filter === 'chat') return event.event_type.includes('chat');
    if (filter === 'reactions') return event.event_type.includes('reaction');
    if (filter === 'screen_share') return event.event_type.includes('screen');
    if (filter === 'polls') return event.event_type.includes('poll');
    return false;
  });

  const clearEvents = () => {
    setEvents([]);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center">
            <Activity className="h-5 w-5 mr-2" />
            Real-Time Event Log
          </span>
          <div className="flex items-center space-x-2">
            <Badge variant={connectionStatus === 'connected' ? 'default' : 'secondary'}>
              {connectionStatus}
            </Badge>
            <Button variant="ghost" size="sm" onClick={clearEvents}>
              Clear
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex items-center justify-between">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter events" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Events</SelectItem>
              <SelectItem value="meetings">Meetings</SelectItem>
              <SelectItem value="participants">Participants</SelectItem>
              <SelectItem value="recordings">Recordings</SelectItem>
              <SelectItem value="chat">Chat</SelectItem>
              <SelectItem value="reactions">Reactions</SelectItem>
              <SelectItem value="screen_share">Screen Share</SelectItem>
              <SelectItem value="polls">Polls</SelectItem>
            </SelectContent>
          </Select>
          
          <div className="flex items-center space-x-2">
            <Switch
              id="auto-scroll"
              checked={autoScroll}
              onCheckedChange={setAutoScroll}
            />
            <Label htmlFor="auto-scroll" className="text-sm">
              Auto-scroll
            </Label>
          </div>
        </div>

        {/* Events */}
        <div className="relative">
          <ScrollArea className="h-96 border rounded" ref={scrollRef}>
            <div className="p-4 space-y-2">
              {filteredEvents.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No events yet</p>
                  <p className="text-sm">Events will appear here as they happen in real-time</p>
                </div>
              ) : (
                filteredEvents.map((event) => (
                  <div key={event.id} className="flex items-start space-x-3 p-2 border rounded hover:bg-gray-50">
                    <div className="flex-shrink-0 mt-1">
                      {getEventIcon(event.event_type)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium truncate">
                          {formatEventMessage(event)}
                        </p>
                        <span className="text-xs text-muted-foreground ml-2">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      
                      {event.meeting_id && (
                        <p className="text-xs text-muted-foreground">
                          Meeting: {event.meeting_id}
                        </p>
                      )}
                      
                      {event.user_id && (
                        <p className="text-xs text-muted-foreground">
                          User: {event.user_id}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Stats */}
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Showing {filteredEvents.length} of {events.length} events</span>
          <span>Connection: {connectionStatus}</span>
        </div>
      </CardContent>
    </Card>
  );
};

// Real-Time Analytics Component
export const ZoomRealTimeAnalytics = ({ 
  userId, 
  accountId, 
  meetingId = null 
}) => {
  const [analytics, setAnalytics] = useState({
    activeConnections: 0,
    totalMessages: 0,
    totalEvents: 0,
    averageLatency: 0,
    eventRate: 0,
    participantCount: 0,
    recordingDuration: 0
  });
  
  const [chartData, setChartData] = useState({
    eventsOverTime: [],
    latencyOverTime: [],
    participantCount: []
  });
  
  const [timeRange, setTimeRange] = useState('5m'); // 5m, 15m, 1h, 24h

  useEffect(() => {
    // Fetch real-time analytics
    const fetchAnalytics = async () => {
      try {
        const response = await fetch('/api/zoom/websocket/analytics/realtime', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            meeting_id: meetingId,
            time_window: parseInt(timeRange) // minutes
          })
        });
        
        const result = await response.json();
        
        if (result.ok) {
          setAnalytics(result.data.summary);
          setChartData(result.data.analytics);
        }
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      }
    };

    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, [meetingId, timeRange]);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  return (
    <div className="space-y-4">
      {/* Time Range Selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center">
              <BarChart3 className="h-5 w-5 mr-2" />
              Real-Time Analytics
            </span>
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5m">5 minutes</SelectItem>
                <SelectItem value="15m">15 minutes</SelectItem>
                <SelectItem value="1h">1 hour</SelectItem>
                <SelectItem value="24h">24 hours</SelectItem>
              </SelectContent>
            </Select>
          </CardTitle>
        </CardHeader>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <Users className="h-8 w-8 mx-auto mb-2 text-blue-600" />
            <div className="text-2xl font-bold">{analytics.activeConnections}</div>
            <div className="text-sm text-muted-foreground">Active Connections</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <MessageSquare className="h-8 w-8 mx-auto mb-2 text-green-600" />
            <div className="text-2xl font-bold">{analytics.totalMessages}</div>
            <div className="text-sm text-muted-foreground">Total Messages</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <Activity className="h-8 w-8 mx-auto mb-2 text-purple-600" />
            <div className="text-2xl font-bold">{analytics.totalEvents}</div>
            <div className="text-sm text-muted-foreground">Total Events</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <Signal className="h-8 w-8 mx-auto mb-2 text-orange-600" />
            <div className="text-2xl font-bold">{analytics.averageLatency}ms</div>
            <div className="text-sm text-muted-foreground">Avg Latency</div>
          </CardContent>
        </Card>
      </div>

      {/* Event Rate Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Event Rate Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 flex items-center justify-center border rounded bg-gray-50">
            <div className="text-center text-muted-foreground">
              <LineChart className="h-12 w-12 mx-auto mb-4" />
              <p>Event Rate Chart</p>
              <p className="text-sm">Chart visualization would be implemented here</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Participant Count Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Participant Count Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 flex items-center justify-center border rounded bg-gray-50">
            <div className="text-center text-muted-foreground">
              <TrendingUp className="h-12 w-12 mx-auto mb-4" />
              <p>Participant Count Chart</p>
              <p className="text-sm">Chart visualization would be implemented here</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Latency Distribution */}
      <Card>
        <CardHeader>
          <CardTitle>Latency Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 flex items-center justify-center border rounded bg-gray-50">
            <div className="text-center text-muted-foreground">
              <PieChart className="h-12 w-12 mx-auto mb-4" />
              <p>Latency Distribution Chart</p>
              <p className="text-sm">Chart visualization would be implemented here</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default {
  useZoomWebSocket,
  ZoomMeetingStatus,
  ZoomRealTimeEventLog,
  ZoomRealTimeAnalytics
};