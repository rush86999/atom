/**
 * Box Integration Page
 * Complete Box file storage and collaboration platform integration
 */

import React, { useState, useEffect } from "react";
import {
  Box as ChakraBox,
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
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  EmailIcon,
  CalendarIcon,
} from "@chakra-ui/icons";

interface BoxFile {
  id: string;
  type: string;
  name: string;
  size?: number;
  created_at: string;
  modified_at: string;
  content_created_at?: string;
  content_modified_at?: string;
  description?: string;
  etag: string;
  file_version?: {
    id: string;
    type: string;
    sha1: string;
  };
  created_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  modified_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  owned_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  shared_link?: {
    url: string;
    download_url: string;
    vanity_name?: string;
    is_password_enabled: boolean;
    unshared_at: string;
    download_count: number;
    preview_count: number;
    access: string;
    effective_access: string;
    permissions: {
      can_download: boolean;
      can_preview: boolean;
      can_upload: boolean;
    };
  };
  parent: {
    id: string;
    type: string;
    sequence_id: number;
    etag: string;
    name: string;
  };
  item_collection?: {
    total_count: number;
    entries: BoxFile[];
    offset: number;
    limit: number;
    order?: Array<{
      by: string;
      direction: string;
    }>;
  };
  path_collection?: {
    total_count: number;
    entries: Array<{
      id: string;
      type: string;
      name: string;
    }>;
  };
  permissions?: Array<{
    id: string;
    type: string;
    created_at: string;
    granted_to?: {
      id: string;
      type: string;
      name: string;
      login: string;
    };
    accessible_by?: {
      id: string;
      type: string;
      name: string;
      login: string;
    };
    role: string;
    granted_to_tag?: any;
  }>;
  tags?: Array<{
    id: string;
    type: string;
    name: string;
    url: string;
  }>;
  lock?: {
    id: string;
    type: string;
    created_at: string;
    locked_by: {
      id: string;
      type: string;
      name: string;
      login: string;
    };
    app_type?: string;
    expires_at?: string;
    is_prevent_unlock?: boolean;
  };
  retention?: {
    id: string;
    type: string;
    policy?: {
      id: string;
      type: string;
      name: string;
    };
    disposition_at?: string;
    can_extend?: boolean;
  };
  watermarked?: boolean;
  allowed_shared_link_access_levels?: string[];
  has_collaborations?: boolean;
  is_externally_owned?: boolean;
  can_non_owners_invite?: boolean;
  is_collaboration_restricted_to_enterprise?: boolean;
  collaborator_restriction?: {
    type: string;
    restriction_type: string;
    allowed_groups?: Array<{
      id: string;
      name: string;
    }>;
    allowed_users?: Array<{
      id: string;
      name: string;
    }>;
  };
  classification?: {
    name: string;
    definition: string;
    color: string;
  };
}

interface BoxFolder {
  id: string;
  type: string;
  name: string;
  created_at: string;
  modified_at: string;
  description?: string;
  size?: number;
  etag: string;
  folder_upload_email?: {
    access: string;
    email: string;
  };
  created_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  modified_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  owned_by?: {
    id: string;
    name: string;
    login: string;
    type: string;
  };
  shared_link?: {
    url: string;
    download_url: string;
    vanity_name?: string;
    is_password_enabled: boolean;
    unshared_at: string;
    download_count: number;
    preview_count: number;
    access: string;
    effective_access: string;
    permissions: {
      can_download: boolean;
      can_preview: boolean;
      can_upload: boolean;
    };
  };
  parent: {
    id: string;
    type: string;
    sequence_id: number;
    etag: string;
    name: string;
  };
  item_collection: {
    total_count: number;
    entries: (BoxFile | BoxFolder)[];
    offset: number;
    limit: number;
    order?: Array<{
      by: string;
      direction: string;
    }>;
  };
  path_collection: {
    total_count: number;
    entries: Array<{
      id: string;
      type: string;
      name: string;
    }>;
  };
  permissions?: Array<{
    id: string;
    type: string;
    created_at: string;
    granted_to?: {
      id: string;
      type: string;
      name: string;
      login: string;
    };
    accessible_by?: {
      id: string;
      type: string;
      name: string;
      login: string;
    };
    role: string;
    granted_to_tag?: any;
  }>;
  watermark_info?: {
    is_watermarked: boolean;
    created_at?: string;
  };
  can_non_owners_invite?: boolean;
  is_collaboration_restricted_to_enterprise?: boolean;
}

interface BoxUser {
  id: string;
  type: string;
  name: string;
  login: string;
  created_at: string;
  modified_at: string;
  language: string;
  timezone: string;
  space_amount: number;
  space_used: number;
  max_upload_size: number;
  status: string;
  job_title?: string;
  phone?: string;
  address?: string;
  avatar_url: string;
  notification_email?: {
    email: string;
    is_confirmed: boolean;
  };
}

interface BoxCollaboration {
  id: string;
  type: string;
  created_by?: {
    id: string;
    type: string;
    name: string;
    login: string;
  };
  created_at: string;
  modified_at: string;
  expires_at?: string;
  status: string;
  accessible_by?: {
    id: string;
    type: string;
    name: string;
    login?: string;
  };
  role: string;
  acknowledged_at?: string;
  item: {
    id: string;
    type: string;
    name: string;
  };
  invite_email?: string;
  can_view_path: boolean;
}

const BoxIntegration: React.FC = () => {
  const [files, setFiles] = useState<BoxFile[]>([]);
  const [folders, setFolders] = useState<BoxFolder[]>([]);
  const [users, setUsers] = useState<BoxUser[]>([]);
  const [collaborations, setCollaborations] = useState<BoxCollaboration[]>([]);
  const [userProfile, setUserProfile] = useState<BoxUser | null>(null);
  const [currentFolder, setCurrentFolder] = useState<BoxFolder | null>(null);
  const [path, setPath] = useState<BoxFolder[]>([]);
  const [loading, setLoading] = useState({
    files: false,
    folders: false,
    users: false,
    collaborations: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");

  // Form states
  const [folderForm, setFolderForm] = useState({
    name: "",
    description: "",
    parent_id: "",
  });

  const [shareForm, setShareForm] = useState({
    access: "collaborators",
    password: "",
    unshare_date: "",
    permissions: {
      can_download: true,
      can_preview: true,
      can_upload: false,
    },
  });

  const [collaborationForm, setCollaborationForm] = useState({
    item_id: "",
    accessible_by_id: "",
    accessible_by_type: "user",
    role: "editor",
    notify: true,
  });

  const {
    isOpen: isFolderOpen,
    onOpen: onFolderOpen,
    onClose: onFolderClose,
  } = useDisclosure();
  const {
    isOpen: isShareOpen,
    onOpen: onShareOpen,
    onClose: onShareClose,
  } = useDisclosure();
  const {
    isOpen: isCollaborationOpen,
    onOpen: onCollaborationOpen,
    onClose: onCollaborationClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/box/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadRootFolder();
        loadUsers();
        loadCollaborations();
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

  // Load Box data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/box/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUserProfile(data.data?.profile || null);
      }
    } catch (error) {
      console.error("Failed to load user profile:", error);
    } finally {
      setLoading((prev) => ({ ...prev, profile: false }));
    }
  };

  const loadRootFolder = async () => {
    setLoading((prev) => ({ ...prev, folders: true, files: true }));
    try {
      const response = await fetch("/api/integrations/box/folder/0", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const folder = data.data?.folder;
        if (folder) {
          setCurrentFolder(folder);
          setPath([folder]);
          const entries = folder.item_collection?.entries || [];
          const folderEntries = entries.filter(
            (e: BoxFile | BoxFolder) => e.type === "folder",
          ) as BoxFolder[];
          const fileEntries = entries.filter(
            (e: BoxFile | BoxFolder) => e.type === "file",
          ) as BoxFile[];
          setFolders(folderEntries);
          setFiles(fileEntries);
        }
      }
    } catch (error) {
      console.error("Failed to load root folder:", error);
      toast({
        title: "Error",
        description: "Failed to load files from Box",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, folders: false, files: false }));
    }
  };

  const loadFolder = async (folder: BoxFolder) => {
    setLoading((prev) => ({ ...prev, folders: true, files: true }));
    try {
      const response = await fetch(
        `/api/integrations/box/folder/${folder.id}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            limit: 100,
          }),
        },
      );

      if (response.ok) {
        const data = await response.json();
        const loadedFolder = data.data?.folder;
        if (loadedFolder) {
          setCurrentFolder(loadedFolder);
          setPath((prev) => {
            const folderIndex = prev.findIndex((f) => f.id === folder.id);
            if (folderIndex !== -1) {
              return prev.slice(0, folderIndex + 1);
            } else {
              return [...prev, loadedFolder];
            }
          });
          const entries = loadedFolder.item_collection?.entries || [];
          const folderEntries = entries.filter(
            (e: BoxFile | BoxFolder) => e.type === "folder",
          ) as BoxFolder[];
          const fileEntries = entries.filter(
            (e: BoxFile | BoxFolder) => e.type === "file",
          ) as BoxFile[];
          setFolders(folderEntries);
          setFiles(fileEntries);
        }
      }
    } catch (error) {
      console.error("Failed to load folder:", error);
    } finally {
      setLoading((prev) => ({ ...prev, folders: false, files: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/box/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
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

  const loadCollaborations = async () => {
    setLoading((prev) => ({ ...prev, collaborations: true }));
    try {
      const response = await fetch("/api/integrations/box/collaborations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCollaborations(data.data?.collaborations || []);
      }
    } catch (error) {
      console.error("Failed to load collaborations:", error);
    } finally {
      setLoading((prev) => ({ ...prev, collaborations: false }));
    }
  };

  const createFolder = async () => {
    if (!folderForm.name) return;

    try {
      const response = await fetch("/api/integrations/box/folders/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          name: folderForm.name,
          description: folderForm.description,
          parent: {
            id: folderForm.parent_id || currentFolder?.id || "0",
            type: "folder",
          },
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Folder created successfully",
          status: "success",
          duration: 3000,
        });
        onFolderClose();
        setFolderForm({ name: "", description: "", parent_id: "" });
        if (currentFolder) {
          loadFolder(currentFolder);
        } else {
          loadRootFolder();
        }
      }
    } catch (error) {
      console.error("Failed to create folder:", error);
      toast({
        title: "Error",
        description: "Failed to create folder",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createSharedLink = async (item: BoxFile | BoxFolder) => {
    try {
      const response = await fetch(
        `/api/integrations/box/${item.type}s/${item.id}/share`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            access: shareForm.access,
            password: shareForm.password || undefined,
            unshare_date: shareForm.unshare_date || undefined,
            permissions: shareForm.permissions,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: `${item.type} shared successfully`,
          status: "success",
          duration: 3000,
        });
        onShareClose();
        setShareForm({
          access: "collaborators",
          password: "",
          unshare_date: "",
          permissions: {
            can_download: true,
            can_preview: true,
            can_upload: false,
          },
        });
        if (currentFolder) {
          loadFolder(currentFolder);
        } else {
          loadRootFolder();
        }
      }
    } catch (error) {
      console.error("Failed to create shared link:", error);
      toast({
        title: "Error",
        description: "Failed to create shared link",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createCollaboration = async () => {
    if (!collaborationForm.item_id || !collaborationForm.accessible_by_id)
      return;

    try {
      const response = await fetch(
        "/api/integrations/box/collaborations/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            item: {
              id: collaborationForm.item_id,
              type: "folder",
            },
            accessible_by: {
              type: collaborationForm.accessible_by_type,
              id: collaborationForm.accessible_by_id,
            },
            role: collaborationForm.role,
            notify: collaborationForm.notify,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: "Collaboration created successfully",
          status: "success",
          duration: 3000,
        });
        onCollaborationClose();
        setCollaborationForm({
          item_id: "",
          accessible_by_id: "",
          accessible_by_type: "user",
          role: "editor",
          notify: true,
        });
        loadCollaborations();
      }
    } catch (error) {
      console.error("Failed to create collaboration:", error);
      toast({
        title: "Error",
        description: "Failed to create collaboration",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredFiles = files.filter(
    (file) =>
      file.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      (selectedType === "all" || selectedType === "files"),
  );

  const filteredFolders = folders.filter(
    (folder) =>
      folder.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      (selectedType === "all" || selectedType === "folders"),
  );

  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.login.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredCollaborations = collaborations.filter(
    (collab) =>
      collab.item?.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      collab.accessible_by?.name
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalFiles = files.length;
  const totalFolders = folders.length;
  const totalUsers = users.length;
  const totalCollaborations = collaborations.length;
  const sharedFiles = files.filter((f) => f.shared_link).length;
  const sharedFolders = folders.filter((f) => f.shared_link).length;
  const spaceUsed = userProfile?.space_used || 0;
  const spaceTotal = userProfile?.space_amount || 0;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadRootFolder();
      loadUsers();
      loadCollaborations();
    }
  }, [connected]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getFileIcon = (file: BoxFile): any => {
    if (file.name.endsWith(".pdf")) return FileIcon;
    if (file.name.endsWith(".doc") || file.name.endsWith(".docx"))
      return EditIcon;
    if (file.name.endsWith(".xls") || file.name.endsWith(".xlsx"))
      return ViewIcon;
    if (file.name.endsWith(".ppt") || file.name.endsWith(".pptx"))
      return ViewIcon;
    if (
      file.name.endsWith(".jpg") ||
      file.name.endsWith(".jpeg") ||
      file.name.endsWith(".png") ||
      file.name.endsWith(".gif")
    )
      return ViewIcon;
    if (
      file.name.endsWith(".zip") ||
      file.name.endsWith(".rar") ||
      file.name.endsWith(".7z")
    )
      return DownloadIcon;
    if (
      file.name.endsWith(".mp4") ||
      file.name.endsWith(".avi") ||
      file.name.endsWith(".mov")
    )
      return ViewIcon;
    if (
      file.name.endsWith(".mp3") ||
      file.name.endsWith(".wav") ||
      file.name.endsWith(".flac")
    )
      return ViewIcon;
    return FileIcon;
  };

  const getAccessColor = (access: string): string => {
    switch (access) {
      case "open":
        return "green";
      case "company":
        return "blue";
      case "collaborators":
        return "yellow";
      default:
        return "gray";
    }
  };

  const getRoleColor = (role: string): string => {
    switch (role) {
      case "owner":
        return "red";
      case "co-owner":
        return "orange";
      case "editor":
        return "yellow";
      case "viewer":
        return "blue";
      case "previewer":
        return "purple";
      case "uploader":
        return "teal";
      case "previewer uploader":
        return "pink";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case "active":
        return "green";
      case "inactive":
        return "gray";
      case "cannot_delete_edit":
        return "red";
      case "cannot_delete_edit_upload":
        return "orange";
      default:
        return "gray";
    }
  };

  const handleBreadcrumbClick = (folder: BoxFolder, index: number) => {
    if (index === path.length - 1) return; // Already in this folder
    if (index === 0 && path[0].id === "0") {
      loadRootFolder();
    } else {
      loadFolder(folder);
    }
  };

  return (
    <ChakraBox minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#0061D5" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Box Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Secure file storage and collaboration platform
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
                <WarningTwoIcon mr={1} />
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

          {userProfile && (
            <HStack spacing={4}>
              <Avatar src={userProfile.avatar_url} name={userProfile.name} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.name}</Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.login} • {formatFileSize(spaceUsed)} used
                </Text>
                <Progress
                  value={(spaceUsed / spaceTotal) * 100}
                  colorScheme={spaceUsed / spaceTotal > 0.9 ? "red" : "blue"}
                  size="sm"
                  width="200px"
                />
              </VStack>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SettingsIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Box</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Box account to start managing files and
                    collaboration
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/box/auth/start")
                  }
                >
                  Connect Box Account
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
                    <StatLabel>Files</StatLabel>
                    <StatNumber>{totalFiles}</StatNumber>
                    <StatHelpText>{sharedFiles} shared</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Folders</StatLabel>
                    <StatNumber>{totalFolders}</StatNumber>
                    <StatHelpText>{sharedFolders} shared</StatHelpText>
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
                    <StatLabel>Collaborations</StatLabel>
                    <StatNumber>{totalCollaborations}</StatNumber>
                    <StatHelpText>Active shares</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Files & Folders</Tab>
                <Tab>Collaborations</Tab>
                <Tab>Users</Tab>
                <Tab>Analytics</Tab>
              </TabList>

              <TabPanels>
                {/* Files & Folders Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {/* Breadcrumb Navigation */}
                    {path.length > 0 && (
                      <Breadcrumb>
                        {path.map((folder, index) => (
                          <BreadcrumbItem key={folder.id}>
                            <BreadcrumbLink
                              onClick={() =>
                                handleBreadcrumbClick(folder, index)
                              }
                              cursor="pointer"
                              color="blue.500"
                              _hover={{ color: "blue.600" }}
                            >
                              {folder.id === "0" ? "Root" : folder.name}
                            </BreadcrumbLink>
                          </BreadcrumbItem>
                        ))}
                      </Breadcrumb>
                    )}

                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by type"
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value)}
                        width="150px"
                      >
                        <option value="all">All</option>
                        <option value="files">Files</option>
                        <option value="folders">Folders</option>
                      </Select>
                      <Input
                        placeholder="Search files and folders..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={() => {
                          setFolderForm({
                            ...folderForm,
                            parent_id: currentFolder?.id || "",
                          });
                          onFolderOpen();
                        }}
                      >
                        Create Folder
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {/* Folders */}
                      {loading.folders ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredFolders.map((folder) => (
                          <Card key={folder.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon
                                  as={FolderIcon}
                                  w={8}
                                  h={8}
                                  color="#0061D5"
                                  cursor="pointer"
                                  onClick={() => loadFolder(folder)}
                                />
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Text
                                      fontWeight="bold"
                                      fontSize="lg"
                                      cursor="pointer"
                                      onClick={() => loadFolder(folder)}
                                      color="blue.600"
                                      _hover={{ color: "blue.700" }}
                                    >
                                      {folder.name}
                                    </Text>
                                    <HStack>
                                      {folder.shared_link && (
                                        <Tag
                                          colorScheme={getAccessColor(
                                            folder.shared_link.access,
                                          )}
                                          size="sm"
                                        >
                                          <LinkIcon mr={1} />
                                          Shared
                                        </Tag>
                                      )}
                                      <Menu>
                                        <MenuButton
                                          as={Button}
                                          size="sm"
                                          variant="outline"
                                        >
                                          Actions
                                        </MenuButton>
                                        <MenuList>
                                          <MenuItem
                                            icon={<ShareIcon />}
                                            onClick={() => {
                                              setShareForm({
                                                ...shareForm,
                                                access:
                                                  folder.shared_link?.access ||
                                                  "collaborators",
                                              });
                                              onShareOpen();
                                            }}
                                          >
                                            Share
                                          </MenuItem>
                                          <MenuItem
                                            icon={<UsersIcon />}
                                            onClick={() => {
                                              setCollaborationForm({
                                                ...collaborationForm,
                                                item_id: folder.id,
                                              });
                                              onCollaborationOpen();
                                            }}
                                          >
                                            Add Collaboration
                                          </MenuItem>
                                          <MenuItem icon={<EditIcon />}>
                                            Rename
                                          </MenuItem>
                                          <MenuItem icon={<DeleteIcon />}>
                                            Delete
                                          </MenuItem>
                                        </MenuList>
                                      </Menu>
                                    </HStack>
                                  </HStack>

                                  {folder.description && (
                                    <Text fontSize="sm" color="gray.600">
                                      {folder.description}
                                    </Text>
                                  )}

                                  <HStack spacing={4}>
                                    <Text fontSize="xs" color="gray.500">
                                      Modified: {formatDate(folder.modified_at)}
                                    </Text>
                                    {folder.item_collection?.total_count !==
                                      undefined && (
                                      <Text fontSize="xs" color="gray.500">
                                        {folder.item_collection.total_count}{" "}
                                        items
                                      </Text>
                                    )}
                                  </HStack>

                                  {folder.created_by && (
                                    <HStack spacing={2}>
                                      <Text fontSize="xs" color="gray.500">
                                        Created by:
                                      </Text>
                                      <Text fontSize="xs" fontWeight="medium">
                                        {folder.created_by.name}
                                      </Text>
                                    </HStack>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}

                      {/* Files */}
                      {loading.files ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredFiles.map((file) => (
                          <Card key={file.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon
                                  as={getFileIcon(file)}
                                  w={8}
                                  h={8}
                                  color="#0061D5"
                                />
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Link
                                      href={file.shared_link?.url || ""}
                                      isExternal
                                    >
                                      <Text fontWeight="bold" fontSize="lg">
                                        {file.name}
                                      </Text>
                                    </Link>
                                    <HStack>
                                      {file.size && (
                                        <Tag size="sm">
                                          {formatFileSize(file.size)}
                                        </Tag>
                                      )}
                                      {file.shared_link && (
                                        <Tag
                                          colorScheme={getAccessColor(
                                            file.shared_link.access,
                                          )}
                                          size="sm"
                                        >
                                          <LinkIcon mr={1} />
                                          Shared
                                        </Tag>
                                      )}
                                      {file.lock && (
                                        <Tag colorScheme="orange" size="sm">
                                          <LockIcon mr={1} />
                                          Locked
                                        </Tag>
                                      )}
                                      <Menu>
                                        <MenuButton
                                          as={Button}
                                          size="sm"
                                          variant="outline"
                                        >
                                          Actions
                                        </MenuButton>
                                        <MenuList>
                                          <MenuItem icon={<DownloadIcon />}>
                                            Download
                                          </MenuItem>
                                          <MenuItem
                                            icon={<ShareIcon />}
                                            onClick={() => {
                                              setShareForm({
                                                ...shareForm,
                                                access:
                                                  file.shared_link?.access ||
                                                  "collaborators",
                                              });
                                              onShareOpen();
                                            }}
                                          >
                                            Share
                                          </MenuItem>
                                          <MenuItem icon={<EditIcon />}>
                                            Rename
                                          </MenuItem>
                                          <MenuItem icon={<DeleteIcon />}>
                                            Delete
                                          </MenuItem>
                                        </MenuList>
                                      </Menu>
                                    </HStack>
                                  </HStack>

                                  {file.description && (
                                    <Text fontSize="sm" color="gray.600">
                                      {file.description}
                                    </Text>
                                  )}

                                  <HStack spacing={4}>
                                    <Text fontSize="xs" color="gray.500">
                                      Modified: {formatDate(file.modified_at)}
                                    </Text>
                                    {file.content_modified_at && (
                                      <Text fontSize="xs" color="gray.500">
                                        Content:{" "}
                                        {formatDate(file.content_modified_at)}
                                      </Text>
                                    )}
                                  </HStack>

                                  {file.created_by && (
                                    <HStack spacing={2}>
                                      <Text fontSize="xs" color="gray.500">
                                        Created by:
                                      </Text>
                                      <Text fontSize="xs" fontWeight="medium">
                                        {file.created_by.name}
                                      </Text>
                                    </HStack>
                                  )}

                                  {file.tags && file.tags.length > 0 && (
                                    <HStack wrap="wrap">
                                      {file.tags.map((tag) => (
                                        <Tag
                                          key={tag.id}
                                          size="sm"
                                          colorScheme="gray"
                                        >
                                          {tag.name}
                                        </Tag>
                                      ))}
                                    </HStack>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Collaborations Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search collaborations..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={() => {
                          setCollaborationForm({
                            ...collaborationForm,
                            item_id: currentFolder?.id || "",
                          });
                          onCollaborationOpen();
                        }}
                      >
                        Add Collaboration
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {loading.collaborations ? (
                            <Spinner size="xl" />
                          ) : (
                            filteredCollaborations.map((collab) => (
                              <Card key={collab.id}>
                                <CardBody>
                                  <HStack spacing={4} align="start">
                                    <Icon
                                      as={UsersIcon}
                                      w={6}
                                      h={6}
                                      color="#0061D5"
                                    />
                                    <VStack spacing={2} flex={1}>
                                      <HStack
                                        justify="space-between"
                                        width="100%"
                                      >
                                        <Text fontWeight="bold">
                                          {collab.item?.name || "Unknown Item"}
                                        </Text>
                                        <HStack>
                                          <Tag
                                            colorScheme={getRoleColor(
                                              collab.role,
                                            )}
                                            size="sm"
                                          >
                                            {collab.role}
                                          </Tag>
                                          <Tag
                                            colorScheme={getStatusColor(
                                              collab.status,
                                            )}
                                            size="sm"
                                          >
                                            {collab.status}
                                          </Tag>
                                        </HStack>
                                      </HStack>

                                      <HStack spacing={4}>
                                        <Text fontSize="sm" color="gray.600">
                                          Collaborator:{" "}
                                          {collab.accessible_by?.name ||
                                            collab.invite_email}
                                        </Text>
                                        {collab.accessible_by?.login && (
                                          <Text fontSize="xs" color="gray.500">
                                            ({collab.accessible_by.login})
                                          </Text>
                                        )}
                                      </HStack>

                                      <HStack spacing={4}>
                                        <Text fontSize="xs" color="gray.500">
                                          Created:{" "}
                                          {formatDate(collab.created_at)}
                                        </Text>
                                        {collab.expires_at && (
                                          <Text fontSize="xs" color="gray.500">
                                            Expires:{" "}
                                            {formatDate(collab.expires_at)}
                                          </Text>
                                        )}
                                      </HStack>

                                      {collab.created_by && (
                                        <Text fontSize="xs" color="gray.500">
                                          Created by: {collab.created_by.name}
                                        </Text>
                                      )}
                                    </VStack>
                                  </HStack>
                                </CardBody>
                              </Card>
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
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
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredUsers.map((user) => (
                          <Card key={user.id}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar
                                  src={user.avatar_url}
                                  name={user.name}
                                  size="lg"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{user.name}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {user.login}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Tag
                                      colorScheme={getStatusColor(user.status)}
                                      size="sm"
                                    >
                                      {user.status}
                                    </Tag>
                                  </HStack>
                                  {user.job_title && (
                                    <Text fontSize="xs" color="gray.500">
                                      {user.job_title}
                                    </Text>
                                  )}
                                  <Text fontSize="xs" color="gray.500">
                                    Storage: {formatFileSize(user.space_used)} /{" "}
                                    {formatFileSize(user.space_amount)}
                                  </Text>
                                  <Progress
                                    value={
                                      (user.space_used / user.space_amount) *
                                      100
                                    }
                                    colorScheme={
                                      user.space_used / user.space_amount > 0.9
                                        ? "red"
                                        : "blue"
                                    }
                                    size="sm"
                                    width="100%"
                                  />
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Analytics Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      <Card>
                        <CardBody>
                          <Stat>
                            <StatLabel>Storage Used</StatLabel>
                            <StatNumber>{formatFileSize(spaceUsed)}</StatNumber>
                            <StatHelpText>
                              of {formatFileSize(spaceTotal)}
                            </StatHelpText>
                          </Stat>
                          <Progress
                            value={(spaceUsed / spaceTotal) * 100}
                            colorScheme={
                              spaceUsed / spaceTotal > 0.9 ? "red" : "blue"
                            }
                            size="sm"
                            mt={4}
                          />
                        </CardBody>
                      </Card>

                      <Card>
                        <CardBody>
                          <Stat>
                            <StatLabel>Shared Items</StatLabel>
                            <StatNumber>
                              {sharedFiles + sharedFolders}
                            </StatNumber>
                            <StatHelpText>
                              {sharedFiles} files, {sharedFolders} folders
                            </StatHelpText>
                          </Stat>
                        </CardBody>
                      </Card>

                      <Card>
                        <CardBody>
                          <Stat>
                            <StatLabel>Active Collaborations</StatLabel>
                            <StatNumber>{totalCollaborations}</StatNumber>
                            <StatHelpText>Team collaborations</StatHelpText>
                          </Stat>
                        </CardBody>
                      </Card>
                    </SimpleGrid>

                    <Card>
                      <CardHeader>
                        <Heading size="md">Recent Activity</Heading>
                      </CardHeader>
                      <CardBody>
                        <Text color="gray.600">
                          Recent file uploads, modifications, and sharing
                          activities would be displayed here. This section would
                          show activity logs with timestamps for monitoring user
                          engagement.
                        </Text>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Folder Modal */}
            <Modal isOpen={isFolderOpen} onClose={onFolderClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Folder</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Folder Name</FormLabel>
                      <Input
                        placeholder="Enter folder name"
                        value={folderForm.name}
                        onChange={(e) =>
                          setFolderForm({
                            ...folderForm,
                            name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Folder description (optional)"
                        value={folderForm.description}
                        onChange={(e) =>
                          setFolderForm({
                            ...folderForm,
                            description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onFolderClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createFolder}
                    disabled={!folderForm.name}
                  >
                    Create Folder
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Share Modal */}
            <Modal isOpen={isShareOpen} onClose={onShareClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Shared Link</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl>
                      <FormLabel>Access Level</FormLabel>
                      <Select
                        value={shareForm.access}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            access: e.target.value,
                          })
                        }
                      >
                        <option value="open">Anyone with link</option>
                        <option value="company">People in company</option>
                        <option value="collaborators">People invited</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Password (optional)</FormLabel>
                      <Input
                        type="password"
                        placeholder="Enter password"
                        value={shareForm.password}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            password: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Unshare Date (optional)</FormLabel>
                      <Input
                        type="date"
                        value={shareForm.unshare_date}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            unshare_date: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <Text fontSize="sm" fontWeight="bold">
                      Permissions
                    </Text>
                    <HStack spacing={4}>
                      <Checkbox
                        isChecked={shareForm.permissions.can_download}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            permissions: {
                              ...shareForm.permissions,
                              can_download: e.target.checked,
                            },
                          })
                        }
                      >
                        Can download
                      </Checkbox>
                      <Checkbox
                        isChecked={shareForm.permissions.can_preview}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            permissions: {
                              ...shareForm.permissions,
                              can_preview: e.target.checked,
                            },
                          })
                        }
                      >
                        Can preview
                      </Checkbox>
                      <Checkbox
                        isChecked={shareForm.permissions.can_upload}
                        onChange={(e) =>
                          setShareForm({
                            ...shareForm,
                            permissions: {
                              ...shareForm.permissions,
                              can_upload: e.target.checked,
                            },
                          })
                        }
                      >
                        Can upload
                      </Checkbox>
                    </HStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onShareClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={() => {
                      // This would be called with the current item
                      // For now, just close the modal
                      onShareClose();
                    }}
                  >
                    Create Link
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Collaboration Modal */}
            <Modal
              isOpen={isCollaborationOpen}
              onClose={onCollaborationClose}
              size="lg"
            >
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Add Collaboration</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl>
                      <FormLabel>Collaborator</FormLabel>
                      <Select
                        value={collaborationForm.accessible_by_id}
                        onChange={(e) =>
                          setCollaborationForm({
                            ...collaborationForm,
                            accessible_by_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Select user</option>
                        {users.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.name} ({user.login})
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Role</FormLabel>
                      <Select
                        value={collaborationForm.role}
                        onChange={(e) =>
                          setCollaborationForm({
                            ...collaborationForm,
                            role: e.target.value,
                          })
                        }
                      >
                        <option value="editor">Editor</option>
                        <option value="viewer">Viewer</option>
                        <option value="previewer">Previewer</option>
                        <option value="uploader">Uploader</option>
                        <option value="previewer uploader">
                          Previewer Uploader
                        </option>
                        <option value="co-owner">Co-owner</option>
                        <option value="owner">Owner</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <Checkbox
                        isChecked={collaborationForm.notify}
                        onChange={(e) =>
                          setCollaborationForm({
                            ...collaborationForm,
                            notify: e.target.checked,
                          })
                        }
                      >
                        Send notification to collaborator
                      </Checkbox>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button
                    variant="outline"
                    mr={3}
                    onClick={onCollaborationClose}
                  >
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createCollaboration}
                    disabled={!collaborationForm.accessible_by_id}
                  >
                    Add Collaboration
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </ChakraBox>
  );
};

export default BoxIntegration;
