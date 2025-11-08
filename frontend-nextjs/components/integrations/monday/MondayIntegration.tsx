import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  CardHeader,
  SimpleGrid,
  Badge,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Input,
  Select,
  FormControl,
  FormLabel,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Flex,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Progress,
  IconButton,
  Tooltip
} from '@chakra-ui/react';
import { AddIcon, ExternalLinkIcon, RepeatIcon, SearchIcon } from '@chakra-ui/icons';

interface MondayBoard {
  id: string;
  name: string;
  description?: string;
  board_kind: string;
  updated_at: string;
  workspace_id?: string;
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
  creator?: {
    id: string;
    name: string;
    email: string;
  };
}

interface MondayWorkspace {
  id: string;
  name: string;
  description?: string;
  kind: string;
  created_at: string;
}

interface MondayUser {
  id: string;
  name: string;
  email: string;
  title?: string;
  created_at: string;
  is_guest: boolean;
  is_pending: boolean;
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
  const [workspaces, setWorkspaces] = useState<MondayWorkspace[]>([]);
  const [users, setUsers] = useState<MondayUser[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MondayItem[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);

  const { isOpen: isConnectOpen, onOpen: onConnectOpen, onClose: onConnectClose } = useDisclosure();
  const { isOpen: isCreateItemOpen, onOpen: onCreateItemOpen, onClose: onCreateItemClose } = useDisclosure();
  const { isOpen: isCreateBoardOpen, onOpen: onCreateBoardOpen, onClose: onCreateBoardClose } = useDisclosure();

  const toast = useToast();

  // Load initial data when access token is available
  useEffect(() => {
    if (accessToken) {
      loadInitialData();
    }
  }, [accessToken]);

  const loadInitialData = async () => {
    if (!accessToken) return;

    setIsLoading(true);
    try {
      // Load boards, workspaces, and users in parallel
      const [boardsRes, workspacesRes, usersRes, healthRes] = await Promise.all([
        fetch(`/api/integrations/monday/boards?access_token=${accessToken}`),
        fetch(`/api/integrations/monday/workspaces?access_token=${accessToken}`),
        fetch(`/api/integrations/monday/users?access_token=${accessToken}`),
        fetch(`/api/integrations/monday/health?access_token=${accessToken}`)
      ]);

      if (boardsRes.ok) {
        const boardsData = await boardsRes.json();
        setBoards(boardsData.boards || []);
      }

      if (workspacesRes.ok) {
        const workspacesData = await workspacesRes.json();
        setWorkspaces(workspacesData.workspaces || []);
      }

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        setUsers(usersData.users || []);
      }

      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealthStatus(healthData);
      }

      // Calculate analytics
      calculateAnalytics();

    } catch (error) {
      console.error('Failed to load Monday.com data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load Monday.com data',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const calculateAnalytics = () => {
    const totalItems = boards.reduce((sum, board) => sum + (board.items_count || 0), 0);
    const publicBoards = boards.filter(board => board.board_kind === 'public').length;
    const privateBoards = boards.filter(board => board.board_kind === 'private').length;

    setAnalytics({
      totalBoards: boards.length,
      totalWorkspaces: workspaces.length,
      totalUsers: users.length,
      totalItems,
      publicBoards,
      privateBoards,
      shareableBoards: boards.length - publicBoards - privateBoards
    });
  };

  const loadBoardItems = async (boardId: string) => {
    if (!accessToken) return;

    setIsLoading(true);
    try {
      const response = await fetch(`/api/integrations/monday/boards/${boardId}/items?access_token=${accessToken}`);
      if (response.ok) {
        const data = await response.json();
        setBoardItems(data.items || []);
        setSelectedBoard(boards.find(board => board.id === boardId) || null);
      }
    } catch (error) {
      console.error('Failed to load board items:', error);
      toast({
        title: 'Error',
        description: 'Failed to load board items',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!accessToken || !searchQuery.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/integrations/monday/search?access_token=${accessToken}&query=${encodeURIComponent(searchQuery)}`
      );
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.items || []);
      }
    } catch (error) {
      console.error('Search failed:', error);
      toast({
        title: 'Error',
        description: 'Search failed',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateItem = async (itemData: { name: string; column_values?: any }) => {
    if (!accessToken || !selectedBoard) return;

    try {
      const response = await fetch(`/api/integrations/monday/boards/${selectedBoard.id}/items`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify(itemData)
      });

      if (response.ok) {
        toast({
          title: 'Success',
          description: 'Item created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        onCreateItemClose();
        loadBoardItems(selectedBoard.id);
      }
    } catch (error) {
      console.error('Failed to create item:', error);
      toast({
        title: 'Error',
        description: 'Failed to create item',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleCreateBoard = async (boardData: { name: string; board_kind: string; workspace_id?: string }) => {
    if (!accessToken) return;

    try {
      const response = await fetch('/api/integrations/monday/boards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify(boardData)
      });

      if (response.ok) {
        toast({
          title: 'Success',
          description: 'Board created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        onCreateBoardClose();
        loadInitialData();
      }
    } catch (error) {
      console.error('Failed to create board:', error);
      toast({
        title: 'Error',
        description: 'Failed to create board',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
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
      console.error('Failed to start OAuth flow:', error);
      toast({
        title: 'Error',
        description: 'Failed to connect to Monday.com',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Render connection state
  if (!accessToken) {
    return (
      <Card>
        <CardBody>
          <VStack spacing={4} align="center" py={8}>
            <Heading size="md">Connect Monday.com</Heading>
            <Text textAlign="center">
              Connect your Monday.com account to manage boards, items, and workspaces directly from ATOM.
            </Text>
            <Button
              colorScheme="blue"
              onClick={handleConnect}
              leftIcon={<ExternalLinkIcon />}
              size="lg"
            >
              Connect Monday.com
            </Button>
          </VStack>
        </CardBody>
      </Card>
    );
  }

  return (
    <Box>
      {/* Header with Health Status */}
      <Card mb={6}>
        <CardBody>
          <Flex justify="space-between" align="center">
            <VStack align="start" spacing={1}>
              <Heading size="md">Monday.com Integration</Heading>
              <Text color="gray.600">
                Manage your Monday.com boards, items, and workspaces
              </Text>
            </VStack>
            <HStack spacing={4}>
              {healthStatus && (
                <Badge
                  colorScheme={healthStatus.status === 'healthy' ? 'green' : 'red'}
                  fontSize="sm"
                >
                  {healthStatus.status}
                </Badge>
              )}
              <Tooltip label="Refresh Data">
                <IconButton
                  aria-label="Refresh data"
                  icon={<RepeatIcon />}
                  onClick={loadInitialData}
                  isLoading={isLoading}
                  variant="outline"
                />
              </Tooltip>
              <Button
                colorScheme="red"
                variant="outline"
                onClick={onDisconnect}
                size="sm"
              >
                Disconnect
              </Button>
            </HStack>
          </Flex>
        </CardBody>
      </Card>

      {/* Analytics Dashboard */}
      {analytics && (
        <Card mb={6}>
          <CardHeader>
            <Heading size="md">Analytics Overview</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
              <Stat>
                <StatLabel>Total Boards</StatLabel>
                <StatNumber>{analytics.totalBoards}</StatNumber>
                <StatHelpText>
                  <StatArrow type="increase" />
                  {analytics.publicBoards} public
                </StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Total Items</StatLabel>
                <StatNumber>{analytics.totalItems}</StatNumber>
                <StatHelpText>Across all boards</StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Workspaces</StatLabel>
                <StatNumber>{analytics.totalWorkspaces}</StatNumber>
                <StatHelpText>Active workspaces</StatHelpText>
              </Stat>
              <Stat>
                <StatLabel>Team Members</StatLabel>
                <StatNumber>{analytics.totalUsers}</StatNumber>
                <StatHelpText>Active users</StatHelpText>
              </Stat>
            </SimpleGrid>
          </CardBody>
        </Card>
      )}

      {/* Main Content Tabs */}
      <Tabs colorScheme="blue">
        <TabList>
          <Tab>Boards</Tab>
          <Tab>Search</Tab>
          <Tab>Workspaces</Tab>
          <Tab>Team</Tab>
        </TabList>

        <TabPanels>
          {/* Boards Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Your Boards</Heading>
                <Button
                  leftIcon={<AddIcon />}
                  colorScheme="blue"
                  onClick={onCreateBoardOpen}
                >
                  Create Board
                </Button>
              </HStack>

              {isLoading ? (
                <Box textAlign="center" py={8}>
                  <Spinner size="xl" />
                  <Text mt={4}>Loading boards...</Text>
                </Box>
              ) : boards.length === 0 ? (
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>No boards found</AlertTitle>
                    <AlertDescription>
                      Create your first board to get started with Monday.com integration.
                    </AlertDescription>
                  </Box>
                </Alert>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                  {boards.map((board) => (
                    <Card
                      key={board.id}
                      cursor="pointer"
                      _hover={{ shadow: 'md' }}
                      onClick={() => loadBoardItems(board.id)}
                    >
                      <CardBody>
                        <VStack align="start" spacing={3}>
                          <Heading size="sm">{board.name}</Heading>
                          {board.description && (
                            <Text fontSize="sm" color="gray.600" noOfLines={2}>
                              {board.description}
                            </Text>
                          )}
                          <HStack spacing={2}>
                            <Badge colorScheme="blue">{board.board_kind}</Badge>
                            <Badge variant="outline">
                              {board.items_count} items
                            </Badge>
                          </HStack>
                          <Text fontSize="xs" color="gray.500">
                            Updated {new Date(board.updated_at).toLocaleDateString()}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              )}

              {/* Board Items View */}
              {selectedBoard && (
                <Card mt={6}>
                  <CardHeader>
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Heading size="md">{selectedBoard.name}</Heading>
                        <Text color="gray.600">
                          {boardItems.length} items • {selectedBoard.columns.length} columns
                        </Text>
                      </VStack>
                      <Button
                        leftIcon={<AddIcon />}
                        colorScheme="blue"
                        onClick={onCreateItemOpen}
                      >
                        Add Item
                      </Button>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    {boardItems.length === 0 ? (
                      <Alert status="info">
                        <AlertIcon />
                        No items found in this board
                      </Alert>
                    ) : (
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Name</Th>
                            <Th>Status</Th>
                            <Th>Created</Th>
                            <Th>Updated</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {boardItems.map((item) => (
                            <Tr key={item.id}>
                              <Td fontWeight="medium">{item.name}</Td>
                              <Td>
                                <Badge
                                  colorScheme={
                                    item.state === 'active' ? 'green' : 'gray'
                                  }
                                >
                                  {item.state}
                                </Badge>
                              </Td>
                              <Td>
                                {new Date(item.created_at).toLocaleDateString()}
                              </Td>
                              <Td>
                                {new Date(item.updated_at).toLocaleDateString()}
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    )}
                  </CardBody>
                </Card>
              )}
            </VStack>
          </TabPanel>

          {/* Search Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Heading size="md">Search Items</Heading>

              <FormControl>
                <FormLabel>Search Query</FormLabel>
                <HStack>
                  <Input
                    placeholder="Search across all boards..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                  <Button
                    leftIcon={<SearchIcon />}
                    colorScheme="blue"
                    onClick={handleSearch}
                    isLoading={isLoading}
                  >
                    Search
                  </Button>
                </HStack>
              </FormControl>

              {searchResults.length > 0 && (
                <Card>
                  <CardHeader>
                    <Heading size="sm">
                      {searchResults.length} search results for "{searchQuery}"
                    </Heading>
                  </CardHeader>
                  <CardBody>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Item</Th>
                          <Th>Board</Th>
                          <Th>Status
