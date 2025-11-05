/**
 * VS Code Development UI Component
 * Complete VS Code development environment integration with file management
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  Button,
  IconButton,
  Avatar,
  AvatarBadge,
  Heading,
  Badge,
  Divider,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useToast,
  Spinner,
  Icon,
  Flex,
  ScrollArea,
  Tooltip,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Switch,
  Select,
  NumberInput,
  NumberInputField,
  CheckboxGroup,
  Checkbox,
  Stack,
  Progress,
  Card,
  CardBody,
  CardHeader,
  Image,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Tfoot,
  TableContainer,
  Code,
  Textarea,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  List,
  ListItem,
  ListIcon,
  Alert,
  AlertIcon,
  Tag,
  TagLabel,
  TagCloseButton,
  SimpleGrid,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Drawer,
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure
} from '@chakra-ui/react';
import {
  FiFile,
  FiFolder,
  FiFolderOpen,
  FiHome,
  FiSearch,
  FiPlus,
  FiEdit2,
  FiTrash2,
  FiDownload,
  FiUpload,
  FiSave,
  FiRefreshCw,
  FiGitBranch,
  FiGitCommit,
  FiGitPullRequest,
  FiSettings,
  FiZap,
  FiZapOff,
  FiActivity,
  FiHardDrive,
  FiCpu,
  FiCode,
  FiTerminal,
  FiDatabase,
  FiShield,
  FiUnlock,
  FiEye,
  FiEyeOff,
  FiClock,
  FiCheck,
  FiX,
  FiAlertTriangle,
  FiChevronDown,
  FiChevronRight,
  FiCopy,
  FiSlash,
  FiFileText,
  FiFilePlus,
  FiGrid,
  FiList,
  FiFilter,
  FiBarChart2,
  FiTrendingUp,
  FiPackage,
  FiTool,
  FiMonitor,
  FiMaximize,
  FiMinimize,
  FiMoreHorizontal,
  FiMoreVertical
} from 'react-icons/fi';

// Import VS Code skills
import { vscodeSkills, vscodeUtils } from './skills/vscodeSkillsComplete';

interface VSCodeFile {
  id: string;
  path: string;
  name: string;
  extension: string;
  size: number;
  created_at: string;
  modified_at: string;
  content: string;
  content_hash: string;
  language: string;
  encoding: string;
  line_count: number;
  char_count: number;
  metadata: any;
}

interface VSCodeProject {
  id: string;
  name: string;
  path: string;
  type: string;
  files: VSCodeFile[];
  folders: string[];
  settings: any;
  extensions: string[];
  git_info: any;
  build_system: string;
  language_stats: any;
  last_activity: string;
  created_at: string;
  updated_at: string;
  metadata: any;
}

interface VSCodeMemorySettings {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  data_retention_days: number;
  include_projects: string[];
  exclude_projects: string[];
  include_file_types: string[];
  exclude_file_types: string[];
  max_file_size_mb: number;
  max_files_per_project: number;
  include_hidden_files: boolean;
  include_binary_files: boolean;
  code_search_enabled: boolean;
  semantic_search_enabled: boolean;
  metadata_extraction_enabled: boolean;
  activity_logging_enabled: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  sync_in_progress: boolean;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}

interface VSCodeSyncStatus {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  sync_in_progress: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  should_sync_now: boolean;
  error_message?: string;
  stats: {
    total_projects_ingested: number;
    total_files_ingested: number;
    total_activities_ingested: number;
    total_size_mb: number;
    failed_ingestions: number;
    last_ingestion_timestamp?: string;
    avg_files_per_project: number;
    avg_processing_time_ms: number;
  };
  settings: {
    include_projects: string[];
    exclude_projects: string[];
    include_file_types: string[];
    exclude_file_types: string[];
    max_file_size_mb: number;
    max_files_per_project: number;
    include_hidden_files: boolean;
    include_binary_files: boolean;
    code_search_enabled: boolean;
    semantic_search_enabled: boolean;
    metadata_extraction_enabled: boolean;
    activity_logging_enabled: boolean;
  };
}

interface VSCodeExtension {
  id: string;
  name: string;
  publisher: any;
  description: string;
  version: string;
  category: string;
  tags: string[];
  release_date: string;
  last_updated: string;
  download_count: number;
  rating: number;
  is_pre_release: boolean;
  dependencies: string[];
  contributes: any;
  metadata: any;
}

interface VSCodeDevelopmentUIProps {
  userId: string;
  className?: string;
  height?: string | number;
  showMemoryControls?: boolean;
  enableRealtimeSync?: boolean;
  defaultWorkspacePath?: string;
  onProjectChange?: (project: VSCodeProject) => void;
  onFileChange?: (file: VSCodeFile) => void;
  onSettingsChange?: (settings: VSCodeMemorySettings) => void;
}

const VSCodeDevelopmentUI: React.FC<VSCodeDevelopmentUIProps> = ({
  userId,
  className = '',
  height = '800px',
  showMemoryControls = true,
  enableRealtimeSync = true,
  defaultWorkspacePath = '',
  onProjectChange,
  onFileChange,
  onSettingsChange
}) => {
  const toast = useToast();
  const { isOpen: settingsOpen, onOpen: settingsOnOpen, onClose: settingsOnClose } = useDisclosure();
  const { isOpen: fileOpen, onOpen: fileOnOpen, onClose: fileOnClose } = useDisclosure();
  const { isOpen: searchOpen, onOpen: searchOnOpen, onClose: searchOnClose } = useDisclosure();
  const { isOpen: extensionsOpen, onOpen: extensionsOnOpen, onClose: extensionsOnClose } = useDisclosure();

  // State management
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [projects, setProjects] = useState<VSCodeProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<VSCodeProject | null>(null);
  const [selectedFile, setSelectedFile] = useState<VSCodeFile | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [workspacePath, setWorkspacePath] = useState(defaultWorkspacePath);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<VSCodeFile[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'tree' | 'list'>('tree');
  const [showHiddenFiles, setShowHiddenFiles] = useState(false);
  const [sortBy, setSortBy] = useState<'name' | 'size' | 'modified'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [realtimeEnabled, setRealtimeEnabled] = useState(enableRealtimeSync);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  
  // Memory management state
  const [memorySettings, setMemorySettings] = useState<VSCodeMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<VSCodeSyncStatus | null>(null);
  const [tempSettings, setTempSettings] = useState<VSCodeMemorySettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  
  // Extensions state
  const [extensions, setExtensions] = useState<VSCodeExtension[]>([]);
  const [recommendations, setRecommendations] = useState<VSCodeExtension[]>([]);
  const [extensionSearchQuery, setExtensionSearchQuery] = useState('');

  // Fetch functions
  const fetchWorkspaceInfo = useCallback(async (path: string) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/vscode/development/workspace/info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: path
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const project = VSCodeProject.from_dict(data.workspace);
        setProjects([project]);
        setSelectedProject(project);
        setConnected(true);
        onProjectChange?.(project);
        
        toast({
          title: 'Workspace Connected',
          description: `Connected to ${project.name}`,
          status: 'success',
          duration: 3000,
        });
      } else {
        setConnected(false);
        toast({
          title: 'Workspace Connection Failed',
          description: data.error || 'Failed to connect to workspace',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching workspace info:', error);
      setConnected(false);
      toast({
        title: 'Connection Error',
        description: 'Failed to connect to workspace',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, onProjectChange, toast]);

  const fetchMemorySettings = useCallback(async () => {
    try {
      const response = await fetch('/api/vscode/development/memory/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setMemorySettings(data.settings);
        setTempSettings(data.settings);
        onSettingsChange?.(data.settings);
      }
    } catch (error) {
      console.error('Error fetching VS Code memory settings:', error);
    }
  }, [userId, onSettingsChange]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/vscode/development/memory/status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSyncStatus(data.memory_status);
      }
    } catch (error) {
      console.error('Error fetching VS Code sync status:', error);
    }
  }, [userId]);

  const fetchFileContent = useCallback(async (project: VSCodeProject, file: VSCodeFile) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/vscode/development/files/content', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: project.path,
          file_path: file.path
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setFileContent(data.file.content);
        setSelectedFile(file);
        onFileChange?.(file);
      } else {
        toast({
          title: 'File Read Error',
          description: data.error || 'Failed to read file',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error fetching file content:', error);
      toast({
        title: 'File Error',
        description: 'Failed to read file',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, onFileChange, toast]);

  const searchWorkspace = useCallback(async (query: string) => {
    if (!query.trim() || !selectedProject) return;
    
    try {
      const response = await fetch('/api/vscode/development/workspace/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: selectedProject.path,
          search_query: query,
          include_content: true
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSearchResults(data.results.map((result: any) => VSCodeFile.from_dict(result)));
      }
    } catch (error) {
      console.error('Error searching workspace:', error);
      toast({
        title: 'Search Error',
        description: 'Failed to search workspace',
        status: 'error',
      });
    }
  }, [userId, selectedProject, toast]);

  const fetchExtensions = useCallback(async (query: string = '') => {
    try {
      const response = await fetch('/api/vscode/development/extensions/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query,
          page_size: 20
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setExtensions(data.extensions.map((ext: any) => VSCodeExtension.from_dict(ext)));
      }
    } catch (error) {
      console.error('Error fetching extensions:', error);
    }
  }, []);

  const fetchRecommendations = useCallback(async () => {
    if (!selectedProject) return;
    
    try {
      const response = await fetch('/api/vscode/development/extensions/recommendations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          project_path: selectedProject.path
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setRecommendations(data.recommendations.map((ext: any) => VSCodeExtension.from_dict(ext)));
      }
    } catch (error) {
      console.error('Error fetching recommendations:', error);
    }
  }, [selectedProject]);

  // File operations
  const saveFile = useCallback(async (project: VSCodeProject, file: VSCodeFile, content: string) => {
    try {
      const response = await fetch('/api/vscode/development/files/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: project.path,
          file_path: file.path,
          content: content
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        toast({
          title: 'File Saved',
          description: `${file.name} saved successfully`,
          status: 'success',
        });
        
        // Refresh file content
        setFileContent(content);
      } else {
        toast({
          title: 'Save Failed',
          description: data.error || 'Failed to save file',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error saving file:', error);
      toast({
        title: 'Save Error',
        description: 'Failed to save file',
        status: 'error',
      });
    }
  }, [userId, toast]);

  const createFile = useCallback(async (project: VSCodeProject, filePath: string, content: string = '') => {
    try {
      const response = await fetch('/api/vscode/development/files/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: project.path,
          file_path: filePath,
          content: content
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        toast({
          title: 'File Created',
          description: `${filePath} created successfully`,
          status: 'success',
        });
        
        // Refresh workspace
        await fetchWorkspaceInfo(project.path);
      } else {
        toast({
          title: 'Create Failed',
          description: data.error || 'Failed to create file',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error creating file:', error);
      toast({
        title: 'Create Error',
        description: 'Failed to create file',
        status: 'error',
      });
    }
  }, [userId, fetchWorkspaceInfo, toast]);

  const deleteFile = useCallback(async (project: VSCodeProject, file: VSCodeFile) => {
    if (!window.confirm(`Are you sure you want to delete ${file.name}?`)) {
      return;
    }
    
    try {
      const response = await fetch('/api/vscode/development/files/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          workspace_path: project.path,
          file_path: file.path
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        toast({
          title: 'File Deleted',
          description: `${file.name} deleted successfully`,
          status: 'success',
        });
        
        // Clear selected file
        if (selectedFile?.id === file.id) {
          setSelectedFile(null);
          setFileContent('');
        }
        
        // Refresh workspace
        await fetchWorkspaceInfo(project.path);
      } else {
        toast({
          title: 'Delete Failed',
          description: data.error || 'Failed to delete file',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error deleting file:', error);
      toast({
        title: 'Delete Error',
        description: 'Failed to delete file',
        status: 'error',
      });
    }
  }, [userId, selectedFile, fetchWorkspaceInfo, toast]);

  // Memory management
  const startIngestion = useCallback(async (forceSync: boolean = false) => {
    if (!selectedProject) return;
    
    try {
      setSyncInProgress(true);
      setSyncResult(null);
      
      const response = await fetch('/api/vscode/development/memory/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          project_path: selectedProject.path,
          force_sync: forceSync
        }),
      });

      const data = await response.json();
      
      setSyncResult(data);
      
      if (data.ok) {
        // Refresh sync status
        await fetchSyncStatus();
        
        toast({
          title: 'Ingestion Complete',
          description: `Ingested ${data.ingestion_result?.files_ingested || 0} files from ${data.ingestion_result?.project_ingested || 'project'}`,
          status: 'success',
          duration: 5000,
        });
      } else {
        toast({
          title: 'Ingestion Failed',
          description: data.error || 'Failed to ingest project data',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error starting ingestion:', error);
      toast({
        title: 'Ingestion Error',
        description: 'Failed to start project ingestion',
        status: 'error',
      });
    } finally {
      setSyncInProgress(false);
    }
  }, [userId, selectedProject, fetchSyncStatus, toast]);

  const updateMemorySettings = useCallback(async (newSettings: VSCodeMemorySettings) => {
    try {
      const response = await fetch('/api/vscode/development/memory/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          ...newSettings
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setMemorySettings(prev => ({ ...prev, ...newSettings }));
        setTempSettings(prev => ({ ...prev, ...newSettings }));
        setHasChanges(false);
        onSettingsChange?.(newSettings);
        
        toast({
          title: 'Settings Updated',
          description: 'VS Code memory settings saved successfully',
          status: 'success',
        });
      }
    } catch (error) {
      console.error('Error updating VS Code settings:', error);
      toast({
        title: 'Settings Error',
        description: 'Failed to update VS Code settings',
        status: 'error',
      });
    }
  }, [userId, onSettingsChange, toast]);

  // File tree management
  const toggleFolder = useCallback((folderPath: string) => {
    setExpandedFolders(prev => {
      const newSet = new Set(prev);
      if (newSet.has(folderPath)) {
        newSet.delete(folderPath);
      } else {
        newSet.add(folderPath);
      }
      return newSet;
    });
  }, []);

  // File sorting
  const sortFiles = useCallback((files: VSCodeFile[]) => {
    return files.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'size':
          comparison = a.size - b.size;
          break;
        case 'modified':
          comparison = new Date(a.modified_at).getTime() - new Date(b.modified_at).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [sortBy, sortOrder]);

  // Effects
  useEffect(() => {
    if (workspacePath) {
      fetchWorkspaceInfo(workspacePath);
    }
  }, [workspacePath, fetchWorkspaceInfo]);

  useEffect(() => {
    if (userId) {
      fetchMemorySettings();
      fetchSyncStatus();
      fetchRecommendations();
    }
  }, [userId, fetchMemorySettings, fetchSyncStatus, fetchRecommendations]);

  // Auto-refresh sync status
  useEffect(() => {
    if (!showMemoryControls) return;
    
    const interval = setInterval(() => {
      fetchSyncStatus();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, [fetchSyncStatus, showMemoryControls]);

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery) {
        searchWorkspace(searchQuery);
      } else {
        setSearchResults([]);
      }
    }, 300);
    
    return () => clearTimeout(timeoutId);
  }, [searchQuery, searchWorkspace]);

  // Memoized file tree
  const fileTree = useMemo(() => {
    if (!selectedProject) return [];
    
    // Create file tree structure
    const tree: any[] = [];
    const folders: { [key: string]: any[] } = {};
    
    // Sort files
    const sortedFiles = sortFiles(selectedProject.files || []);
    
    // Build tree
    sortedFiles.forEach(file => {
      const parts = file.path.split('/');
      let currentPath = '';
      let currentLevel = tree;
      
      // Build folder structure
      for (let i = 0; i < parts.length - 1; i++) {
        currentPath += (currentPath ? '/' : '') + parts[i];
        
        if (!folders[currentPath]) {
          folders[currentPath] = [];
          currentLevel.push({
            name: parts[i],
            path: currentPath,
            type: 'folder',
            children: folders[currentPath],
            expanded: expandedFolders.has(currentPath)
          });
        }
        
        currentLevel = folders[currentPath];
      }
      
      // Add file to current level
      currentLevel.push({
        ...file,
        type: 'file'
      });
    });
    
    return tree;
  }, [selectedProject, sortFiles, expandedFolders]);

  // Memoized search results
  const filteredSearchResults = useMemo(() => {
    return searchResults.filter(file => 
      showHiddenFiles || !file.name.startsWith('.')
    );
  }, [searchResults, showHiddenFiles]);

  return (
    <Box className={className} height={height} display="flex" borderWidth={1} borderRadius="lg" overflow="hidden">
      <VStack flex={1} spacing={0} align="stretch">
        {/* Header */}
        <HStack 
          p={4} 
          borderBottomWidth={1} 
          bg="vscode.dark.50" 
          justify="space-between"
        >
          <HStack spacing={3} flex={1}>
            <Icon as={FiCode} boxSize={5} color="vscode.500" />
            <VStack spacing={0} align="start" flex={1}>
              <HStack spacing={2}>
                <Text fontWeight="bold">VS Code Development</Text>
                <Badge colorScheme="vscode">Development</Badge>
                {realtimeEnabled && (
                  <Badge colorScheme="green" variant="outline">
                    <Icon as={FiZap} boxSize={3} mr={1} />
                    Live
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="gray.500">
                {selectedProject ? selectedProject.name : 'No workspace selected'} › {selectedFile ? selectedFile.name : 'No file selected'}
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            {showMemoryControls && (
              <>
                <Tooltip label="Memory Settings">
                  <IconButton 
                    icon={<FiSettings />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => settingsOnOpen()}
                  />
                </Tooltip>
                
                <Tooltip label={`Last sync: ${syncStatus?.stats.last_ingestion_timestamp ? vscodeUtils.formatDateTime(syncStatus.stats.last_ingestion_timestamp) : 'Never'}`}>
                  <IconButton 
                    icon={<FiDatabase />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => startIngestion(false)}
                    isLoading={syncInProgress}
                  />
                </Tooltip>
              </>
            )}
            
            <Tooltip label="Extensions">
              <IconButton 
                icon={<FiPackage />} 
                variant="ghost" 
                size="sm"
                onClick={() => {
                  fetchExtensions();
                  extensionsOnOpen();
                }}
              />
            </Tooltip>
            
            <Tooltip label={realtimeEnabled ? 'Disable Real-time' : 'Enable Real-time'}>
              <IconButton 
                icon={realtimeEnabled ? <FiZap /> : <FiZapOff />} 
                variant="ghost" 
                size="sm"
                onClick={() => setRealtimeEnabled(!realtimeEnabled)}
                colorScheme={realtimeEnabled ? 'green' : 'gray'}
              />
            </Tooltip>
          </HStack>
        </HStack>

        {/* Workspace Path Input */}
        <HStack p={3} borderBottomWidth={1} bg="gray.50">
          <Input
            placeholder="Workspace path (e.g., /path/to/project)"
            value={workspacePath}
            onChange={(e) => setWorkspacePath(e.target.value)}
            size="sm"
            flex={1}
          />
          
          <Button
            size="sm"
            colorScheme="vscode"
            onClick={() => workspacePath && fetchWorkspaceInfo(workspacePath)}
            isLoading={loading}
            leftIcon={<FiHome />}
          >
            Connect
          </Button>
          
          <Divider orientation="vertical" h={6} />
          
          <Input
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
            maxW="200px"
            leftIcon={<FiSearch />}
          />
          
          <Button
            size="sm"
            variant="outline"
            onClick={() => searchOnOpen()}
            isDisabled={!searchQuery.trim()}
            leftIcon={<FiFilter />}
          >
            Filters
          </Button>
        </HStack>

        <HStack flex={1} spacing={0} align="stretch">
          {/* File Explorer */}
          <VStack 
            flex={1} 
            maxW="300px" 
            spacing={0} 
            align="stretch"
            borderRightWidth={1}
            bg="gray.50"
          >
            <HStack p={3} borderBottomWidth={1} bg="vscode.light.100">
              <Text fontWeight="medium" fontSize="sm">Explorer</Text>
              <Box flex={1} />
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setViewMode(viewMode === 'tree' ? 'list' : 'tree')}
                leftIcon={viewMode === 'tree' ? <FiList /> : <FiGrid />}
              />
            </HStack>
            
            <ScrollArea flex={1}>
              <VStack spacing={0} align="stretch" p={2}>
                {connected && selectedProject ? (
                  <>
                    {/* Project Info */}
                    <HStack 
                      p={2} 
                      bg="vscode.light.200" 
                      borderRadius="md"
                      cursor="pointer"
                      onClick={() => toggleFolder('')}
                    >
                      <Icon as={expandedFolders.has('') ? FiFolderOpen : FiFolder} />
                      <Text fontSize="sm" fontWeight="medium">{selectedProject.name}</Text>
                      <Badge size="xs" colorScheme="vscode">
                        {selectedProject.files?.length || 0} files
                      </Badge>
                    </HStack>
                    
                    {/* File Tree */}
                    {fileTree.map((item, index) => (
                      <FileTreeItem
                        key={`${item.path || item.id}-${index}`}
                        item={item}
                        level={0}
                        expanded={expandedFolders.has(item.path)}
                        selected={selectedFile?.id === item.id}
                        onSelect={() => {
                          if (item.type === 'file') {
                            fetchFileContent(selectedProject, item);
                          }
                        }}
                        onToggle={() => toggleFolder(item.path)}
                        onRename={(newName) => {
                          // Implementation for renaming
                        }}
                        onDelete={() => {
                          if (item.type === 'file') {
                            deleteFile(selectedProject, item);
                          }
                        }}
                        showHidden={showHiddenFiles}
                      />
                    ))}
                  </>
                ) : (
                  <VStack spacing={4} align="center" py={8}>
                    <Icon as={FiFolder} boxSize={8} color="gray.400" />
                    <Text color="gray.500" textAlign="center">
                      {workspacePath ? 'Connect to workspace' : 'Enter workspace path'}
                    </Text>
                  </VStack>
                )}
              </VStack>
            </ScrollArea>
            
            {/* Explorer Footer */}
            <HStack p={2} borderTopWidth={1} bg="vscode.light.100">
              <Checkbox
                size="sm"
                isChecked={showHiddenFiles}
                onChange={(e) => setShowHiddenFiles(e.target.checked)}
              >
                Show Hidden
              </Checkbox>
              
              <Menu>
                <MenuButton as={Button} variant="ghost" size="sm" rightIcon={<FiChevronDown />}>
                  Sort: {sortBy}
                </MenuButton>
                <MenuList>
                  <MenuItem onClick={() => setSortBy('name')}>Name</MenuItem>
                  <MenuItem onClick={() => setSortBy('size')}>Size</MenuItem>
                  <MenuItem onClick={() => setSortBy('modified')}>Modified</MenuItem>
                  <Divider />
                  <MenuItem onClick={() => setSortOrder('asc')}>Ascending</MenuItem>
                  <MenuItem onClick={() => setSortOrder('desc')}>Descending</MenuItem>
                </MenuList>
              </Menu>
            </HStack>
          </VStack>

          {/* File Editor */}
          <VStack flex={1} spacing={0} align="stretch">
            {selectedFile ? (
              <>
                {/* Editor Header */}
                <HStack 
                  p={3} 
                  borderBottomWidth={1} 
                  bg="vscode.light.100"
                  justify="space-between"
                >
                  <HStack spacing={3}>
                    <Icon as={FiFileText} boxSize={4} />
                    <Text fontWeight="medium" fontSize="sm">{selectedFile.name}</Text>
                    <Badge size="xs" colorScheme={vscodeUtils.getLanguageColor(selectedFile.language)}>
                      {selectedFile.language}
                    </Badge>
                    <Text fontSize="xs" color="gray.500">
                      {selectedFile.size.toLocaleString()} bytes
                    </Text>
                  </HStack>
                  
                  <HStack spacing={1}>
                    <IconButton
                      icon={<FiSave />}
                      variant="ghost"
                      size="sm"
                      onClick={() => saveFile(selectedProject, selectedFile, fileContent)}
                    />
                    <IconButton
                      icon={<FiDownload />}
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        // Implementation for download
                      }}
                    />
                    <IconButton
                      icon={<FiTrash2 />}
                      variant="ghost"
                      size="sm"
                      colorScheme="red"
                      onClick={() => deleteFile(selectedProject, selectedFile)}
                    />
                  </HStack>
                </HStack>
                
                {/* Editor Content */}
                <ScrollArea flex={1}>
                  <Textarea
                    value={fileContent}
                    onChange={(e) => setFileContent(e.target.value)}
                    placeholder={`Edit ${selectedFile.name}...`}
                    fontFamily="mono"
                    fontSize="sm"
                    variant="unstyled"
                    h="100%"
                    p={4}
                    resize="none"
                  />
                </ScrollArea>
                
                {/* Editor Footer */}
                <HStack 
                  p={2} 
                  borderTopWidth={1} 
                  bg="vscode.light.100"
                  justify="space-between"
                >
                  <Text fontSize="xs" color="gray.500">
                    Lines: {selectedFile.line_count} | Characters: {selectedFile.char_count}
                  </Text>
                  
                  <Text fontSize="xs" color="gray.500">
                    Encoding: {selectedFile.encoding} | Modified: {vscodeUtils.formatDateTime(selectedFile.modified_at)}
                  </Text>
                </HStack>
              </>
            ) : (
              <VStack flex={1} justify="center" align="center" spacing={4}>
                <Icon as={FiFile} boxSize={12} color="gray.400" />
                <Text color="gray.500" fontSize="lg">
                  No file selected
                </Text>
                <Text color="gray.400" fontSize="sm">
                  Select a file from the explorer to edit
                </Text>
              </VStack>
            )}
          </VStack>
        </HStack>
      </VStack>

      {/* Memory Settings Modal */}
      <Modal 
        isOpen={settingsOpen} 
        onClose={settingsOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiDatabase} />
              <Text>VS Code Memory Settings</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {tempSettings && (
              <VStack spacing={6} align="stretch">
                {/* General Settings */}
                <Accordion allowToggle defaultIndex={[0]}>
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">General Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-ingestion-enabled">
                            Enable Development Memory
                          </FormLabel>
                          <Switch
                            id="modal-ingestion-enabled"
                            isChecked={tempSettings.ingestion_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, ingestion_enabled: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Sync Frequency</FormLabel>
                          <Select
                            value={tempSettings.sync_frequency}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, sync_frequency: e.target.value }))}
                          >
                            <option value="real-time">Real-time</option>
                            <option value="hourly">Hourly</option>
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="manual">Manual</option>
                          </Select>
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Data Retention (Days)</FormLabel>
                          <NumberInput
                            value={tempSettings.data_retention_days}
                            min={1}
                            max={3650}
                            onChange={(value) => setTempSettings(prev => ({ ...prev, data_retention_days: parseInt(value) || 365 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* File Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">File Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-include-hidden">
                            Include Hidden Files
                          </FormLabel>
                          <Switch
                            id="modal-include-hidden"
                            isChecked={tempSettings.include_hidden_files}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_hidden_files: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-include-binary">
                            Include Binary Files
                          </FormLabel>
                          <Switch
                            id="modal-include-binary"
                            isChecked={tempSettings.include_binary_files}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_binary_files: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max File Size (MB)</FormLabel>
                          <NumberInput
                            value={tempSettings.max_file_size_mb}
                            min={1}
                            max={1000}
                            onChange={(value) => setTempSettings(prev => ({ ...prev, max_file_size_mb: parseInt(value) || 10 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Files per Project</FormLabel>
                          <NumberInput
                            value={tempSettings.max_files_per_project}
                            min={100}
                            max={100000}
                            onChange={(value) => setTempSettings(prev => ({ ...prev, max_files_per_project: parseInt(value) || 10000 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Search Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Search Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-code-search">
                            Enable Code Search
                          </FormLabel>
                          <Switch
                            id="modal-code-search"
                            isChecked={tempSettings.code_search_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, code_search_enabled: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-semantic-search">
                            Enable Semantic Search
                          </FormLabel>
                          <Switch
                            id="modal-semantic-search"
                            isChecked={tempSettings.semantic_search_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, semantic_search_enabled: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-metadata-extraction">
                            Enable Metadata Extraction
                          </FormLabel>
                          <Switch
                            id="modal-metadata-extraction"
                            isChecked={tempSettings.metadata_extraction_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, metadata_extraction_enabled: e.target.checked }))}
                          />
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                </Accordion>
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={() => setTempSettings(memorySettings)}
                disabled={!hasChanges}
              >
                Reset
              </Button>
              
              <Button
                variant="outline"
                onClick={settingsOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="vscode"
                onClick={() => {
                  updateMemorySettings(tempSettings!);
                  settingsOnClose();
                }}
                disabled={!hasChanges || !tempSettings}
              >
                Save Changes
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Extensions Modal */}
      <Modal 
        isOpen={extensionsOpen} 
        onClose={extensionsOnClose}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiPackage} />
              <Text>VS Code Extensions</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {/* Search */}
              <FormControl>
                <Input
                  placeholder="Search extensions..."
                  value={extensionSearchQuery}
                  onChange={(e) => setExtensionSearchQuery(e.target.value)}
                  leftIcon={<FiSearch />}
                />
              </FormControl>
              
              {/* Tabs */}
              <Tabs>
                <TabList>
                  <Tab>Search Results</Tab>
                  <Tab>Recommendations</Tab>
                </TabList>
                
                <TabPanels>
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {extensions.map((extension) => (
                        <Card key={extension.id} variant="outline">
                          <CardBody>
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2} flex={1}>
                                <Text fontWeight="bold">{extension.name}</Text>
                                <Text fontSize="sm" color="gray.600">
                                  by {extension.publisher.name}
                                </Text>
                                <Text fontSize="xs" color="gray.500">
                                  {extension.description}
                                </Text>
                                <HStack spacing={2}>
                                  <Badge size="xs" colorScheme="blue">
                                    {extension.category}
                                  </Badge>
                                  <Badge size="xs" colorScheme="green">
                                    v{extension.version}
                                  </Badge>
                                  {extension.is_pre_release && (
                                    <Badge size="xs" colorScheme="orange" variant="outline">
                                      Pre-release
                                    </Badge>
                                  )}
                                </HStack>
                              </VStack>
                              
                              <VStack align="end" spacing={2}>
                                <Text fontSize="sm" fontWeight="medium">
                                  {extension.download_count.toLocaleString()}
                                </Text>
                                <Text fontSize="xs" color="gray.500">
                                  downloads
                                </Text>
                                <Badge size="xs" colorScheme="yellow">
                                  ⭐ {extension.rating.toFixed(1)}
                                </Badge>
                              </VStack>
                            </HStack>
                          </CardBody>
                        </Card>
                      ))}
                    </VStack>
                  </TabPanel>
                  
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      <Alert status="info">
                        <AlertIcon />
                        <Text fontSize="sm">
                          Based on your project structure and detected technologies
                        </Text>
                      </Alert>
                      
                      {recommendations.map((extension) => (
                        <Card key={extension.id} variant="outline">
                          <CardBody>
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2} flex={1}>
                                <Text fontWeight="bold">{extension.name}</Text>
                                <Text fontSize="sm" color="gray.600">
                                  by {extension.publisher.name}
                                </Text>
                                <Text fontSize="xs" color="gray.500">
                                  {extension.description}
                                </Text>
                              </VStack>
                              
                              <Button
                                size="sm"
                                colorScheme="vscode"
                                onClick={() => {
                                  // Implementation for installing extension
                                }}
                              >
                                Install
                              </Button>
                            </HStack>
                          </CardBody>
                        </Card>
                      ))}
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={extensionsOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

// File Tree Item Component
const FileTreeItem: React.FC<{
  item: any;
  level: number;
  expanded: boolean;
  selected: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onRename: (newName: string) => void;
  onDelete: () => void;
  showHidden: boolean;
}> = ({ item, level, expanded, selected, onSelect, onToggle, onRename, onDelete, showHidden }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(item.name);
  
  const handleEdit = () => {
    setIsEditing(true);
    setEditName(item.name);
  };
  
  const handleSave = () => {
    if (editName !== item.name) {
      onRename(editName);
    }
    setIsEditing(false);
  };
  
  const handleCancel = () => {
    setEditName(item.name);
    setIsEditing(false);
  };
  
  // Skip hidden files if not shown
  if (!showHidden && item.name.startsWith('.')) {
    return null;
  }
  
  return (
    <HStack
      pl={`${level * 4 + 2}px`}
      py={1}
      bg={selected ? 'vscode.light.200' : 'transparent'}
      _hover={{ bg: 'vscode.light.100' }}
      cursor="pointer"
      onClick={() => {
        if (item.type === 'folder') {
          onToggle();
        } else {
          onSelect();
        }
      }}
    >
      {item.type === 'folder' && (
        <Icon as={expanded ? FiFolderOpen : FiFolder} color="vscode.500" />
      )}
      
      {item.type === 'file' && (
        <Icon as={FiFile} color="gray.500" />
      )}
      
      {isEditing ? (
        <Input
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSave();
            } else if (e.key === 'Escape') {
              handleCancel();
            }
          }}
          size="xs"
          variant="outline"
          autoFocus
        />
      ) : (
        <Text fontSize="sm" flex={1}>
          {item.name}
        </Text>
      )}
      
      {!isEditing && (
        <IconButton
          icon={<FiEdit2 />}
          variant="ghost"
          size="xs"
          opacity={0}
          _groupHover={{ opacity: 1 }}
          onClick={(e) => {
            e.stopPropagation();
            handleEdit();
          }}
        />
      )}
      
      {!isEditing && item.type === 'file' && (
        <IconButton
          icon={<FiTrash2 />}
          variant="ghost"
          size="xs"
          colorScheme="red"
          opacity={0}
          _groupHover={{ opacity: 1 }}
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        />
      )}
    </HStack>
  );
};

export default VSCodeDevelopmentUI;