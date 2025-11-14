/**
 * Notion Integration Page
 * Complete Notion document and database management integration
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tag,
  TagLabel,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  Spinner,
  Link,
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
  ArrowForwardIcon,
  ListIcon as DatabaseIcon,
  AttachmentIcon as FileIcon,
  ViewIcon as FolderIcon,
  GenericAvatarIcon as UserIcon,
  TimeIcon,
} from "@chakra-ui/icons";

interface NotionPage {
  id: string;
  created_time: string;
  last_edited_time: string;
  properties: {
    title?: {
      title: Array<{ text: { content: string } }>;
    };
    status?: {
      select: { name: string; color?: string };
    };
    priority?: {
      select: { name: string; color?: string };
    };
    assignee?: {
      people: Array<{ name?: string; avatar_url?: string }>;
    };
    due_date?: {
      date: { start: string; end?: string };
    };
    tags?: {
      multi_select: Array<{ name: string; color?: string }>;
    };
    created_by?: {
      created_by: { name?: string; avatar_url?: string };
    };
  };
  parent: {
    type: string;
    page_id?: string;
    database_id?: string;
    workspace?: boolean;
  };
  url: string;
  archived: boolean;
  in_trash: boolean;
  public_url?: string;
}

interface NotionDatabase {
  id: string;
  created_time: string;
  last_edited_time: string;
  title: Array<{ text: { content: string } }>;
  properties: Record<string, any>;
  parent: {
    type: string;
    page_id?: string;
    workspace?: boolean;
  };
  url: string;
  archived: boolean;
  is_inline: boolean;
  description: Array<{ text: { content: string } }>;
  icon: {
    type: string;
    emoji?: string;
    file?: { url: string };
  };
  cover: {
    type: string;
    external?: { url: string };
  };
}

interface NotionUser {
  id: string;
  name?: string;
  avatar_url?: string;
  type: string;
  person?: {
    email: string;
  };
  bot?: {
    owner?: { type: string; user?: { object: string; id: string } };
  };
}

interface NotionSearchResult {
  object: string;
  id: string;
  created_time: string;
  last_edited_time: string;
  has_children: boolean;
  archived: boolean;
  properties?: any;
  title?: string;
  url: string;
}

const NotionIntegration: React.FC = () => {
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [databases, setDatabases] = useState<NotionDatabase[]>([]);
  const [users, setUsers] = useState<NotionUser[]>([]);
  const [searchResults, setSearchResults] = useState<NotionSearchResult[]>([]);
  const [loading, setLoading] = useState({
    pages: false,
    databases: false,
    users: false,
    search: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("all");

  // Form states
  const [pageForm, setPageForm] = useState({
    parent_type: "page",
    parent_id: "",
    title: "",
    children: [] as any[],
  });

  const [databaseForm, setDatabaseForm] = useState({
    parent_type: "page",
    parent_id: "",
    title: "",
    properties: {} as any,
    is_inline: false,
  });

  const {
    isOpen: isPageOpen,
    onOpen: onPageOpen,
    onClose: onPageClose,
  } = useDisclosure();
  const {
    isOpen: isDatabaseOpen,
    onOpen: onDatabaseOpen,
    onClose: onDatabaseClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/notion/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadDatabases();
        loadUsers();
      } else {
        setConnected(false);
        setHealthStatus("error");
      }
    } catch (error) {
      console.error("Health check failed:", error);
      setConnected(false);
      setHealthStatus("error");
    }
  };

  // Load Notion data
  const loadPages = async (databaseId?: string) => {
    setLoading((prev) => ({ ...prev, pages: true }));
    try {
      const response = await fetch("/api/integrations/notion/pages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          database_id: databaseId,
          filter:
            selectedFilter !== "all"
              ? {
                  property: "status",
                  select: { equals: selectedFilter },
                }
              : undefined,
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPages(data.data?.pages || []);
      }
    } catch (error) {
      console.error("Failed to load pages:", error);
      toast({
        title: "Error",
        description: "Failed to load pages from Notion",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, pages: false }));
    }
  };

  const loadDatabases = async () => {
    setLoading((prev) => ({ ...prev, databases: true }));
    try {
      const response = await fetch("/api/integrations/notion/databases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setDatabases(data.data?.databases || []);
        if (data.data?.databases?.length > 0) {
          setSelectedDatabase(data.data.databases[0].id);
        }
      }
    } catch (error) {
      console.error("Failed to load databases:", error);
    } finally {
      setLoading((prev) => ({ ...prev, databases: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/notion/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.data?.users || []);
      }
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setLoading((prev) => ({ ...prev, users: false }));
    }
  };

  const searchNotion = async () => {
    if (!searchQuery) return;

    setLoading((prev) => ({ ...prev, search: true }));
    try {
      const response = await fetch("/api/integrations/notion/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          query: searchQuery,
          filter: {
            property: "object",
            value: selectedFilter === "all" ? undefined : selectedFilter,
          },
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.data?.results || []);
      }
    } catch (error) {
      console.error("Failed to search:", error);
    } finally {
      setLoading((prev) => ({ ...prev, search: false }));
    }
  };

  const createPage = async () => {
    try {
      const response = await fetch("/api/integrations/notion/pages/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          parent: {
            type: pageForm.parent_type,
            [pageForm.parent_type === "database_id"
              ? "database_id"
              : "page_id"]: pageForm.parent_id,
          },
          properties: {
            title: {
              title: [
                {
                  text: {
                    content: pageForm.title,
                  },
                },
              ],
            },
          },
          children: pageForm.children,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Page created successfully",
          status: "success",
          duration: 3000,
        });
        onPageClose();
        setPageForm({
          parent_type: "page",
          parent_id: "",
          title: "",
          children: [],
        });
        if (selectedDatabase) {
          loadPages(selectedDatabase);
        }
      }
    } catch (error) {
      console.error("Failed to create page:", error);
      toast({
        title: "Error",
        description: "Failed to create page",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createDatabase = async () => {
    try {
      const response = await fetch(
        "/api/integrations/notion/databases/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            parent: {
              type: databaseForm.parent_type,
              [databaseForm.parent_type === "page_id"
                ? "page_id"
                : "workspace"]: databaseForm.parent_id,
            },
            title: [
              {
                text: {
                  content: databaseForm.title,
                },
              },
            ],
            properties: databaseForm.properties,
            is_inline: databaseForm.is_inline,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: "Database created successfully",
          status: "success",
          duration: 3000,
        });
        onDatabaseClose();
        setDatabaseForm({
          parent_type: "page",
          parent_id: "",
          title: "",
          properties: {},
          is_inline: false,
        });
        loadDatabases();
      }
    } catch (error) {
      console.error("Failed to create database:", error);
      toast({
        title: "Error",
        description: "Failed to create database",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredDatabases = databases.filter((db) =>
    db.title[0]?.text.content.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredPages = pages.filter((page) =>
    page.properties.title?.title[0]?.text.content
      .toLowerCase()
      .includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalDatabases = databases.length;
  const totalPages = pages.length;
  const totalUsers = users.length;
  const activePages = pages.filter((p) => !p.archived).length;

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (connected) {
      loadDatabases();
      loadUsers();
    }
  }, [connected]);

  useEffect(() => {
    if (selectedDatabase) {
      loadPages(selectedDatabase);
    }
  }, [selectedDatabase, selectedFilter, loadPages]);

  useEffect(() => {
    if (searchQuery) {
      searchNotion();
    } else {
      setSearchResults([]);
    }
  }, [searchQuery, selectedFilter, searchNotion]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusColor = (status?: string): string => {
    switch (status?.toLowerCase()) {
      case "done":
        return "green";
      case "in progress":
        return "yellow";
      case "not started":
        return "gray";
      case "blocked":
        return "red";
      default:
        return "gray";
    }
  };

  const getPriorityColor = (priority?: string): string => {
    switch (priority?.toLowerCase()) {
      case "high":
        return "red";
      case "medium":
        return "yellow";
      case "low":
        return "blue";
      default:
        return "gray";
    }
  };

  const getPageTitle = (page: NotionPage): string => {
    return page.properties.title?.title[0]?.text.content || "Untitled";
  };

  const getDatabaseTitle = (db: NotionDatabase): string => {
    return db.title[0]?.text.content || "Untitled Database";
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="black" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Notion Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Document management and knowledge base platform
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge
              colorScheme={healthStatus === "healthy" ? "green" : "red"}
              display="flex"
              alignItems="center"
            >
              {healthStatus === "healthy" ? (
                <CheckCircleIcon mr={1} />
              ) : (
                <WarningIcon mr={1} />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SettingsIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Notion</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Notion workspace to start managing documents
                    and databases
                  </Text>
                </VStack>
                <Button
                  colorScheme="black"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/notion/auth/start")
                  }
                >
                  Connect Notion Workspace
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Databases</StatLabel>
                    <StatNumber>{totalDatabases}</StatNumber>
                    <StatHelpText>Knowledge bases</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Pages</StatLabel>
                    <StatNumber>{totalPages}</StatNumber>
                    <StatHelpText>{activePages} active</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Users</StatLabel>
                    <StatNumber>{totalUsers}</StatNumber>
                    <StatHelpText>Team members</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Search Results</StatLabel>
                    <StatNumber>{searchResults.length}</StatNumber>
                    <StatHelpText>Current query</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Databases</Tab>
                <Tab>Pages</Tab>
                <Tab>Search</Tab>
                <Tab>Users</Tab>
              </TabList>

              <TabPanels>
                {/* Databases Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search databases..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="black"
                        leftIcon={<AddIcon />}
                        onClick={onDatabaseOpen}
                      >
                        Create Database
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.databases ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredDatabases.map((db) => (
                          <Card
                            key={db.id}
                            cursor="pointer"
                            _hover={{
                              shadow: "md",
                              transform: "translateY(-2px)",
                            }}
                            transition="all 0.2s"
                            onClick={() => {
                              setSelectedDatabase(db.id);
                              loadPages(db.id);
                            }}
                            borderWidth="1px"
                            borderColor={
                              selectedDatabase === db.id
                                ? "blue.500"
                                : borderColor
                            }
                          >
                            <CardHeader>
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {getDatabaseTitle(db)}
                                  </Text>
                                  {db.icon?.emoji && (
                                    <Text fontSize="2xl">{db.icon.emoji}</Text>
                                  )}
                                </HStack>
                                <Text fontSize="sm" color="gray.600">
                                  {db.description[0]?.text.content ||
                                    "No description"}
                                </Text>
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                <HStack justify="space-between">
                                  <Tag colorScheme="blue" size="sm">
                                    Database
                                  </Tag>
                                  <Tag
                                    colorScheme={
                                      db.is_inline ? "green" : "gray"
                                    }
                                    size="sm"
                                  >
                                    {db.is_inline ? "Inline" : "Full Page"}
                                  </Tag>
                                </HStack>
                                <Text fontSize="xs" color="gray.500">
                                  Created: {formatDate(db.created_time)}
                                </Text>
                                <Text fontSize="xs" color="gray.500">
                                  Modified: {formatDate(db.last_edited_time)}
                                </Text>
                                <Link href={db.url} isExternal>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    leftIcon={<ViewIcon />}
                                  >
                                    Open in Notion
                                  </Button>
                                </Link>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Pages Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select database"
                        value={selectedDatabase}
                        onChange={(e) => {
                          setSelectedDatabase(e.target.value);
                          loadPages(e.target.value);
                        }}
                        width="300px"
                      >
                        {databases.map((db) => (
                          <option key={db.id} value={db.id}>
                            {getDatabaseTitle(db)}
                          </option>
                        ))}
                      </Select>
                      <Select
                        placeholder="Filter by status"
                        value={selectedFilter}
                        onChange={(e) => setSelectedFilter(e.target.value)}
                        width="150px"
                      >
                        <option value="all">All Status</option>
                        <option value="Not Started">Not Started</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Done">Done</option>
                      </Select>
                      <Input
                        placeholder="Search pages..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="black"
                        leftIcon={<AddIcon />}
                        onClick={onPageOpen}
                        disabled={!selectedDatabase}
                      >
                        Create Page
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.pages ? (
                        <Spinner size="xl" />
                      ) : selectedDatabase ? (
                        filteredPages.map((page) => (
                          <Card key={page.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <HStack>
                                      <Link href={page.url} isExternal>
                                        <Text fontWeight="bold" fontSize="lg">
                                          {getPageTitle(page)}
                                        </Text>
                                      </Link>
                                      {page.properties.status?.select && (
                                        <Tag
                                          colorScheme={getStatusColor(
                                            page.properties.status.select.name,
                                          )}
                                          size="sm"
                                        >
                                          {page.properties.status.select.name}
                                        </Tag>
                                      )}
                                    </HStack>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(page.last_edited_time)}
                                    </Text>
                                  </HStack>

                                  <HStack spacing={4}>
                                    {page.properties.priority?.select && (
                                      <Tag
                                        colorScheme={getPriorityColor(
                                          page.properties.priority.select.name,
                                        )}
                                        size="sm"
                                      >
                                        Priority:{" "}
                                        {page.properties.priority.select.name}
                                      </Tag>
                                    )}
                                    {page.properties.due_date?.date && (
                                      <Tag colorScheme="blue" size="sm">
                                        Due:{" "}
                                        {new Date(
                                          page.properties.due_date.date.start,
                                        ).toLocaleDateString()}
                                      </Tag>
                                    )}
                                  </HStack>

                                  {page.properties.tags?.multi_select && (
                                    <HStack wrap="wrap">
                                      {page.properties.tags.multi_select.map(
                                        (tag) => (
                                          <Tag
                                            key={tag.name}
                                            size="sm"
                                            colorScheme="gray"
                                          >
                                            {tag.name}
                                          </Tag>
                                        ),
                                      )}
                                    </HStack>
                                  )}

                                  <Link href={page.url} isExternal>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      leftIcon={<ViewIcon />}
                                    >
                                      Open in Notion
                                    </Button>
                                  </Link>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a database to view pages
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Search Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by type"
                        value={selectedFilter}
                        onChange={(e) => setSelectedFilter(e.target.value)}
                        width="150px"
                      >
                        <option value="all">All Types</option>
                        <option value="page">Pages</option>
                        <option value="database">Databases</option>
                      </Select>
                      <Input
                        placeholder="Search all content..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                        onKeyPress={(e) => {
                          if (e.key === "Enter") {
                            searchNotion();
                          }
                        }}
                      />
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.search ? (
                        <Spinner size="xl" />
                      ) : searchResults.length > 0 ? (
                        searchResults.map((result) => (
                          <Card key={result.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon
                                  as={
                                    result.object === "database"
                                      ? DatabaseIcon
                                      : FileIcon
                                  }
                                  color="blue.500"
                                  w={6}
                                  h={6}
                                />
                                <VStack align="start" spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Link href={result.url} isExternal>
                                      <Text fontWeight="bold">
                                        {result.title || result.object}
                                      </Text>
                                    </Link>
                                    <Tag colorScheme="blue" size="sm">
                                      {result.object}
                                    </Tag>
                                  </HStack>
                                  <Text fontSize="xs" color="gray.500">
                                    Modified:{" "}
                                    {formatDate(result.last_edited_time)}
                                  </Text>
                                  <Link href={result.url} isExternal>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      leftIcon={<ViewIcon />}
                                    >
                                      Open in Notion
                                    </Button>
                                  </Link>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : searchQuery ? (
                        <Text color="gray.500" textAlign="center" py={8}>
                          No results found for &ldquo;{searchQuery}&rdquo;
                        </Text>
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Enter a search query to find content
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search users..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                      />
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        users
                          .filter(
                            (user) =>
                              user.name
                                ?.toLowerCase()
                                .includes(searchQuery.toLowerCase()) ||
                              user.person?.email
                                ?.toLowerCase()
                                .includes(searchQuery.toLowerCase()),
                          )
                          .map((user) => (
                            <Card key={user.id}>
                              <CardBody>
                                <HStack spacing={4}>
                                  <Avatar
                                    src={user.avatar_url}
                                    name={user.name}
                                    size="lg"
                                  />
                                  <VStack align="start" spacing={1} flex={1}>
                                    <Text fontWeight="bold">
                                      {user.name || "Unknown"}
                                    </Text>
                                    {user.person?.email && (
                                      <Text fontSize="sm" color="gray.600">
                                        {user.person.email}
                                      </Text>
                                    )}
                                    <HStack spacing={2}>
                                      <Tag
                                        colorScheme={
                                          user.type === "person"
                                            ? "green"
                                            : "blue"
                                        }
                                        size="sm"
                                      >
                                        {user.type}
                                      </Tag>
                                    </HStack>
                                  </VStack>
                                </HStack>
                              </CardBody>
                            </Card>
                          ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Page Modal */}
            <Modal isOpen={isPageOpen} onClose={onPageClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Page</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Parent</FormLabel>
                      <Select
                        value={pageForm.parent_id}
                        onChange={(e) =>
                          setPageForm({
                            ...pageForm,
                            parent_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Select parent</option>
                        <option value={selectedDatabase}>
                          Selected Database
                        </option>
                        {databases.map((db) => (
                          <option key={db.id} value={db.id}>
                            {getDatabaseTitle(db)}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Page Title</FormLabel>
                      <Input
                        placeholder="Enter page title"
                        value={pageForm.title}
                        onChange={(e) =>
                          setPageForm({
                            ...pageForm,
                            title: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Initial Content</FormLabel>
                      <Textarea
                        placeholder="Optional initial content..."
                        value={
                          pageForm.children?.[0]?.text?.[0]?.text?.content || ""
                        }
                        onChange={(e) =>
                          setPageForm({
                            ...pageForm,
                            children: e.target.value
                              ? [
                                  {
                                    object: "block",
                                    type: "paragraph",
                                    paragraph: {
                                      text: [
                                        {
                                          type: "text",
                                          text: { content: e.target.value },
                                        },
                                      ],
                                    },
                                  },
                                ]
                              : [],
                          })
                        }
                        rows={4}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onPageClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="black"
                    onClick={createPage}
                    disabled={!pageForm.title}
                  >
                    Create Page
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Database Modal */}
            <Modal isOpen={isDatabaseOpen} onClose={onDatabaseClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Database</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Parent</FormLabel>
                      <Select
                        value={databaseForm.parent_id}
                        onChange={(e) =>
                          setDatabaseForm({
                            ...databaseForm,
                            parent_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Workspace Root</option>
                        {databases.map((db) => (
                          <option key={db.id} value={db.id}>
                            Inside: {getDatabaseTitle(db)}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Database Name</FormLabel>
                      <Input
                        placeholder="Enter database name"
                        value={databaseForm.title}
                        onChange={(e) =>
                          setDatabaseForm({
                            ...databaseForm,
                            title: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Database Type</FormLabel>
                      <Select
                        value={databaseForm.is_inline ? "inline" : "full"}
                        onChange={(e) =>
                          setDatabaseForm({
                            ...databaseForm,
                            is_inline: e.target.value === "inline",
                          })
                        }
                      >
                        <option value="full">Full Page</option>
                        <option value="inline">Inline</option>
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onDatabaseClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="black"
                    onClick={createDatabase}
                    disabled={!databaseForm.title}
                  >
                    Create Database
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default NotionIntegration;
