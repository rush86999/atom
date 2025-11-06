/**
 * Trello Integration Page
 * Complete Trello integration with comprehensive project and task management features
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
  Trello, 
  Layout, 
  ClipboardList, 
  Users, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Star,
  Eye,
  Calendar,
  Clock,
  User,
  MessageSquare,
  Tag,
  ChevronRight,
  Filter
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface TrelloBoard {
  id: string;
  name: string;
  description: string;
  closed: boolean;
  url: string;
  shortUrl: string;
  shortLink: string;
  dateLastActivity: string;
  pinned: boolean;
  starred: boolean;
  subscribed: boolean;
  totalCards: number;
  totalLists: number;
  totalMembers: number;
  totalChecklists: number;
}

interface TrelloCard {
  id: string;
  idBoard: string;
  idList: string;
  name: string;
  description: string;
  closed: boolean;
  due?: string;
  dueComplete: boolean;
  start?: string;
  url: string;
  shortUrl: string;
  shortLink: string;
  subscribed: boolean;
  labels: Array<{ id: string; name: string; color: string }>;
  members: Array<{ id: string; username: string; fullName: string }>;
  checklists: Array<{ id: string; name: string; checkItems: Array<{ state: string; name: string }> }>;
  badges: {
    comments: number;
    attachments: number;
    checkItems: number;
    checkItemsChecked: number;
  };
  dateLastActivity: string;
}

interface TrelloList {
  id: string;
  name: string;
  closed: boolean;
  pos: number;
  subscribed: boolean;
  totalCards: number;
  cards?: TrelloCard[];
}

interface TrelloMember {
  id: string;
  username: string;
  fullName: string;
  email: string;
  avatarUrl: string;
  bio: string;
  status: string;
  memberType: string;
  confirmed: boolean;
  activityBlocked: boolean;
  loginAllowed: boolean;
}

interface TrelloStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'error' | 'unavailable';
  timestamp: string;
  components: {
    service?: { status: string; message: string };
    configuration?: { status: string; api_key_configured: boolean };
    database?: { status: string; message: string };
    api?: { status: string; rate_limit_remaining: number };
  };
}

export default function TrelloIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<TrelloStatus | null>(null);
  const [userInfo, setUserInfo] = useState<TrelloMember | null>(null);
  const [boards, setBoards] = useState<TrelloBoard[]>([]);
  const [cards, setCards] = useState<TrelloCard[]>([]);
  const [lists, setLists] = useState<TrelloList[]>([]);
  const [members, setMembers] = useState<TrelloMember[]>([]);
  const [selectedBoard, setSelectedBoard] = useState('');
  const [cardTitle, setCardTitle] = useState('');
  const [cardDescription, setCardDescription] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const TRELLO_ENHANCED_URL = `${API_BASE_URL}/api/integrations/trello`;
  const TRELLO_OAUTH_URL = `${API_BASE_URL}/api/auth/trello`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'boards') {
      loadBoards();
    } else if (activeTab === 'cards') {
      loadCards();
    } else if (activeTab === 'members') {
      loadMembers();
    } else if (activeTab === 'lists') {
      loadLists();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'trello_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/users/profile`, {
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
          description: `Successfully loaded profile for ${data.data.user.fullName}`,
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
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBoards = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/boards/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          include_closed: false,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setBoards(data.data.boards);
        toast({
          title: "Boards loaded",
          description: `Loaded ${data.data.boards.length} boards`,
        });
      } else {
        toast({
          title: "Failed to load boards",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load boards:', error);
      toast({
        title: "Error loading boards",
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadCards = async () => {
    if (!selectedBoard) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/cards/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          board_id: selectedBoard,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCards(data.data.cards);
        toast({
          title: "Cards loaded",
          description: `Loaded ${data.data.cards.length} cards from ${selectedBoard}`,
        });
      } else {
        toast({
          title: "Failed to load cards",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load cards:', error);
      toast({
        title: "Error loading cards",
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadLists = async () => {
    if (!selectedBoard) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/lists/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          board_id: selectedBoard,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setLists(data.data.lists);
        toast({
          title: "Lists loaded",
          description: `Loaded ${data.data.lists.length} lists from ${selectedBoard}`,
        });
      } else {
        toast({
          title: "Failed to load lists",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load lists:', error);
      toast({
        title: "Error loading lists",
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async () => {
    if (!selectedBoard) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/members/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          board_id: selectedBoard,
          limit: 200
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setMembers(data.data.members);
        toast({
          title: "Members loaded",
          description: `Loaded ${data.data.members.length} members from ${selectedBoard}`,
        });
      } else {
        toast({
          title: "Failed to load members",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load members:', error);
      toast({
        title: "Error loading members",
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createCard = async () => {
    if (!cardTitle.trim() || !selectedBoard) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${TRELLO_ENHANCED_URL}/cards/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          board_id: selectedBoard,
          name: cardTitle.trim(),
          description: cardDescription.trim(),
          list_id: lists.find(l => l.name === "To Do")?.id || lists[0]?.id
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCardTitle('');
        setCardDescription('');
        toast({
          title: "Card created",
          description: "Card created successfully",
        });
        // Reload cards
        setTimeout(() => loadCards(), 1000);
      } else {
        toast({
          title: "Failed to create card",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to create card:', error);
      toast({
        title: "Error creating card",
        description: "Could not connect to Trello service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${TRELLO_OAUTH_URL}/authorize`, {
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

  const getBoardIcon = (board: TrelloBoard) => {
    if (board.starred) {
      return <Star className="h-6 w-6 text-yellow-500" />;
    } else if (board.closed) {
      return <Layout className="h-6 w-6 text-gray-500" />;
    } else {
      return <Trello className="h-6 w-6 text-blue-500" />;
    }
  };

  const getCardPriorityColor = (card: TrelloCard) => {
    if (card.dueComplete) {
      return 'bg-green-500';
    } else if (card.due && new Date(card.due) < new Date()) {
      return 'bg-red-500';
    } else if (card.due) {
      return 'bg-yellow-500';
    } else {
      return 'bg-gray-500';
    }
  };

  const getMemberAvatar = (member: TrelloMember) => {
    if (member.avatarUrl) {
      return <img src={member.avatarUrl} alt={member.fullName} className="w-8 h-8 rounded-full" />;
    } else {
      return <User className="w-8 h-8 text-gray-500" />;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center">
          <Trello className="h-8 w-8 mr-3" />
          Trello Integration
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
            Trello integration is {status.status}. 
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
          <TabsTrigger value="boards" className="flex items-center">
            <Layout className="h-4 w-4 mr-2" />
            Boards
          </TabsTrigger>
          <TabsTrigger value="cards" className="flex items-center">
            <ClipboardList className="h-4 w-4 mr-2" />
            Cards
          </TabsTrigger>
          <TabsTrigger value="lists" className="flex items-center">
            <Layout className="h-4 w-4 mr-2" />
            Lists
          </TabsTrigger>
          <TabsTrigger value="members" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Members
          </TabsTrigger>
          <TabsTrigger value="workflows" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Workflows
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
                      {getMemberAvatar(userInfo)}
                      <div>
                        <div className="font-medium">{userInfo.fullName}</div>
                        <div className="text-sm text-muted-foreground">@{userInfo.username}</div>
                      </div>
                    </div>
                    {userInfo.email && (
                      <div>
                        <span className="font-medium">Email:</span> {userInfo.email}
                      </div>
                    )}
                    <div>
                      <span className="font-medium">Status:</span> {userInfo.status}
                    </div>
                    <div>
                      <span className="font-medium">Type:</span> {userInfo.memberType}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="boards" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Layout className="h-5 w-5 mr-2" />
                Trello Boards
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {boards.length > 0 ? (
                  boards.map((board) => (
                    <div key={board.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getBoardIcon(board)}
                          <h4 className="font-medium">{board.name}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          {board.starred && <Badge variant="outline" className="text-xs">Starred</Badge>}
                          {board.closed && <Badge variant="outline" className="text-xs">Closed</Badge>}
                          {board.pinned && <Badge variant="outline" className="text-xs">Pinned</Badge>}
                        </div>
                      </div>
                      {board.description && (
                        <div className="text-sm text-muted-foreground">
                          {board.description}
                        </div>
                      )}
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <div className="flex items-center space-x-1">
                          <ClipboardList className="h-3 w-3" />
                          <span>{board.totalCards}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Layout className="h-3 w-3" />
                          <span>{board.totalLists}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Users className="h-3 w-3" />
                          <span>{board.totalMembers}</span>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Last Activity:</strong> {formatDateTime(board.dateLastActivity)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No boards found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadBoards} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Boards
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cards" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <ClipboardList className="h-5 w-5 mr-2" />
                Trello Cards
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Board Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="boardSelect">Select Board</Label>
                <Select value={selectedBoard} onValueChange={setSelectedBoard}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a board" />
                  </SelectTrigger>
                  <SelectContent>
                    {boards.map((board) => (
                      <SelectItem key={board.id} value={board.id}>
                        <div className="flex items-center space-x-2">
                          {getBoardIcon(board)}
                          <span>{board.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Card Creation */}
              {selectedBoard && (
                <div className="space-y-2 mb-4 border rounded-lg p-3">
                  <Label htmlFor="cardTitle">Card Title</Label>
                  <Input
                    id="cardTitle"
                    value={cardTitle}
                    onChange={(e) => setCardTitle(e.target.value)}
                    placeholder="Enter card title"
                    className="mb-2"
                  />
                  <Label htmlFor="cardDescription">Description</Label>
                  <Textarea
                    id="cardDescription"
                    value={cardDescription}
                    onChange={(e) => setCardDescription(e.target.value)}
                    placeholder="Enter card description"
                    className="mb-2"
                    rows={3}
                  />
                  <div className="flex space-x-2">
                    <Button 
                      onClick={createCard} 
                      disabled={loading || !cardTitle.trim()}
                      className="flex-1"
                    >
                      {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                      Create Card
                    </Button>
                  </div>
                </div>
              )}

              {/* Cards List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {cards.length > 0 ? (
                  cards.map((card) => (
                    <div key={card.id} className="mb-3">
                      <div className="flex items-start space-x-2">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${getCardPriorityColor(card)} text-white`}>
                          {card.badges.checkItems > 0 ? `${card.badges.checkItemsChecked}/${card.badges.checkItems}` : ''}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium">{card.name}</span>
                            {card.due && (
                              <div className="flex items-center space-x-1">
                                <Calendar className="h-3 w-3" />
                                <span className="text-sm">{new Date(card.due).toLocaleDateString()}</span>
                              </div>
                            )}
                          </div>
                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span>Created on {card.idBoard}</span>
                            <div className="flex items-center space-x-1">
                              <MessageSquare className="h-3 w-3" />
                              <span>{card.badges.comments}</span>
                            </div>
                            {card.badges.attachments > 0 && (
                              <div className="flex items-center space-x-1">
                                <Star className="h-3 w-3" />
                                <span>{card.badges.attachments}</span>
                              </div>
                            )}
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
                      "No cards found. Select a board to view cards."
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lists" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Layout className="h-5 w-5 mr-2" />
                Trello Lists
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Board Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="listBoardSelect">Select Board</Label>
                <Select value={selectedBoard} onValueChange={setSelectedBoard}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a board" />
                  </SelectTrigger>
                  <SelectContent>
                    {boards.map((board) => (
                      <SelectItem key={board.id} value={board.id}>
                        <div className="flex items-center space-x-2">
                          {getBoardIcon(board)}
                          <span>{board.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Lists List */}
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {lists.length > 0 ? (
                  lists.map((list) => (
                    <div key={list.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{list.name}</h4>
                        <div className="flex items-center space-x-2">
                          {list.closed && <Badge variant="outline" className="text-xs">Closed</Badge>}
                          <Badge variant="outline" className="text-xs">{list.totalCards} cards</Badge>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Position:</strong> {list.pos}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No lists found. Select a board to view lists."
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadLists} 
                disabled={loading || !selectedBoard}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Lists
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="members" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Trello Members
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Board Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="memberBoardSelect">Select Board</Label>
                <Select value={selectedBoard} onValueChange={setSelectedBoard}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a board" />
                  </SelectTrigger>
                  <SelectContent>
                    {boards.map((board) => (
                      <SelectItem key={board.id} value={board.id}>
                        <div className="flex items-center space-x-2">
                          {getBoardIcon(board)}
                          <span>{board.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Members List */}
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {members.length > 0 ? (
                  members.map((member) => (
                    <div key={member.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
                          {getMemberAvatar(member)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium">{member.fullName}</h4>
                            <Badge variant="outline" className="text-xs">
                              @{member.username}
                            </Badge>
                          </div>
                          {member.email && (
                            <div className="text-sm text-muted-foreground">{member.email}</div>
                          )}
                          <div className="text-sm text-muted-foreground">
                            <strong>Status:</strong> {member.status}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            <strong>Type:</strong> {member.memberType}
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
                      "No members found. Select a board to view members."
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadMembers} 
                disabled={loading || !selectedBoard}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Members
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Settings className="h-5 w-5 mr-2" />
                Trello Workflows
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <Settings className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Workflows Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  Trello workflow management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Butler automation rules</li>
                  <li>• Custom workflow creation</li>
                  <li>• Power-Up integrations</li>
                  <li>• Template management</li>
                  <li>• Board automation</li>
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
                  Connect to Trello
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Trello OAuth to authorize ATOM access to your boards.
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