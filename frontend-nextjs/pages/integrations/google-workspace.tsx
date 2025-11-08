/**
 * Google Workspace Integration Page
 * Complete Google Workspace productivity suite integration
 */

import React, { useState, useEffect } from 'react';
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
  Spacer,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  useDisclosure,
  Tag,
  TagLabel,
  Flex,
  Grid,
  GridItem,
  Alert,
  AlertIcon,
  Avatar,
  Image,
  IconButton,
  Tooltip,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  CheckboxGroup,
  Checkbox,
  Select,
} from "@chakra-ui/react";
import {
  DocumentIcon,
  Icon as ChakraIcon,
  SearchIcon,
  AddIcon,
  EditIcon,
  DeleteIcon,
  ExternalLinkIcon,
  ViewIcon,
  RepeatIcon,
  SettingsIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  TimeIcon,
  CalendarIcon,
  NotesIcon,
  SheetIcon,
  SlidesIcon,
  ChatIcon,
  TaskIcon,
  FolderIcon,
  ShareIcon,
  DownloadIcon,
} from "@chakra-ui/icons";

interface GoogleDocument {
  id: string;
  name: string;
  type: string;
  mimeType: string;
  created: string;
  modified: string;
  webViewLink: string;
  owner: string;
  ownerEmail: string;
  thumbnail: string;
  shared: boolean;
  size: string;
  version: string;
  contentLength: number;
  documentId: string;
  slideCount: number;
  sheetCount: number;
  notesCount: number;
  tasksCount: number;
}

interface GoogleNote {
  id: string;
  title: string;
  content: string;
  color: string;
  labels: string[];
  created: string;
  modified: string;
  archived: boolean;
  pinned: boolean;
  reminder?: string;
  checklistItems?: string[];
  attachments?: any[];
}

interface GoogleTask {
  id: string;
  title: string;
  notes?: string;
  status: string;
  due?: string;
  position: string;
  parent?: string;
  taskListId: string;
  taskListTitle: string;
  isCompleted: boolean;
  hasNotes: boolean;
  hasDueDate: boolean;
  isOverdue: boolean;
}

const GoogleWorkspaceIntegration: React.FC = () => {
  const [documents, setDocuments] = useState<GoogleDocument[]>([]);
  const [notes, setNotes] = useState<GoogleNote[]>([]);
  const [tasks, setTasks] = useState<GoogleTask[]>([]);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "error" | "unknown">("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedService, setSelectedService] = useState("all");
  const [loading, setLoading] = useState({
    docs: false,
    notes: false,
    tasks: false,
    search: false,
    create: false,
  });

  // Document/Note/Task creation states
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [noteColor, setNoteColor] = useState("DEFAULT");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskNotes, setTaskNotes] = useState("");
  const [taskListId, setTaskListId] = useState("");
  const [taskDue, setTaskDue] = useState("");

  const { isOpen: isDocOpen, onOpen: onDocOpen, onClose: onDocClose } = useDisclosure();
  const { isOpen: isNoteOpen, onOpen: onNoteOpen, onClose: onNoteClose } = useDisclosure();
  const { isOpen: isTaskOpen, onOpen: onTaskOpen, onClose: onTaskClose } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/google-workspace/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
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

  // Load documents
  const loadDocuments = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, docs: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/docs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery || undefined,
          page_size: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setDocuments(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load documents:", error);
    } finally {
      setLoading((prev) => ({ ...prev, docs: false }));
    }
  };

  // Load notes
  const loadNotes = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, notes: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/keep/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery || undefined,
          page_size: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setNotes(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load notes:", error);
    } finally {
      setLoading((prev) => ({ ...prev, notes: false }));
    }
  };

  // Load tasks
  const loadTasks = async () => {
    if (!connected) return;

    setLoading((prev) => ({ ...prev, tasks: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_list_id: taskListId || undefined,
          max_results: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTasks(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load tasks:", error);
    } finally {
      setLoading((prev) => ({ ...prev, tasks: false }));
    }
  };

  // Create document
  const createDocument = async () => {
    if (!documentTitle.trim()) return;

    setLoading((prev) => ({ ...prev, create: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/docs/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: documentTitle,
          content: documentContent,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast({
            title: "Document created",
            status: "success",
            duration: 3000,
          });
          setDocumentTitle("");
          setDocumentContent("");
          onDocClose();
          await loadDocuments();
        }
      }
    } catch (error) {
      console.error("Failed to create document:", error);
      toast({
        title: "Failed to create document",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, create: false }));
    }
  };

  // Create note
  const createNote = async () => {
    if (!noteTitle.trim()) return;

    setLoading((prev) => ({ ...prev, create: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/keep/notes/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: noteTitle,
          content: noteContent,
          color: noteColor,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast({
            title: "Note created",
            status: "success",
            duration: 3000,
          });
          setNoteTitle("");
          setNoteContent("");
          onNoteClose();
          await loadNotes();
        }
      }
    } catch (error) {
      console.error("Failed to create note:", error);
      toast({
        title: "Failed to create note",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, create: false }));
    }
  };

  // Create task
  const createTask = async () => {
    if (!taskTitle.trim() || !taskListId) return;

    setLoading((prev) => ({ ...prev, create: true }));
    try {
      const response = await fetch("/api/integrations/google-workspace/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_list_id: taskListId,
          title: taskTitle,
          notes: taskNotes,
          due: taskDue || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast({
            title: "Task created",
            status: "success",
            duration: 3000,
          });
          setTaskTitle("");
          setTaskNotes("");
          setTaskDue("");
          onTaskClose();
          await loadTasks();
        }
      }
    } catch (error) {
      console.error("Failed to create task:", error);
      toast({
        title: "Failed to create task",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, create: false }));
    }
  };

  // Search across Google Workspace
  const searchWorkspace = async () => {
    if (!searchQuery.trim() || !connected) return;

    setLoading((prev) => ({ ...prev, search: true }));
    try {
      const searchPromises = [];

      if (selectedService === "all" || selectedService === "docs") {
        searchPromises.push(
          fetch("/api/integrations/google-workspace/docs/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: searchQuery,
              scope: "all",
            }),
          })
        );
      }

      if (selectedService === "all" || selectedService === "keep") {
        searchPromises.push(
          fetch("/api/integrations/google-workspace/keep/notes/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: searchQuery,
            }),
          })
        );
      }

      if (selectedService === "all" || selectedService === "tasks") {
        searchPromises.push(
          fetch("/api/integrations/google-workspace/tasks/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: searchQuery,
            }),
          })
        );
      }

      const results = await Promise.all(searchPromises);
      const searchResultsData = [];

      results.forEach((response, index) => {
        const service = index === 0 ? "docs" : index === 1 ? "keep" : "tasks";
        if (response.ok) {
          const data = response.json();
          searchResultsData.push({
            service,
            data: data.data || [],
            total: data.total || 0,
          });
        }
      });

      setSearchResults(searchResultsData);
    } catch (error) {
      console.error("Failed to search workspace:", error);
    } finally {
      setLoading((prev) => ({ ...prev, search: false }));
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadDocuments();
      loadNotes();
      loadTasks();
    }
  }, [connected]);

  const getServiceIcon = (type: string, mimeType?: string) => {
    if (mimeType?.includes("document") || type === "document") return DocumentIcon;
    if (mimeType?.includes("spreadsheet") || type === "spreadsheet") return SheetIcon;
    if (mimeType?.includes("presentation") || type === "presentation") return SlidesIcon;
    if (type === "note") return NotesIcon;
    if (type === "task") return TaskIcon;
    return FolderIcon;
  };

  const getServiceColor = (type: string, mimeType?: string) => {
    if (mimeType?.includes("document") || type === "document") return "blue";
    if (mimeType?.includes("spreadsheet") || type === "spreadsheet") return "green";
    if (mimeType?.includes("presentation") || type === "presentation") return "orange";
    if (type === "note") return "yellow";
    if (type === "task") return "purple";
    return "gray";
  };

  const formatDate = (timestamp: string | number): string => {
    return new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp).toLocaleString();
  };

  const formatFileSize = (bytes: string): string => {
    const size = parseInt(bytes);
    if (size === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(size) / Math.log(k));
    return parseFloat((size / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // Stats calculations
  const totalDocs = documents.length;
  const totalNotes = notes.length;
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter(t => t.isCompleted).length;
  const pendingTasks = tasks.filter(t => !t.isCompleted).length;

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={DocumentIcon} w={8} h={8} color="orange.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Google Workspace Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete productivity suite integration
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
                <Icon as={DocumentIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Google Workspace</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Google account to access Docs, Sheets, Slides, Keep, and Tasks
                  </Text>
                </VStack>
                <Button
                  colorScheme="orange"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/google-drive/auth")
                  }
                >
                  Connect Google Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Documents</StatLabel>
                    <StatNumber>{totalDocs}</StatNumber>
                    <StatHelpText>Docs, Sheets, Slides</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Notes</StatLabel>
                    <StatNumber>{totalNotes}</StatNumber>
                    <StatHelpText>Google Keep notes</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Tasks</StatLabel>
                    <StatNumber>{totalTasks}</StatNumber>
                    <StatHelpText>All task lists</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Completed</StatLabel>
                    <StatNumber>{completedTasks}</StatNumber>
                    <StatHelpText>Tasks completed</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Pending</StatLabel>
                    <StatNumber>{pendingTasks}</StatNumber>
                    <StatHelpText>Tasks pending</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Documents</Tab>
                <Tab>Notes</Tab>
                <Tab>Tasks</Tab>
                <Tab>Search</Tab>
              </TabList>

              <TabPanels>
                {/* Documents Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search documents..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Button
                        colorScheme="orange"
                        leftIcon={<AddIcon />}
                        onClick={onDocOpen}
                      >
                        New Document
                      </Button>
                      <Button
                        colorScheme="orange"
                        leftIcon={<RepeatIcon />}
                        onClick={loadDocuments}
                        isLoading={loading.docs}
                      >
                        Refresh
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Type</Th>
                                <Th>Owner</Th>
                                <Th>Modified</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {documents.map((doc) => (
                                <Tr key={doc.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={getServiceIcon(doc.type, doc.mimeType)} 
                                           color={getServiceColor(doc.type, doc.mimeType) + ".500"} />
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">{doc.name}</Text>
                                        <Text fontSize="sm" color="gray.600">
                                          {doc.size && formatFileSize(doc.size)}
                                        </Text>
                                      </VStack>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Badge colorScheme={getServiceColor(doc.type, doc.mimeType)} size="sm">
                                      <TagLabel>{doc.type}</TagLabel>
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{doc.owner}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(doc.modified)}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ViewIcon />}
                                        onClick={() => window.open(doc.webViewLink)}
                                      >
                                        Open
                                      </Button>
                                    </HStack>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Notes Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search notes..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Button
                        colorScheme="orange"
                        leftIcon={<AddIcon />}
                        onClick={onNoteOpen}
                      >
                        New Note
                      </Button>
                      <Button
                        colorScheme="orange"
                        leftIcon={<RepeatIcon />}
                        onClick={loadNotes}
                        isLoading={loading.notes}
                      >
                        Refresh
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {notes.map((note) => (
                            <Box key={note.id} p={4} borderWidth="1px" borderRadius="md">
                              <HStack spacing={3} mb={2}>
                                <Box w="4" h="4" rounded="full" bg={note.color.toLowerCase()} />
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight="medium">{note.title}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {formatDate(note.modified)}
                                  </Text>
                                </VStack>
                                <Spacer />
                                {note.pinned && (
                                  <Icon as={SettingsIcon} color="gray.500" />
                                )}
                              </HStack>
                              
                              <Text mb={2} noOfLines={3}>{note.content}</Text>
                              
                              {note.labels && note.labels.length > 0 && (
                                <HStack>
                                  {note.labels.map((label, index) => (
                                    <Tag key={index} size="sm" colorScheme="blue">
                                      <TagLabel>{label}</TagLabel>
                                    </Tag>
                                  ))}
                                </HStack>
                              )}
                            </Box>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Tasks Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="All task lists"
                        value={taskListId}
                        onChange={(e) => setTaskListId(e.target.value)}
                        width="200px"
                      >
                        <option value="">All Task Lists</option>
                        {/* Add task list options here */}
                      </Select>
                      <Button
                        colorScheme="orange"
                        leftIcon={<AddIcon />}
                        onClick={onTaskOpen}
                      >
                        New Task
                      </Button>
                      <Button
                        colorScheme="orange"
                        leftIcon={<RepeatIcon />}
                        onClick={loadTasks}
                        isLoading={loading.tasks}
                      >
                        Refresh
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {tasks.map((task) => (
                            <Box key={task.id} p={4} borderWidth="1px" borderRadius="md">
                              <HStack spacing={3} mb={2}>
                                <Checkbox isChecked={task.isCompleted} />
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight={task.isCompleted ? "line-through" : "medium"}>
                                    {task.title}
                                  </Text>
                                  {task.due && (
                                    <Text fontSize="sm" color={task.isOverdue ? "red.500" : "gray.600"}>
                                      Due: {formatDate(task.due)}
                                    </Text>
                                  )}
                                </VStack>
                                <Spacer />
                                {task.isOverdue && (
                                  <Badge colorScheme="red" size="sm">
                                    Overdue
                                  </Badge>
                                )}
                              </HStack>
                              
                              {task.notes && (
                                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                  {task.notes}
                                </Text>
                              )}
                            </Box>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Search Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Search all services"
                        value={selectedService}
                        onChange={(e) => setSelectedService(e.target.value)}
                        width="200px"
                      >
                        <option value="all">All Services</option>
                        <option value="docs">Documents</option>
                        <option value="keep">Notes</option>
                        <option value="tasks">Tasks</option>
                      </Select>
                      <Input
                        placeholder="Search workspace..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            searchWorkspace();
                          }
                        }}
                      />
                      <Button
                        colorScheme="orange"
                        onClick={searchWorkspace}
                        isLoading={loading.search}
                        disabled={!searchQuery.trim()}
                      >
                        Search
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={6} align="stretch">
                          {searchResults.map((result, index) => (
                            <Box key={index}>
                              <Heading size="sm" mb={4}>
                                {result.service.charAt(0).toUpperCase() + result.service.slice(1)} ({result.total} results)
                              </Heading>
                              
                              <VStack spacing={2} align="stretch">
                                {result.data.map((item: any, itemIndex: number) => (
                                  <Box key={itemIndex} p={3} borderWidth="1px" borderRadius="md">
                                    <HStack spacing={3}>
                                      <Icon as={getServiceIcon(item.type)} 
                                           color={getServiceColor(item.type) + ".500"} />
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">{item.title || item.name}</Text>
                                        <Text fontSize="sm" color="gray.600">
                                          {item.content ? item.content.substring(0, 100) + "..." : ""}
                                        </Text>
                                      </VStack>
                                    </HStack>
                                  </Box>
                                ))}
                              </VStack>
                              
                              {index < searchResults.length - 1 && <Divider />}
                            </Box>
                          ))}
                          
                          {searchResults.length === 0 && searchQuery && (
                            <VStack spacing={4} py={8}>
                              <Icon as={SearchIcon} w={12} h={12} color="gray.400" />
                              <Text color="gray.600">No search results found</Text>
                            </VStack>
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </>
        )}

        {/* Create Document Modal */}
        <Modal isOpen={isDocOpen} onClose={onDocClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Document</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Title</FormLabel>
                  <Input
                    value={documentTitle}
                    onChange={(e) => setDocumentTitle(e.target.value)}
                    placeholder="Document title"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Content</FormLabel>
                  <Textarea
                    value={documentContent}
                    onChange={(e) => setDocumentContent(e.target.value)}
                    placeholder="Document content (optional)"
                    rows={6}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={onDocClose}>
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={createDocument}
                isLoading={loading.create}
                disabled={!documentTitle.trim()}
              >
                Create Document
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Note Modal */}
        <Modal isOpen={isNoteOpen} onClose={onNoteClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Note</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Title</FormLabel>
                  <Input
                    value={noteTitle}
                    onChange={(e) => setNoteTitle(e.target.value)}
                    placeholder="Note title"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Content</FormLabel>
                  <Textarea
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                    placeholder="Note content"
                    rows={6}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Color</FormLabel>
                  <Select
                    value={noteColor}
                    onChange={(e) => setNoteColor(e.target.value)}
                  >
                    <option value="DEFAULT">Default</option>
                    <option value="RED">Red</option>
                    <option value="ORANGE">Orange</option>
                    <option value="YELLOW">Yellow</option>
                    <option value="GREEN">Green</option>
                    <option value="BLUE">Blue</option>
                    <option value="PURPLE">Purple</option>
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={onNoteClose}>
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={createNote}
                isLoading={loading.create}
                disabled={!noteTitle.trim()}
              >
                Create Note
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Task Modal */}
        <Modal isOpen={isTaskOpen} onClose={onTaskClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Task</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Task List</FormLabel>
                  <Select
                    value={taskListId}
                    onChange={(e) => setTaskListId(e.target.value)}
                    placeholder="Select task list"
                  >
                    <option value="">Select a task list</option>
                    {/* Add task list options here */}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Title</FormLabel>
                  <Input
                    value={taskTitle}
                    onChange={(e) => setTaskTitle(e.target.value)}
                    placeholder="Task title"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Notes</FormLabel>
                  <Textarea
                    value={taskNotes}
                    onChange={(e) => setTaskNotes(e.target.value)}
                    placeholder="Task notes (optional)"
                    rows={3}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Due Date</FormLabel>
                  <Input
                    type="datetime-local"
                    value={taskDue}
                    onChange={(e) => setTaskDue(e.target.value)}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={onTaskClose}>
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={createTask}
                isLoading={loading.create}
                disabled={!taskTitle.trim() || !taskListId}
              >
                Create Task
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default GoogleWorkspaceIntegration;