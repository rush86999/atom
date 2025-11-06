/**
 * 🔄 Zoom Real-Time Integration Demo
 * Real-time WebSocket integration demo for Zoom
 */

"use client"

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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Switch } from '@/components/ui/switch';
import { 
  Activity, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  Settings, 
  Play, 
  Pause, 
  Square, 
  Circle, 
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
  Eye,
  EyeOff,
  Bell,
  BellOff,
  Volume2,
  VolumeX,
  Globe,
  Lock,
  Unlock,
  Key,
  Zap,
  Radio,
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

// Import real-time components
import {
  useZoomWebSocket,
  ZoomMeetingStatus,
  ZoomRealTimeEventLog,
  ZoomRealTimeAnalytics
} from '@/components/ui/zoom-realtime-components';

const ZoomRealTimeDemo = () => {
  const { toast } = useToast();
  
  // Demo configuration
  const [config, setConfig] = useState({
    userId: 'demo_user_123',
    accountId: 'demo_account_456',
    meetingId: 'demo_meeting_789',
    autoConnect: true,
    debugMode: true
  });
  
  // Connection management
  const {
    socket,
    connectionStatus,
    lastMessage,
    messages,
    error,
    reconnectAttempts,
    connect,
    disconnect,
    sendMessage
  } = useZoomWebSocket({
    userId: config.userId,
    accountId: config.accountId,
    meetingId: config.meetingId
  });
  
  // State management
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [demoEvents, setDemoEvents] = useState([]);
  const [connectedUsers, setConnectedUsers] = useState(0);
  const [totalEvents, setTotalEvents] = useState(0);
  const [latency, setLatency] = useState(0);
  const [selectedEventType, setSelectedEventType] = useState('participant_joined');
  
  // Demo data
  const demoParticipants = [
    { id: 'user_1', name: 'Alice Johnson', email: 'alice@example.com', avatar: '/avatars/alice.jpg' },
    { id: 'user_2', name: 'Bob Smith', email: 'bob@example.com', avatar: '/avatars/bob.jpg' },
    { id: 'user_3', name: 'Carol White', email: 'carol@example.com', avatar: '/avatars/carol.jpg' },
    { id: 'user_4', name: 'David Brown', email: 'david@example.com', avatar: '/avatars/david.jpg' },
    { id: 'user_5', name: 'Eve Davis', email: 'eve@example.com', avatar: '/avatars/eve.jpg' }
  ];
  
  const demoEventsList = [
    { value: 'meeting_started', label: 'Meeting Started', icon: Play },
    { value: 'participant_joined', label: 'Participant Joined', icon: Users },
    { value: 'participant_left', label: 'Participant Left', icon: XCircle },
    { value: 'recording_started', label: 'Recording Started', icon: Circle },
    { value: 'recording_stopped', label: 'Recording Stopped', icon: Square },
    { value: 'chat_message', label: 'Chat Message', icon: MessageSquare },
    { value: 'reaction_added', label: 'Reaction Added', icon: ThumbsUp },
    { value: 'screen_share_started', label: 'Screen Share Started', icon: ScreenShare },
    { value: 'screen_share_stopped', label: 'Screen Share Stopped', icon: ScreenShareOff },
    { value: 'poll_started', label: 'Poll Started', icon: BarChart3 }
  ];
  
  // Auto-connect on mount
  useEffect(() => {
    if (config.autoConnect && connectionStatus === 'disconnected') {
      connect();
    }
  }, [config.autoConnect, connect]);
  
  // Update stats
  useEffect(() => {
    setTotalEvents(messages.length);
    setConnectedUsers(messages.filter(m => m.event_type === 'participant_joined').length);
    
    // Update latency from last message
    if (lastMessage && lastMessage.data && lastMessage.data.latency) {
      setLatency(Math.round(lastMessage.data.latency * 1000)); // Convert to ms
    }
  }, [messages, lastMessage]);
  
  // Send demo event
  const sendDemoEvent = useCallback(() => {
    const event = demoEventsList.find(e => e.value === selectedEventType);
    if (!event) return;
    
    let demoData = {};
    
    switch (selectedEventType) {
      case 'meeting_started':
        demoData = {
          meeting_id: config.meetingId,
          topic: 'Demo Meeting - Real-Time Features',
          host_id: config.userId,
          host_name: 'Demo User',
          start_time: new Date().toISOString()
        };
        break;
        
      case 'participant_joined':
      case 'participant_left':
        const participant = demoParticipants[Math.floor(Math.random() * demoParticipants.length)];
        demoData = {
          participant: {
            id: participant.id,
            name: participant.name,
            email: participant.email,
            audio_on: Math.random() > 0.3,
            video_on: Math.random() > 0.5,
            screen_share_on: Math.random() > 0.8
          }
        };
        break;
        
      case 'chat_message':
        const sender = demoParticipants[Math.floor(Math.random() * demoParticipants.length)];
        demoData = {
          sender_id: sender.id,
          sender_name: sender.name,
          message: 'This is a demo chat message!',
          timestamp: new Date().toISOString()
        };
        break;
        
      case 'reaction_added':
        const reactor = demoParticipants[Math.floor(Math.random() * demoParticipants.length)];
        demoData = {
          user_id: reactor.id,
          user_name: reactor.name,
          emoji: ['👍', '❤️', '😂', '😮', '😢'][Math.floor(Math.random() * 5)]
        };
        break;
        
      case 'recording_started':
      case 'recording_stopped':
        demoData = {
          meeting_id: config.meetingId,
          recording_id: `recording_${Date.now()}`,
          recording_type: 'shared_screen_with_speaker_view'
        };
        break;
        
      case 'screen_share_started':
      case 'screen_share_stopped':
        const sharer = demoParticipants[Math.floor(Math.random() * demoParticipants.length)];
        demoData = {
          user_id: sharer.id,
          user_name: sharer.name,
          screen_share_on: selectedEventType === 'screen_share_started'
        };
        break;
        
      case 'poll_started':
        demoData = {
          poll_id: `poll_${Date.now()}`,
          poll_title: 'Demo Poll: How is the meeting going?',
          poll_options: ['Great!', 'Good', 'Okay', 'Not so good']
        };
        break;
        
      default:
        demoData = {
          custom_data: 'Demo event data'
        };
    }
    
    // Send message
    const message = {
      type: 'demo_event',
      event_type: selectedEventType,
      data: demoData,
      timestamp: new Date().toISOString()
    };
    
    const success = sendMessage(message);
    
    if (success) {
      setDemoEvents(prev => [...prev, {
        id: Date.now(),
        type: selectedEventType,
        data: demoData,
        timestamp: new Date().toISOString(),
        sent: true
      }]);
      
      toast({
        title: "Demo Event Sent",
        description: `${event.label} event sent successfully`,
      });
    } else {
      toast({
        title: "Send Failed",
        description: "Failed to send demo event",
        variant: "destructive",
      });
    }
  }, [selectedEventType, config, sendMessage, toast]);
  
  // Get connection status icon and color
  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <Wifi className="h-5 w-5 text-green-600" />;
      case 'disconnected': return <WifiOff className="h-5 w-5 text-red-600" />;
      case 'reconnecting': return <RefreshCw className="h-5 w-5 text-yellow-600 animate-spin" />;
      case 'error': return <XCircle className="h-5 w-5 text-red-600" />;
      default: return <WifiOff className="h-5 w-5 text-gray-600" />;
    }
  };
  
  const getConnectionColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-100 text-green-600';
      case 'disconnected': return 'bg-red-100 text-red-600';
      case 'reconnecting': return 'bg-yellow-100 text-yellow-600';
      case 'error': return 'bg-red-100 text-red-600';
      default: return 'bg-gray-100 text-gray-600';
    }
  };
  
  const getLatencyColor = () => {
    if (latency < 50) return 'text-green-600';
    if (latency < 150) return 'text-yellow-600';
    return 'text-red-600';
  };
  
  const getSignalIcon = () => {
    if (latency < 50) return <SignalHigh className="h-4 w-4 text-green-600" />;
    if (latency < 150) return <Signal className="h-4 w-4 text-yellow-600" />;
    return <SignalLow className="h-4 w-4 text-red-600" />;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center">
            <Activity className="h-8 w-8 mr-3 text-blue-600" />
            Zoom Real-Time Integration Demo
          </h1>
          <p className="text-muted-foreground mt-2">
            Experience real-time WebSocket integration with live event streaming, 
            participant tracking, and instant notifications.
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className={getConnectionColor()}>
            {getConnectionIcon()}
            <span className="ml-2">{connectionStatus}</span>
          </Badge>
          
          <Switch
            id="demo-mode"
            checked={isDemoMode}
            onCheckedChange={setIsDemoMode}
          />
          <Label htmlFor="demo-mode" className="text-sm">
            Demo Mode
          </Label>
        </div>
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Settings className="h-5 w-5 mr-2" />
            Demo Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="user-id">User ID</Label>
              <Input
                id="user-id"
                value={config.userId}
                onChange={(e) => setConfig(prev => ({ ...prev, userId: e.target.value }))}
                placeholder="Enter user ID"
              />
            </div>
            
            <div>
              <Label htmlFor="account-id">Account ID</Label>
              <Input
                id="account-id"
                value={config.accountId}
                onChange={(e) => setConfig(prev => ({ ...prev, accountId: e.target.value }))}
                placeholder="Enter account ID"
              />
            </div>
            
            <div>
              <Label htmlFor="meeting-id">Meeting ID</Label>
              <Input
                id="meeting-id"
                value={config.meetingId}
                onChange={(e) => setConfig(prev => ({ ...prev, meetingId: e.target.value }))}
                placeholder="Enter meeting ID"
              />
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="auto-connect"
                  checked={config.autoConnect}
                  onCheckedChange={(checked) => setConfig(prev => ({ ...prev, autoConnect: checked }))}
                />
                <Label htmlFor="auto-connect" className="text-sm">Auto-connect</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="debug-mode"
                  checked={config.debugMode}
                  onCheckedChange={(checked) => setConfig(prev => ({ ...prev, debugMode: checked }))}
                />
                <Label htmlFor="debug-mode" className="text-sm">Debug Mode</Label>
              </div>
            </div>
            
            <div className="flex space-x-2">
              <Button
                variant="outline"
                onClick={connect}
                disabled={connectionStatus === 'connected'}
              >
                <Wifi className="h-4 w-4 mr-2" />
                Connect
              </Button>
              
              <Button
                variant="outline"
                onClick={disconnect}
                disabled={connectionStatus === 'disconnected'}
              >
                <WifiOff className="h-4 w-4 mr-2" />
                Disconnect
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Connection Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <Wifi className="h-8 w-8 mx-auto mb-2 text-blue-600" />
            <div className="text-2xl font-bold">{connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}</div>
            <div className="text-sm text-muted-foreground">Connection Status</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            {getSignalIcon()}
            <div className="text-2xl font-bold mt-2">{latency}ms</div>
            <div className="text-sm text-muted-foreground">Latency</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <MessageSquare className="h-8 w-8 mx-auto mb-2 text-green-600" />
            <div className="text-2xl font-bold">{totalEvents}</div>
            <div className="text-sm text-muted-foreground">Events Received</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6 text-center">
            <Users className="h-8 w-8 mx-auto mb-2 text-purple-600" />
            <div className="text-2xl font-bold">{connectedUsers}</div>
            <div className="text-sm text-muted-foreground">Connected Users</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="demo" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="demo">Demo Controls</TabsTrigger>
          <TabsTrigger value="meeting">Meeting Status</TabsTrigger>
          <TabsTrigger value="events">Event Log</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        {/* Demo Controls */}
        <TabsContent value="demo" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Zap className="h-5 w-5 mr-2" />
                Send Demo Events
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Simulate real-time Zoom events to test the WebSocket integration
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-4">
                <div className="flex-1">
                  <Label htmlFor="event-type">Event Type</Label>
                  <Select value={selectedEventType} onValueChange={setSelectedEventType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select event type" />
                    </SelectTrigger>
                    <SelectContent>
                      {demoEventsList.map((event) => (
                        <SelectItem key={event.value} value={event.value}>
                          <div className="flex items-center">
                            <event.icon className="h-4 w-4 mr-2" />
                            {event.label}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <Button
                  onClick={sendDemoEvent}
                  disabled={connectionStatus !== 'connected'}
                  className="mt-6"
                >
                  <Radio className="h-4 w-4 mr-2" />
                  Send Event
                </Button>
              </div>
              
              {isDemoMode && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Demo Mode is active. Events will be simulated automatically every 5 seconds.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Recent Demo Events */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center">
                  <Clock className="h-5 w-5 mr-2" />
                  Recent Demo Events
                </span>
                <Badge variant="outline">{demoEvents.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                <div className="space-y-2">
                  {demoEvents.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      <Radio className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>No demo events sent yet</p>
                      <p className="text-sm">Select an event type and click "Send Event" to get started</p>
                    </div>
                  ) : (
                    demoEvents.slice(-10).reverse().map((event) => {
                      const eventType = demoEventsList.find(e => e.value === event.type);
                      return (
                        <div key={event.id} className="flex items-center justify-between p-2 border rounded">
                          <div className="flex items-center space-x-3">
                            {eventType && <eventType.icon className="h-4 w-4" />}
                            <div>
                              <div className="font-medium">{eventType?.label || event.type}</div>
                              <div className="text-xs text-muted-foreground">
                                {new Date(event.timestamp).toLocaleTimeString()}
                              </div>
                            </div>
                          </div>
                          
                          <Badge variant={event.sent ? 'default' : 'secondary'}>
                            {event.sent ? 'Sent' : 'Failed'}
                          </Badge>
                        </div>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Meeting Status */}
        <TabsContent value="meeting">
          <ZoomMeetingStatus
            userId={config.userId}
            accountId={config.accountId}
            meetingId={config.meetingId}
          />
        </TabsContent>

        {/* Event Log */}
        <TabsContent value="events">
          <ZoomRealTimeEventLog
            userId={config.userId}
            accountId={config.accountId}
            meetingId={config.meetingId}
          />
        </TabsContent>

        {/* Analytics */}
        <TabsContent value="analytics">
          <ZoomRealTimeAnalytics
            userId={config.userId}
            accountId={config.accountId}
            meetingId={config.meetingId}
          />
        </TabsContent>
      </Tabs>

      {/* Debug Information */}
      {config.debugMode && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Info className="h-5 w-5 mr-2" />
              Debug Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Socket Status:</span>
                <div className="font-medium">{socket?.readyState} (OPEN=1)</div>
              </div>
              <div>
                <span className="text-muted-foreground">Reconnect Attempts:</span>
                <div className="font-medium">{reconnectAttempts}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Last Message:</span>
                <div className="font-medium">
                  {lastMessage ? new Date(lastMessage.timestamp).toLocaleTimeString() : 'Never'}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Total Messages:</span>
                <div className="font-medium">{messages.length}</div>
              </div>
            </div>
            
            {error && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <strong>Connection Error:</strong> {error}
                </AlertDescription>
              </Alert>
            )}
            
            {lastMessage && (
              <div>
                <Label className="text-sm font-medium">Last Message:</Label>
                <div className="mt-1 p-3 bg-gray-50 rounded text-xs">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(lastMessage, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ZoomRealTimeDemo;