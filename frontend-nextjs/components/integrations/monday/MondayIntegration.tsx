import React, { useState, useEffect } from 'react';
import {
  PlusCircle,
  ArrowRight,
  RefreshCw,
  Search,
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useToast } from "@/components/ui/use-toast";

interface MondayBoard {
  id: string;
  name: string;
  description?: string;
  board_kind: string;
  updated_at: string;
  items_count: number;
  columns: Array<{
    id: string;
    title: string;
    type: string;
  }>;
}

interface MondayItem {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  state: string;
  column_values: Array<{
    id: string;
    text: string;
    value: string;
    type: string;
  }>;
}

interface MondayIntegrationProps {
  accessToken?: string;
  onConnect: () => void;
  onDisconnect: () => void;
}

const MondayIntegration: React.FC<MondayIntegrationProps> = ({
  accessToken,
  onConnect,
  onDisconnect
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [boards, setBoards] = useState<MondayBoard[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<MondayBoard | null>(null);
  const [boardItems, setBoardItems] = useState<MondayItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [analytics, setAnalytics] = useState<any>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (accessToken) {
      loadInitialData();
    }
  }, [accessToken]);

  const loadInitialData = async () => {
    if (!accessToken) return;

    setIsLoading(true);
    try {
      const [boardsRes, healthRes] = await Promise.all([
        fetch(`/api/integrations/monday/boards?access_token=${accessToken}`),
        fetch(`/api/integrations/monday/health?access_token=${accessToken}`)
      ]);

      if (boardsRes.ok) {
        const boardsData = await boardsRes.json();
        setBoards(boardsData.boards || []);
      }

      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealthStatus(healthData);
      }

      calculateAnalytics();

    } catch (error) {
      console.error('Failed to load Monday.com data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load Monday.com data',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const calculateAnalytics = () => {
    const totalItems = boards.reduce((sum, board) => sum + (board.items_count || 0), 0);
    const publicBoards = boards.filter(board => board.board_kind === 'public').length;

    setAnalytics({
      totalBoards: boards.length,
      totalItems,
      publicBoards,
    });
  };

  const loadBoardItems = async (boardId: string) => {
    if (!accessToken) return;

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/integrations/monday/boards/${boardId}/items?access_token=${accessToken}`
      );
      if (response.ok) {
        const data = await response.json();
        setBoardItems(data.items || []);
        setSelectedBoard(boards.find(board => board.id === boardId) || null);
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load board items',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    try {
      const response = await fetch('/api/integrations/monday/authorize');
      if (response.ok) {
        const data = await response.json();
        window.location.href = data.authorization_url;
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to connect to Monday.com',
        variant: 'destructive',
      });
    }
  };

  if (!accessToken) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center space-y-4 py-8">
            <h2 className="text-2xl font-bold">Connect Monday.com</h2>
            <p className="text-center text-muted-foreground">
              Connect your Monday.com account to manage boards, items, and workspaces directly from ATOM.
            </p>
            <Button onClick={handleConnect} size="lg">
              <ArrowRight className="mr-2 h-4 w-4" />
              Connect Monday.com
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold">Monday.com Integration</h1>
              <p className="text-muted-foreground">
                Manage your Monday.com boards, items, and workspaces
              </p>
            </div>
            <div className="flex gap-2 items-center">
              {healthStatus && (
                <Badge
                  variant={healthStatus.status === 'healthy' ? 'default' : 'destructive'}
                  className={healthStatus.status === 'healthy' ? 'bg-green-500' : ''}
                >
                  {healthStatus.status}
                </Badge>
              )}
              <Button variant="outline" size="sm" onClick={loadInitialData} disabled={isLoading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={onDisconnect}>
                Disconnect
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Analytics */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Total Boards</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{analytics.totalBoards}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {analytics.publicBoards} public
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Total Items</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{analytics.totalItems}</p>
              <p className="text-xs text-muted-foreground mt-1">Across all boards</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Active</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {boardItems.filter(i => i.state === 'active').length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">Active items</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content */}
      <Tabs defaultValue="boards">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="boards">Boards</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
        </TabsList>

        <TabsContent value="boards" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Your Boards</h2>
            <Button>
              <PlusCircle className="mr-2 h-4 w-4" />
              Create Board
            </Button>
          </div>

          {isLoading ? (
            <div className="flex flex-col items-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin" />
              <p className="mt-2 text-muted-foreground">Loading boards...</p>
            </div>
          ) : boards.length === 0 ? (
            <Alert>
              <AlertTitle>No boards found</AlertTitle>
              <AlertDescription>
                Create your first board to get started with Monday.com integration.
              </AlertDescription>
            </Alert>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {boards.map((board) => (
                <Card
                  key={board.id}
                  className="cursor-pointer transition-shadow hover:shadow-md"
                  onClick={() => loadBoardItems(board.id)}
                >
                  <CardContent className="pt-6">
                    <h3 className="font-semibold mb-2">{board.name}</h3>
                    {board.description && (
                      <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                        {board.description}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <Badge>{board.board_kind}</Badge>
                      <Badge variant="outline">{board.items_count} items</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-3">
                      Updated {new Date(board.updated_at).toLocaleDateString()}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {selectedBoard && (
            <Card className="mt-6">
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>{selectedBoard.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {boardItems.length} items • {selectedBoard.columns.length} columns
                    </p>
                  </div>
                  <Button>
                    <PlusCircle className="mr-2 h-4 w-4" />
                    Add Item
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {boardItems.length === 0 ? (
                  <Alert>
                    <AlertDescription>No items found in this board</AlertDescription>
                  </Alert>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Updated</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {boardItems.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="font-medium">{item.name}</TableCell>
                          <TableCell>
                            <Badge
                              variant={item.state === 'active' ? 'default' : 'secondary'}
                              className={item.state === 'active' ? 'bg-green-500' : ''}
                            >
                              {item.state}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {new Date(item.created_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell>
                            {new Date(item.updated_at).toLocaleDateString()}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="search" className="space-y-4">
          <h2 className="text-xl font-semibold">Search Items</h2>
          <div className="flex gap-2">
            <Input
              placeholder="Search across all boards..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <Button>
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MondayIntegration;
