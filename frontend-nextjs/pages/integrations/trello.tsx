/**
 * Trello Integration Page
 * Complete Trello integration with comprehensive project and task management features
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Button,
  Input,
  FormLabel,
  Textarea,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Badge,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Select,
  VStack,
  HStack,
  Text,
  Spinner,
  IconButton,
  useToast,
  useColorModeValue,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningIcon,
  RepeatIcon,
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  SearchIcon,
  StarIcon,
  CalendarIcon,
  AttachmentIcon,
} from "@chakra-ui/icons";

interface TrelloBoard {
  id: string;
  name: string;
  description: string;
  url: string;
  closed: boolean;
  starred: boolean;
  lists: TrelloList[];
  members: TrelloMember[];
}

interface TrelloList {
  id: string;
  name: string;
  closed: boolean;
  position: number;
  cards: TrelloCard[];
}

interface TrelloCard {
  id: string;
  name: string;
  description: string;
  due: string;
  dueComplete: boolean;
  url: string;
  cover: any;
  attachments: any[];
  labels: TrelloLabel[];
  members: TrelloMember[];
  listId: string;
  boardId: string;
}

interface TrelloLabel {
  id: string;
  name: string;
  color: string;
}

interface TrelloMember {
  id: string;
  fullName: string;
  username: string;
  avatarUrl: string;
}

interface TrelloStatus {
  service: string;
  status: "connected" | "disconnected" | "error";
  timestamp: string;
  boards: number;
  cards: number;
  members: number;
}

const TrelloIntegration: React.FC = () => {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<TrelloStatus | null>(null);
  const [boards, setBoards] = useState<TrelloBoard[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<string>("");
  const [lists, setLists] = useState<TrelloList[]>([]);
  const [cards, setCards] = useState<TrelloCard[]>([]);
  const [members, setMembers] = useState<TrelloMember[]>([]);
  const [activeTab, setActiveTab] = useState("boards");
  const [searchQuery, setSearchQuery] = useState("");
  const [newCardTitle, setNewCardTitle] = useState("");
  const [newCardDescription, setNewCardDescription] = useState("");
  const [selectedList, setSelectedList] = useState("");

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const TRELLO_OAUTH_URL = `${API_BASE_URL}/api/v1/trello/oauth`;

  const bgColor = useColorModeValue("gray.50", "gray.900");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const cardBg = useColorModeValue("white", "gray.800");

  const loadStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/trello/status`);
      const data = await response.json();

      if (data.status === "connected") {
        setStatus(data);
        toast({
          title: "Trello Status Loaded",
          description: "Successfully connected to Trello",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
      } else {
        setStatus(data);
        toast({
          title: "Trello Disconnected",
          description: "Please connect your Trello account",
          status: "warning",
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error("Error loading Trello status:", error);
      toast({
        title: "Error Loading Trello Status",
        description: "Failed to connect to Trello",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBoards = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/trello/boards`);
      const data = await response.json();
      setBoards(data.boards || []);
    } catch (error) {
      console.error("Error loading boards:", error);
      toast({
        title: "Error Loading Boards",
        description: "Failed to load Trello boards",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const loadLists = async (boardId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/trello/boards/${boardId}/lists`,
      );
      const data = await response.json();
      setLists(data.lists || []);
    } catch (error) {
      console.error("Error loading lists:", error);
      toast({
        title: "Error Loading Lists",
        description: "Failed to load Trello lists",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const loadCards = async (boardId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/trello/boards/${boardId}/cards`,
      );
      const data = await response.json();
      setCards(data.cards || []);
    } catch (error) {
      console.error("Error loading cards:", error);
      toast({
        title: "Error Loading Cards",
        description: "Failed to load Trello cards",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const loadMembers = async (boardId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/trello/boards/${boardId}/members`,
      );
      const data = await response.json();
      setMembers(data.members || []);
    } catch (error) {
      console.error("Error loading members:", error);
      toast({
        title: "Error Loading Members",
        description: "Failed to load Trello members",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const initiateOAuth = async () => {
    setLoading(true);
    try {
      const response = await fetch(TRELLO_OAUTH_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: "current_user" }),
      });

      const data = await response.json();

      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error("No authentication URL received");
      }
    } catch (error) {
      console.error("Error initiating OAuth:", error);
      toast({
        title: "OAuth Initiation Failed",
        description: "Failed to start Trello authentication",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const createCard = async () => {
    if (!newCardTitle.trim() || !selectedList) {
      toast({
        title: "Missing Information",
        description: "Please select a list and enter a card title",
        status: "warning",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/trello/cards`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          list_id: selectedList,
          name: newCardTitle,
          description: newCardDescription,
        }),
      });

      const data = await response.json();

      if (data.success) {
        toast({
          title: "Card Created",
          description: "Successfully created new Trello card",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        setNewCardTitle("");
        setNewCardDescription("");
        if (selectedBoard) {
          loadCards(selectedBoard);
        }
      } else {
        throw new Error(data.error || "Failed to create card");
      }
    } catch (error) {
      console.error("Error creating card:", error);
      toast({
        title: "Card Creation Failed",
        description: "Failed to create Trello card",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const searchCards = async () => {
    if (!searchQuery.trim()) {
      toast({
        title: "Empty Search",
        description: "Please enter a search query",
        status: "warning",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/trello/cards/search`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: searchQuery,
          }),
        },
      );

      const data = await response.json();
      setCards(data.cards || []);

      toast({
        title: "Search Complete",
        description: `Found ${data.cards?.length || 0} cards`,
        status: "success",
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error searching cards:", error);
      toast({
        title: "Search Failed",
        description: "Failed to search Trello cards",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleBoardSelect = (boardId: string) => {
    setSelectedBoard(boardId);
    if (boardId) {
      loadLists(boardId);
      loadCards(boardId);
      loadMembers(boardId);
    } else {
      setLists([]);
      setCards([]);
      setMembers([]);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    if (status?.status === "connected") {
      loadBoards();
    }
  }, [status]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "green";
      case "disconnected":
        return "yellow";
      case "error":
        return "red";
      default:
        return "gray";
    }
  };

  const getLabelColor = (color: string) => {
    const colorMap: { [key: string]: string } = {
      green: "green",
      yellow: "yellow",
      orange: "orange",
      red: "red",
      purple: "purple",
      blue: "blue",
      sky: "cyan",
      lime: "green",
      pink: "pink",
      black: "gray",
    };
    return colorMap[color] || "gray";
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <Heading size="2xl">Trello Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete Trello integration with boards, lists, cards, and project
            management features
          </Text>

          {/* Status Card */}
          <Card bg={cardBg} border="1px" borderColor={borderColor} w="100%">
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Connection Status</Heading>
                <IconButton
                  aria-label="Refresh status"
                  icon={<RepeatIcon />}
                  onClick={loadStatus}
                  isLoading={loading}
                />
              </HStack>
            </CardHeader>
            <CardBody>
              {status ? (
                <VStack align="start" spacing={4}>
                  <HStack>
                    <Badge
                      colorScheme={getStatusColor(status.status)}
                      fontSize="md"
                      px={3}
                      py={1}
                    >
                      {status.status.toUpperCase()}
                    </Badge>
                    <Text fontSize="sm" color="gray.600">
                      Last updated:{" "}
                      {new Date(status.timestamp).toLocaleString()}
                    </Text>
                  </HStack>

                  <HStack spacing={6}>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Boards</Text>
                      <Text fontSize="xl">{status.boards}</Text>
                    </VStack>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Cards</Text>
                      <Text fontSize="xl">{status.cards}</Text>
                    </VStack>
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold">Members</Text>
                      <Text fontSize="xl">{status.members}</Text>
                    </VStack>
                  </HStack>

                  {status.status !== "connected" && (
                    <Button
                      colorScheme="blue"
                      onClick={initiateOAuth}
                      isLoading={loading}
                      leftIcon={<SettingsIcon />}
                    >
                      Connect Trello
                    </Button>
                  )}
                </VStack>
              ) : (
                <HStack>
                  <Spinner size="sm" />
                  <Text>Loading Trello status...</Text>
                </HStack>
              )}
            </CardBody>
          </Card>
        </VStack>

        {/* Main Content */}
        <Card bg={cardBg} border="1px" borderColor={borderColor}>
          <CardHeader>
            <Tabs
              variant="enclosed"
              onChange={(index) =>
                setActiveTab(["boards", "cards", "create"][index] || "boards")
              }
            >
              <TabList>
                <Tab>
                  <HStack>
                    <ViewIcon />
                    <Text>Boards</Text>
                    <Badge colorScheme="blue" ml={2}>
                      {boards.length}
                    </Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <ViewIcon />
                    <Text>Cards</Text>
                    <Badge colorScheme="green" ml={2}>
                      {cards.length}
                    </Badge>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <AddIcon />
                    <Text>Create Card</Text>
                  </HStack>
                </Tab>
              </TabList>
            </Tabs>
          </CardHeader>

          <CardBody>
            <TabPanels>
              {/* Boards Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  <Select
                    placeholder="Select a board"
                    value={selectedBoard}
                    onChange={(e) => handleBoardSelect(e.target.value)}
                  >
                    {boards.map((board) => (
                      <option key={board.id} value={board.id}>
                        {board.name} {board.starred && "⭐"}
                      </option>
                    ))}
                  </Select>

                  {selectedBoard && (
                    <VStack spacing={4} align="stretch">
                      <Heading size="md">Lists</Heading>
                      {lists.length > 0 ? (
                        lists.map((list) => (
                          <Card key={list.id} variant="outline">
                            <CardBody>
                              <VStack align="start" spacing={2}>
                                <Heading size="sm">{list.name}</Heading>
                                <Text color="gray.600" fontSize="sm">
                                  {list.cards?.length || 0} cards
                                </Text>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Alert status="info">
                          <AlertIcon />
                          <AlertTitle>No Lists</AlertTitle>
                          <AlertDescription>
                            No lists found in this board.
                          </AlertDescription>
                        </Alert>
                      )}

                      <Heading size="md">Members</Heading>
                      {members.length > 0 ? (
                        members.map((member) => (
                          <Card key={member.id} variant="outline">
                            <CardBody>
                              <HStack>
                                <Text fontWeight="bold">{member.fullName}</Text>
                                <Text color="gray.600" fontSize="sm">
                                  @{member.username}
                                </Text>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Alert status="info">
                          <AlertIcon />
                          <AlertTitle>No Members</AlertTitle>
                          <AlertDescription>
                            No members found in this board.
                          </AlertDescription>
                        </Alert>
                      )}
                    </VStack>
                  )}
                </VStack>
              </TabPanel>

              {/* Cards Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  {/* Search Cards */}
                  <Card variant="outline">
                    <CardBody>
                      <VStack spacing={4}>
                        <FormLabel>Search Cards</FormLabel>
                        <HStack w="100%">
                          <Input
                            placeholder="Search cards..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                          />
                          <Button
                            onClick={searchCards}
                            isLoading={loading}
                            leftIcon={<SearchIcon />}
                          >
                            Search
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Cards List */}
                  {cards.length > 0 ? (
                    cards.map((card) => (
                      <Card key={card.id} variant="outline">
                        <CardBody>
                          <VStack align="start" spacing={2}>
                            <HStack justify="space-between" w="100%">
                              <Heading size="sm">{card.name}</Heading>
                            </HStack>
                            {card.description && (
                              <Text fontSize="sm" color="gray.600">
                                {card.description}
                              </Text>
                            )}
                            <HStack spacing={2}>
                              {card.labels?.map((label) => (
                                <Badge
                                  key={label.id}
                                  colorScheme={getLabelColor(label.color)}
                                  fontSize="xs"
                                >
                                  {label.name}
                                </Badge>
                              ))}
                              {card.due && (
                                <Badge colorScheme="orange" fontSize="xs">
                                  <HStack spacing={1}>
                                    <CalendarIcon boxSize={2} />
                                    <Text>
                                      {new Date(card.due).toLocaleDateString()}
                                    </Text>
                                  </HStack>
                                </Badge>
                              )}
                            </HStack>
                            {card.members?.length > 0 && (
                              <Text fontSize="sm" color="gray.600">
                                <strong>Members:</strong>{" "}
                                {card.members.map((m) => m.fullName).join(", ")}
                              </Text>
                            )}
                          </VStack>
                        </CardBody>
                      </Card>
                    ))
                  ) : (
                    <Alert status="info">
                      <AlertIcon />
                      <AlertTitle>No Cards</AlertTitle>
                      <AlertDescription>
                        No Trello cards found. Try creating a card or searching
                        for existing cards.
                      </AlertDescription>
                    </Alert>
                  )}
                </VStack>
              </TabPanel>

              {/* Create Card Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  <Card variant="outline">
                    <CardBody>
                      <VStack spacing={4}>
                        <FormLabel>Create New Card</FormLabel>
                        <Select
                          placeholder="Select a board"
                          value={selectedBoard}
                          onChange={(e) => handleBoardSelect(e.target.value)}
                        >
                          {boards.map((board) => (
                            <option key={board.id} value={board.id}>
                              {board.name} {board.starred && "⭐"}
                            </option>
                          ))}
                        </Select>
                        {selectedBoard && (
                          <>
                            <Select
                              placeholder="Select a list"
                              value={selectedList}
                              onChange={(e) => setSelectedList(e.target.value)}
                            >
                              {lists.map((list) => (
                                <option key={list.id} value={list.id}>
                                  {list.name}
                                </option>
                              ))}
                            </Select>
                            <Input
                              placeholder="Card title"
                              value={newCardTitle}
                              onChange={(e) => setNewCardTitle(e.target.value)}
                            />
                            <Textarea
                              placeholder="Card description (optional)"
                              value={newCardDescription}
                              onChange={(e) =>
                                setNewCardDescription(e.target.value)
                              }
                              rows={3}
                            />
                            <Button
                              colorScheme="blue"
                              onClick={createCard}
                              isLoading={loading}
                              leftIcon={<AddIcon />}
                              isDisabled={!selectedList || !newCardTitle.trim()}
                            >
                              Create Card
                            </Button>
                          </>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                </VStack>
              </TabPanel>
            </TabPanels>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default TrelloIntegration;
