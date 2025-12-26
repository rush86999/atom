/**
 * WhatsApp Business Integration Component
 * Simplified version using Shadcn UI components
 */

import React, { useState, useEffect } from 'react';
import {
  MessageCircle,
  Phone,
  Clock,
  CheckCircle,
  AlertTriangle,
  Settings,
  PlusSquare,
  RefreshCw,
  Send,
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface WhatsAppConversation {
  id: string;
  conversation_id: string;
  whatsapp_id: string;
  status: string;
  last_message_at: string;
  metadata?: any;
  name?: string;
  phone_number?: string;
  message_count?: number;
}

interface WhatsAppMessage {
  id: string;
  message_id: string;
  whatsapp_id: string;
  message_type: string;
  content: any;
  direction: 'inbound' | 'outbound';
  status: string;
  timestamp: string;
}

interface WhatsAppAnalytics {
  message_statistics: Array<{
    direction: string;
    message_type: string;
    status: string;
    count: number;
  }>;
  conversation_statistics: {
    total_conversations: number;
    active_conversations: number;
  };
  contact_growth: Array<{
    date: string;
    new_contacts: number;
  }>;
}

const WhatsAppBusinessIntegration: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [conversations, setConversations] = useState<WhatsAppConversation[]>([]);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [analytics, setAnalytics] = useState<WhatsAppAnalytics | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<WhatsAppConversation | null>(null);
  const [newMessage, setNewMessage] = useState('');
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    fetchWhatsAppData();
    const interval = setInterval(fetchConversations, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchWhatsAppData = async () => {
    try {
      setIsLoading(true);
      const healthResponse = await fetch('/api/whatsapp/health');
      const healthData = await healthResponse.json();
      const isHealthy = healthData.status === 'healthy';
      setIsConnected(isHealthy);

      if (isHealthy) {
        await Promise.all([
          fetchConversations(),
          fetchAnalytics(),
        ]);
      }
    } catch (error) {
      console.error('Error fetching WhatsApp data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load WhatsApp integration data',
        variant: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await fetch('/api/whatsapp/conversations');
      const data = await response.json();
      if (data.success) {
        setConversations(data.conversations);
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
    }
  };

  const fetchMessages = async (whatsappId: string) => {
    try {
      const response = await fetch(`/api/whatsapp/messages/${whatsappId}`);
      const data = await response.json();
      if (data.success) {
        setMessages(data.messages);
      }
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await fetch('/api/whatsapp/analytics');
      const data = await response.json();
      if (data.success) {
        setAnalytics(data.analytics);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedConversation) return;

    try {
      const response = await fetch('/api/whatsapp/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: selectedConversation.whatsapp_id,
          type: 'text',
          content: { body: newMessage },
        }),
      });

      const result = await response.json();
      if (result.success) {
        toast({
          title: 'Message Sent',
          description: 'Your WhatsApp message has been sent successfully',
        });
        setNewMessage('');
        fetchMessages(selectedConversation.whatsapp_id);
      }
    } catch (error) {
      toast({
        title: 'Send Failed',
        description: 'An error occurred while sending the message',
        variant: 'error',
      });
    }
  };

  const handleConversationSelect = (conversation: WhatsAppConversation) => {
    setSelectedConversation(conversation);
    fetchMessages(conversation.whatsapp_id);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <RefreshCw className="h-12 w-12 animate-spin text-blue-500" />
        <p className="mt-4 text-muted-foreground">Loading WhatsApp Business integration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">WhatsApp Business Integration</h1>
          <p className="text-muted-foreground mt-1">
            Manage customer communications through WhatsApp Business API
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Badge
            variant={isConnected ? "default" : "destructive"}
            className={isConnected ? "bg-green-500 hover:bg-green-600" : ""}
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" />
            Configure
          </Button>
          <Button
            disabled={!isConnected}
            onClick={() => setIsComposeOpen(true)}
          >
            <PlusSquare className="mr-2 h-4 w-4" />
            New Message
          </Button>
        </div>
      </div>

      {/* Analytics Overview */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Total Conversations</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {analytics.conversation_statistics.total_conversations}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Active Conversations</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-green-600">
                {analytics.conversation_statistics.active_conversations}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Messages Sent Today</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {analytics.message_statistics
                  .filter(m => m.direction === 'outbound')
                  .reduce((sum, m) => sum + m.count, 0)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Messages Received Today</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {analytics.message_statistics
                  .filter(m => m.direction === 'inbound')
                  .reduce((sum, m) => sum + m.count, 0)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content */}
      <Tabs defaultValue="conversations">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="conversations">Conversations</TabsTrigger>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="conversations" className="space-y-4">
          {!isConnected ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>WhatsApp Not Connected</AlertTitle>
              <AlertDescription>
                Please configure your WhatsApp Business API settings to start managing conversations.
              </AlertDescription>
            </Alert>
          ) : (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">Recent Conversations</h2>
                <Button variant="outline" size="sm" onClick={fetchConversations}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {conversations.map((conversation) => (
                  <Card
                    key={conversation.id}
                    className={`cursor-pointer transition-shadow hover:shadow-lg ${selectedConversation?.id === conversation.id
                        ? 'border-2 border-blue-500'
                        : ''
                      }`}
                    onClick={() => handleConversationSelect(conversation)}
                  >
                    <CardContent className="pt-6">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <p className="font-medium">
                            {conversation.name || conversation.phone_number}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {conversation.phone_number}
                          </p>
                        </div>
                        <Badge
                          variant={conversation.status === 'active' ? 'default' : 'secondary'}
                          className={conversation.status === 'active' ? 'bg-green-500' : ''}
                        >
                          {conversation.status}
                        </Badge>
                      </div>
                      <div className="flex justify-between mt-3 text-sm text-muted-foreground">
                        <span>{conversation.message_count || 0} messages</span>
                        <span>{new Date(conversation.last_message_at).toLocaleDateString()}</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="messages" className="space-y-4">
          {selectedConversation ? (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle>
                    Messages with {selectedConversation.name || selectedConversation.phone_number}
                  </CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchMessages(selectedConversation.whatsapp_id)}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.direction === 'outbound' ? 'justify-end' : 'justify-start'
                        }`}
                    >
                      <div
                        className={`max-w-xs md:max-w-md p-3 rounded-lg ${message.direction === 'outbound'
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-black'
                          }`}
                      >
                        <p className="text-sm font-medium mb-1">
                          {message.direction === 'outbound' ? 'You' : 'Customer'}
                        </p>
                        <p>
                          {message.message_type === 'text'
                            ? message.content?.body
                            : `[${message.message_type.toUpperCase()}]`}
                        </p>
                        <p className="text-xs mt-2 opacity-70">
                          {new Date(message.timestamp).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
              <CardFooter>
                <div className="flex w-full gap-2">
                  <Input
                    placeholder="Type a message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                  />
                  <Button onClick={handleSendMessage} disabled={!newMessage.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </CardFooter>
            </Card>
          ) : (
            <Alert>
              <AlertDescription>
                Select a conversation from the Conversations tab to view and send messages.
              </AlertDescription>
            </Alert>
          )}
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          {analytics ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Message Statistics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {analytics.message_statistics.map((stat, index) => (
                      <div key={index} className="flex justify-between">
                        <span className="text-sm">
                          {stat.direction} {stat.message_type} ({stat.status})
                        </span>
                        <span className="font-bold">{stat.count}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Contact Growth</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {analytics.contact_growth.map((growth, index) => (
                      <div key={index} className="flex justify-between">
                        <span className="text-sm">{growth.date}</span>
                        <span className="font-bold">+{growth.new_contacts}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Alert>
              <AlertDescription>No analytics data available</AlertDescription>
            </Alert>
          )}
        </TabsContent>
      </Tabs>

      {/* Compose Dialog */}
      <Dialog open={isComposeOpen} onOpenChange={setIsComposeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Compose New Message</DialogTitle>
            <DialogDescription>
              Send a WhatsApp message to a contact
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">Recipient Phone Number</label>
              <Input placeholder="+1234567890" />
            </div>
            <div>
              <label className="text-sm font-medium">Message Type</label>
              <Select defaultValue="text">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Text Message</SelectItem>
                  <SelectItem value="template">Template Message</SelectItem>
                  <SelectItem value="media">Media Message</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">Message Content</label>
              <Textarea
                placeholder="Type your message here..."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsComposeOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSendMessage}>Send Message</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WhatsAppBusinessIntegration;