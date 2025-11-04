/**
 * ATOM Unified Search Component
 * Shared search interface for web and desktop applications
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Button,
  Select,
  Checkbox,
  Stack,
  Divider,
  Badge,
  Icon,
  useToast,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
  FormControl,
  FormLabel,
  SimpleGrid,
  useDisclosure,
  Collapse,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Tooltip,
  Flex,
  Spacer,
  Heading,
  useColorModeValue,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Card,
  CardBody,
  CardHeader,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  AvatarGroup,
  Tag,
  TagLabel,
  TagLeftIcon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Skeleton,
  useBreakpointValue,
  IconButton,
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerCloseButton,
  DrawerBody,
  DrawerFooter,
  useClipboard,
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogCloseButton,
  AlertDialogBody,
  AlertDialogFooter,
  Slide,
  ScaleFade,
  Fade,
  Scale,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Center,
  Spinner,
  ButtonGroup,
  Switch,
  NumberInput,
  NumberInputField,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverHeader,
  PopoverBody,
  Portal
} from '@chakra-ui/react';
import {
  SearchIcon,
  FilterIcon,
  CloseIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  TimeIcon,
  StarIcon,
  SettingsIcon,
  RepeatIcon,
  DownloadIcon,
  AddIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  HistoryIcon,
  BookmarkIcon,
  ExternalLinkIcon,
  BellIcon,
  GlobeIcon,
  FolderIcon,
  CodeIcon,
  BugIcon,
  DocumentIcon,
  CalendarIcon,
  UserIcon,
  ChatIcon,
  EmailIcon,
  BoxIcon,
  DropBoxIcon,
  GoogleDriveIcon,
  NotionIcon,
  JiraIcon,
  GitHubIcon,
  GitlabIcon,
  SlackIcon,
  EditIcon,
  TrashIcon,
  ViewIcon,
  InfoIcon,
  CopyIcon,
  ShareIcon,
  HamburgerIcon,
  SunIcon,
  MoonIcon,
  DesktopIcon,
  PhoneIcon,
  TabletIcon,
  Search2Icon,
  CpuIcon,
  BrainIcon,
  ZapIcon,
  Settings2Icon,
  CommandIcon,
  PlusIcon,
  SmallCloseIcon,
  CheckIcon,
  WarningIcon,
  QuestionIcon,
  DragHandleIcon,
  LockIcon,
  UnlockIcon,
  ClockIcon,
  CalendarDaysIcon,
  FilterOffIcon,
  FunnelIcon,
  BookMarkedIcon,
  BookOpenIcon,
  LinkIcon,
  UnlinkIcon,
  Edit2Icon,
  MoreIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  SkipBackIcon,
  SkipForwardIcon,
  RewindIcon,
  FastForwardIcon
} from '@chakra-ui/icons';

import {
  AtomSearchResult,
  AtomSearchFilters,
  AtomSearchSort,
  AtomSearchStats,
  AtomSavedSearch,
  AtomSearchConfig,
  AtomVectorMemory,
  AtomVectorConfig
} from '../search/searchTypes';
import { AtomSearchUtils } from '../search/searchUtils';
import useVectorSearch from '../search/useVectorSearch';

// Platform detection
interface PlatformConfig {
  isWeb: boolean;
  isDesktop: boolean;
  isMobile: boolean;
  platform: 'web' | 'desktop' | 'mobile';
  capabilities: {
    notifications: boolean;
    fileSystem: boolean;
    systemIntegration: boolean;
    offlineMode: boolean;
    nativeMenus: boolean;
    hotkeys: boolean;
    autoUpdate: boolean;
  };
}

// App context for shared configuration
interface AtomAppConfig {
  version: string;
  environment: 'development' | 'staging' | 'production';
  theme: 'light' | 'dark' | 'system';
  language: string;
  integrations: string[];
  features: {
    vectorSearch: boolean;
    aiSearch: boolean;
    voiceSearch: boolean;
    offlineSearch: boolean;
    collaborativeSearch: boolean;
    realtimeSearch: boolean;
  };
  performance: {
    maxResults: number;
    searchTimeout: number;
    cacheEnabled: boolean;
    prefetchEnabled: boolean;
    lazyLoading: boolean;
  };
}

interface AtomUnifiedSearchProps {
  platformConfig: PlatformConfig;
  appConfig: AtomAppConfig;
  onSearch: (query: string, filters: AtomSearchFilters, options: any) => void;
  onResultClick: (result: AtomSearchResult) => void;
  onIntegrationClick: (integration: string) => void;
  recentSearches: string[];
  savedSearches: AtomSavedSearch[];
  integrations: string[];
  vectorSearchEnabled?: boolean;
  aiSearchEnabled?: boolean;
  voiceSearchEnabled?: boolean;
  offlineMode?: boolean;
  collaborationEnabled?: boolean;
}

const AtomUnifiedSearch: React.FC<AtomUnifiedSearchProps> = ({
  platformConfig,
  appConfig,
  onSearch,
  onResultClick,
  onIntegrationClick,
  recentSearches,
  savedSearches,
  integrations,
  vectorSearchEnabled = false,
  aiSearchEnabled = false,
  voiceSearchEnabled = false,
  offlineMode = false,
  collaborationEnabled = false
}) => {
  // Core search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<AtomSearchResult[]>([]);
  const [filters, setFilters] = useState<AtomSearchFilters>({
    sources: [],
    types: [],
    dateRange: { from: '', to: '' },
    authors: [],
    projects: [],
    tags: [],
    status: [],
    priority: [],
    includeArchived: false,
    includeDeleted: false
  });

  const [sort, setSort] = useState<AtomSearchSort>({
    field: 'relevance',
    direction: 'desc'
  });

  const [searchMode, setSearchMode] = useState<'hybrid' | 'semantic' | 'keyword' | 'ai' | 'voice'>('hybrid');
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'table' | 'cards'>('list');
  const [selectedTab, setSelectedTab] = useState<'all' | 'files' | 'issues' | 'commits' | 'messages' | 'projects'>('all');

  // UI state
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [showSavedSearchModal, setShowSavedSearchModal] = useState(false);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showSearchStats, setShowSearchStats] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const [isSearching, setIsSearching] = useState(false);
  const [isFiltering, setIsFiltering] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isOffline, setIsOffline] = useState(false);

  const [searchSuggestions, setSearchSuggestions] = useState<string[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  // Platform-specific state
  const [showNativeMenu, setShowNativeMenu] = useState(false);
  const [showSystemTray, setShowSystemTray] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showFileChooser, setShowFileChooser] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);

  // Search statistics
  const [searchStats, setSearchStats] = useState<AtomSearchStats>({
    total: 0,
    sources: 0,
    types: 0,
    time: 0
  });

  // Vector search hook (if enabled)
  const vectorSearch = vectorSearchEnabled ? useVectorSearch({
    lancedbEndpoint: appConfig.features.vectorSearch ? '/api/vector/search' : '',
    memoryEndpoint: appConfig.features.aiSearch ? '/api/memory/search' : '',
    embeddingApiEndpoint: '/api/embeddings',
    defaultEmbeddingModel: 'text-embedding-ada-002',
    availableEmbeddingModels: [],
    defaultVectorConfig: {
      tableName: 'atom_embeddings',
      embeddingDimension: 1536,
      indexType: 'ivf_pq',
      metric: 'cosine',
      useCache: true,
      cacheSize: 1000,
      batchSize: 32,
      numPartitions: 256,
      numSubVectors: 16
    },
    cacheEnabled: appConfig.performance.cacheEnabled,
    cacheTimeout: 300000,
    enablePersistence: true,
    enableAnalytics: true
  }) : null;

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const { hasCopied, onCopy } = useClipboard('');

  // Toast and modals
  const toast = useToast();
  const {
    isOpen: isDeleteOpen,
    onOpen: onDeleteOpen,
    onClose: onDeleteClose
  } = useDisclosure();

  const {
    isOpen: isShareOpen,
    onOpen: onShareOpen,
    onClose: onShareClose
  } = useDisclosure();

  // Responsive breakpoints
  const isMobile = useBreakpointValue({ base: true, md: false });
  const isTablet = useBreakpointValue({ base: false, md: true, lg: false });
  const isDesktop = useBreakpointValue({ base: false, lg: true });

  // Color mode values
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBgColor = useColorModeValue('gray.50', 'gray.700');
  const textColor = useColorModeValue('gray.700', 'gray.300');

  // Platform-specific integration
  useEffect(() => {
    // Initialize platform-specific features
    if (platformConfig.isDesktop && platformConfig.capabilities.hotkeys) {
      // Register keyboard shortcuts
      setupKeyboardShortcuts();
    }

    if (platformConfig.isDesktop && platformConfig.capabilities.notifications) {
      // Request notification permission
      requestNotificationPermission();
    }

    // Check online status
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [platformConfig]);

  // Setup keyboard shortcuts
  const setupKeyboardShortcuts = useCallback(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd/Ctrl + K for search focus
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault();
        searchInputRef.current?.focus();
      }

      // Cmd/Ctrl + / for keyboard shortcuts
      if ((event.metaKey || event.ctrlKey) && event.key === '/') {
        event.preventDefault();
        setShowKeyboardShortcuts(true);
      }

      // Escape to clear search
      if (event.key === 'Escape') {
        setSearchQuery('');
        setSearchTerm('');
        setSearchResults([]);
        searchInputRef.current?.blur();
      }

      // Arrow keys for suggestion navigation
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setSelectedSuggestionIndex(prev => 
          Math.min(prev + 1, searchSuggestions.length - 1)
        );
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setSelectedSuggestionIndex(prev => Math.max(prev - 1, -1));
      }

      // Enter to accept suggestion
      if (event.key === 'Enter' && selectedSuggestionIndex >= 0) {
        event.preventDefault();
        setSearchQuery(searchSuggestions[selectedSuggestionIndex]);
        setSearchTerm(searchSuggestions[selectedSuggestionIndex]);
        setSelectedSuggestionIndex(-1);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [searchSuggestions, selectedSuggestionIndex]);

  // Request notification permission (desktop)
  const requestNotificationPermission = useCallback(async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission();
    }
  }, []);

  // Perform search with platform optimization
  const performSearch = useCallback(async () => {
    if (!searchTerm.trim()) {
      setSearchResults([]);
      setSearchStats({ total: 0, sources: 0, types: 0, time: 0 });
      return;
    }

    setIsSearching(true);
    const startTime = Date.now();

    try {
      let results: AtomSearchResult[] = [];

      // Use vector search if enabled and available
      if (vectorSearchEnabled && vectorSearch && (searchMode === 'semantic' || searchMode === 'hybrid')) {
        await vectorSearch.search({
          query: searchTerm,
          filters,
          mode: searchMode === 'hybrid' ? 'hybrid' : 'semantic',
          options: {
            vector: { threshold: 0.5, topK: 50 },
            memory: { limit: 20, similarity_threshold: 0.6 },
            hybrid: { weight: { vector: 0.7, memory: 0.3 } }
          }
        });
        results = vectorSearch.combinedResults;
      } else {
        // Use traditional search
        // In a real implementation, this would call your search API
        results = generateMockSearchResults(searchTerm, filters, sort);
      }

      // Platform-specific result processing
      if (platformConfig.isDesktop && platformConfig.capabilities.fileSystem) {
        // Add local file results for desktop
        const localResults = await searchLocalFiles(searchTerm, filters);
        results = [...results, ...localResults];
      }

      if (platformConfig.isDesktop && platformConfig.capabilities.systemIntegration) {
        // Add system search results (documents, emails, etc.)
        const systemResults = await searchSystemContent(searchTerm, filters);
        results = [...results, ...systemResults];
      }

      // Apply filters and sorting
      const filteredResults = AtomSearchUtils.filterSearchResults(results, filters);
      const sortedResults = AtomSearchUtils.sortSearchResults(filteredResults, sort);

      const endTime = Date.now();

      setSearchResults(sortedResults);
      setSearchStats(AtomSearchUtils.calculateSearchStats(sortedResults, endTime - startTime));

      // Add to search history
      if (!recentSearches.includes(searchTerm)) {
        const newHistory = [searchTerm, ...recentSearches.slice(0, 9)];
        if (platformConfig.isWeb) {
          localStorage.setItem('atom-search-history', JSON.stringify(newHistory));
        }
      }

      // Platform-specific notifications
      if (platformConfig.isDesktop && platformConfig.capabilities.notifications) {
        if (sortedResults.length === 0) {
          new Notification('ATOM Search', {
            body: `No results found for "${searchTerm}"`,
            icon: '/icons/atom-search.png'
          });
        } else if (sortedResults.length > 0) {
          new Notification('ATOM Search', {
            body: `Found ${sortedResults.length} results for "${searchTerm}"`,
            icon: '/icons/atom-search.png'
          });
        }
      }

    } catch (error) {
      console.error('Search error:', error);
      toast({
        title: 'Search Error',
        description: 'Failed to perform search. Please try again.',
        status: 'error',
        duration: 3000
      });
    } finally {
      setIsSearching(false);
    }
  }, [searchTerm, filters, sort, searchMode, vectorSearchEnabled, vectorSearch, platformConfig, recentSearches, toast]);

  // Mock local file search (desktop)
  const searchLocalFiles = useCallback(async (query: string, filters: AtomSearchFilters): Promise<AtomSearchResult[]> => {
    // In a real desktop app, this would use native file system APIs
    if (!platformConfig.capabilities.fileSystem) return [];

    // Mock implementation
    const mockLocalFiles: AtomSearchResult[] = [
      {
        id: 'local_file_1',
        type: 'file',
        title: `Local Document about ${query}`,
        description: 'This is a local document found on your computer',
        source: 'local_files',
        sourceIcon: DesktopIcon,
        sourceColor: 'blue.500',
        url: 'file:///Users/username/Documents/doc.pdf',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        metadata: { local: true, path: '/Users/username/Documents', size: 1024000 },
        score: 0.8
      }
    ];

    return mockLocalFiles.filter(file => 
      file.title.toLowerCase().includes(query.toLowerCase()) ||
      file.description.toLowerCase().includes(query.toLowerCase())
    );
  }, [platformConfig]);

  // Mock system content search (desktop)
  const searchSystemContent = useCallback(async (query: string, filters: AtomSearchFilters): Promise<AtomSearchResult[]> => {
    // In a real desktop app, this would search emails, calendars, contacts, etc.
    if (!platformConfig.capabilities.systemIntegration) return [];

    // Mock implementation
    const mockSystemResults: AtomSearchResult[] = [
      {
        id: 'system_email_1',
        type: 'message',
        title: `Email about ${query}`,
        description: 'This is an email from your system',
        source: 'system_emails',
        sourceIcon: EmailIcon,
        sourceColor: 'red.500',
        url: 'mailto:example@email.com',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        author: { id: '1', name: 'John Doe', username: 'john' },
        metadata: { system: true, type: 'email', unread: false },
        score: 0.7
      }
    ];

    return mockSystemResults.filter(result => 
      result.title.toLowerCase().includes(query.toLowerCase()) ||
      result.description.toLowerCase().includes(query.toLowerCase())
    );
  }, [platformConfig]);

  // Generate mock search results
  const generateMockSearchResults = useCallback((
    query: string,
    filters: AtomSearchFilters,
    sort: AtomSearchSort
  ): AtomSearchResult[] => {
    const results: AtomSearchResult[] = [];
    const sources = filters.sources.length > 0 ? filters.sources : integrations;
    const types = filters.types.length > 0 ? filters.types : ['file', 'issue', 'commit', 'message', 'task'];

    sources.forEach((source, sourceIndex) => {
      const sourceIcon = getIntegrationIcon(source);
      const sourceColor = getIntegrationColor(source);

      types.forEach((type, typeIndex) => {
        const typeIcon = getTypeIcon(type);
        const typeColor = getTypeColor(type);

        for (let i = 0; i < 3; i++) {
          const score = Math.random() * 100;
          results.push({
            id: `${source}-${type}-${sourceIndex}-${typeIndex}-${i}`,
            type: type as any,
            title: `${query} - ${type} from ${source}`,
            description: `This is a ${type} from ${source} that matches your search query "${query}".`,
            source,
            sourceIcon,
            sourceColor,
            url: `https://${source}.example.com/item/${i}`,
            createdAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
            updatedAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
            author: {
              id: `user_${i}`,
              name: `User ${i}`,
              username: `user${i}`,
              avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${i}`
            },
            metadata: {
              sourceId: sourceIndex,
              typeId: typeIndex,
              itemId: i,
              local: platformConfig.isDesktop,
              system: platformConfig.capabilities.systemIntegration
            },
            score,
            highlights: [query, type, source]
          });
        }
      });
    });

    return AtomSearchUtils.sortSearchResults(results, sort.field, sort.direction);
  }, [filters, sort, integrations, platformConfig]);

  // Get integration icons
  const getIntegrationIcon = (source: string) => {
    const icons: { [key: string]: any } = {
      gitlab: GitlabIcon,
      github: GitHubIcon,
      slack: SlackIcon,
      gmail: EmailIcon,
      notion: NotionIcon,
      jira: JiraIcon,
      box: BoxIcon,
      dropbox: DropBoxIcon,
      gdrive: GoogleDriveIcon,
      local_files: DesktopIcon,
      system_emails: EmailIcon,
      system_contacts: UserIcon
    };
    return icons[source] || DocumentIcon;
  };

  // Get integration colors
  const getIntegrationColor = (source: string): string => {
    const colors: { [key: string]: string } = {
      gitlab: '#FC6D26',
      github: '#24292e',
      slack: '#4A154B',
      gmail: '#EA4335',
      notion: '#000000',
      jira: '#0052CC',
      box: '#0061D5',
      dropbox: '#0061FF',
      gdrive: '#4285F4',
      local_files: '#3182CE',
      system_emails: '#E53E3E',
      system_contacts: '#319795'
    };
    return colors[source] || '#718096';
  };

  // Get type icons
  const getTypeIcon = (type: string) => {
    const icons: { [key: string]: any } = {
      file: DocumentIcon,
      issue: BugIcon,
      commit: CodeIcon,
      message: ChatIcon,
      task: CheckIcon,
      document: DocumentIcon,
      project: FolderIcon,
      user: UserIcon
    };
    return icons[type] || DocumentIcon;
  };

  // Get type colors
  const getTypeColor = (type: string): string => {
    const colors: { [key: string]: string } = {
      file: '#718096',
      issue: '#E53E3E',
      commit: '#38A169',
      message: '#3182CE',
      task: '#805AD5',
      document: '#718096',
      project: '#DD6B20',
      user: '#319795'
    };
    return colors[type] || '#718096';
  };

  // Update filters
  const updateFilters = useCallback((newFilters: Partial<AtomSearchFilters>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    setActiveFilters(Object.keys(updatedFilters).filter(key => {
      const value = updatedFilters[key as keyof AtomSearchFilters];
      if (Array.isArray(value)) return value.length > 0;
      if (typeof value === 'boolean') return value;
      if (typeof value === 'object') return Object.values(value).some(v => v && v.toString().trim());
      return false;
    }));
  }, [filters]);

  // Update sort
  const updateSort = useCallback((field: string, direction?: 'asc' | 'desc') => {
    const newDirection = direction || (sort.field === field && sort.direction === 'desc' ? 'asc' : 'desc');
    const newSort = { field, direction: newDirection };
    setSort(newSort);
  }, [sort]);

  // Clear all filters
  const clearFilters = useCallback(() => {
    const defaultFilters: AtomSearchFilters = {
      sources: [],
      types: [],
      dateRange: { from: '', to: '' },
      authors: [],
      projects: [],
      tags: [],
      status: [],
      priority: [],
      includeArchived: false,
      includeDeleted: false
    };
    
    setFilters(defaultFilters);
    setActiveFilters([]);
  }, []);

  // Handle result click
  const handleResultClick = useCallback((result: AtomSearchResult) => {
    onResultClick(result);
    
    // Platform-specific actions
    if (platformConfig.isDesktop && result.url) {
      if (result.url.startsWith('file://')) {
        // Open local file in system default app
        window.__TAURI__?.shell?.open(result.url);
      } else {
        // Open external URL in default browser
        window.__TAURI__?.shell?.open(result.url);
      }
    } else {
      // Web: open in new tab
      window.open(result.url, '_blank');
    }
  }, [onResultClick, platformConfig]);

  // Share search results
  const shareResults = useCallback(async () => {
    const shareData = {
      query: searchTerm,
      filters,
      results: searchResults,
      stats: searchStats,
      timestamp: new Date().toISOString(),
      platform: platformConfig.platform
    };

    if (platformConfig.isDesktop && window.__TAURI__?.clipboard) {
      // Desktop: copy to clipboard
      await window.__TAURI__?.clipboard.writeText(JSON.stringify(shareData, null, 2));
      toast({
        title: 'Results Copied',
        description: 'Search results copied to clipboard',
        status: 'success',
        duration: 2000
      });
    } else if (navigator.share) {
      // Web: use native sharing
      try {
        await navigator.share({
          title: `ATOM Search: ${searchTerm}`,
          text: `Found ${searchStats.total} results for "${searchTerm}"`,
          url: window.location.href
        });
      } catch (error) {
        console.error('Share error:', error);
      }
    } else {
      // Fallback: copy to clipboard
      onCopy(JSON.stringify(shareData, null, 2));
      toast({
        title: 'Results Copied',
        description: hasCopied ? 'Results copied to clipboard' : 'Failed to copy',
        status: hasCopied ? 'success' : 'error',
        duration: 2000
      });
    }
  }, [searchTerm, filters, searchResults, searchStats, platformConfig, onCopy, hasCopied, toast]);

  // Export search results
  const exportResults = useCallback(async (format: 'json' | 'csv' | 'html') => {
    const exportData = {
      query: searchTerm,
      filters,
      results: searchResults,
      stats: searchStats,
      exportedAt: new Date().toISOString(),
      platform: platformConfig.platform
    };

    let content: string;
    let filename: string;
    let mimeType: string;

    switch (format) {
      case 'json':
        content = JSON.stringify(exportData, null, 2);
        filename = `atom-search-${searchTerm}.json`;
        mimeType = 'application/json';
        break;
      case 'csv':
        content = AtomSearchUtils.exportSearchResults(searchResults, 'csv', searchTerm);
        filename = `atom-search-${searchTerm}.csv`;
        mimeType = 'text/csv';
        break;
      case 'html':
        content = generateHTMLExport(exportData);
        filename = `atom-search-${searchTerm}.html`;
        mimeType = 'text/html';
        break;
    }

    // Platform-specific file handling
    if (platformConfig.isDesktop && window.__TAURI__?.dialog) {
      const selectedPath = await window.__TAURI__?.dialog.save({
        defaultPath: filename,
        filters: [
          {
            name: format.toUpperCase(),
            extensions: [format]
          }
        ]
      });

      if (selectedPath) {
        await window.__TAURI__?.fs.writeFile(selectedPath, content);
        toast({
          title: 'Export Complete',
          description: `Results exported to ${selectedPath}`,
          status: 'success',
          duration: 3000
        });
      }
    } else {
      // Web: download file
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: 'Export Complete',
        description: `Results exported as ${format.toUpperCase()}`,
        status: 'success',
        duration: 2000
      });
    }
  }, [searchTerm, filters, searchResults, searchStats, platformConfig, toast]);

  // Generate HTML export
  const generateHTMLExport = (data: any): string => {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATOM Search Results: ${data.query}</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; margin: 2rem; }
        .header { border-bottom: 2px solid #e2e8f0; padding-bottom: 1rem; margin-bottom: 2rem; }
        .result { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
        .result-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
        .result-description { color: #4a5568; margin-bottom: 0.5rem; }
        .result-meta { font-size: 0.875rem; color: #718096; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem; }
        .source-badge { background: #bee3f8; color: #2c5282; }
        .type-badge { background: #e9d8fd; color: #44337a; }
    </style>
</head>
<body>
    <div class="header">
        <h1>ATOM Search Results</h1>
        <p><strong>Query:</strong> ${data.query}</p>
        <p><strong>Total Results:</strong> ${data.stats.total}</p>
        <p><strong>Searched:</strong> ${new Date(data.timestamp).toLocaleString()}</p>
    </div>
    ${data.results.map((result: AtomSearchResult) => `
        <div class="result">
            <div class="result-title">${result.title}</div>
            <div class="result-description">${result.description || ''}</div>
            <div class="result-meta">
                <span class="badge source-badge">${result.source}</span>
                <span class="badge type-badge">${result.type}</span>
                <span>Updated: ${new Date(result.updatedAt).toLocaleString()}</span>
                ${result.author ? `<span>By: ${result.author.name}</span>` : ''}
            </div>
        </div>
    `).join('')}
</body>
</html>`;
  };

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchTerm(searchQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Perform search when dependencies change
  useEffect(() => {
    if (searchTerm.trim()) {
      performSearch();
    }
  }, [searchTerm, performSearch]);

  // Render search result item
  const renderSearchResult = (result: AtomSearchResult) => {
    const TypeIcon = result.type === 'file' ? getTypeIcon(result.type) : result.type === 'issue' ? getTypeIcon(result.type) : getTypeIcon(result.type);
    const SourceIcon = result.sourceIcon;
    const resultAge = new Date(result.updatedAt).getTime() - Date.now();

    return (
      <Box
        key={result.id}
        p={4}
        bg={bgColor}
        border="1px"
        borderColor={borderColor}
        borderRadius="md"
        cursor="pointer"
        _hover={{ bg: hoverBgColor, shadow: 'sm' }}
        transition="all 0.2s"
        onClick={() => handleResultClick(result)}
      >
        <VStack spacing={3} align="stretch">
          <HStack justify="space-between" align="start">
            <HStack spacing={3}>
              <Icon
                as={TypeIcon}
                w={4} h={4}
                color={getTypeColor(result.type)}
              />
              <VStack align="start" spacing={1">
                <Text fontWeight="bold" noOfLines={1}>
                  {AtomSearchUtils.highlightSearchTerms(result.title, searchTerm)}
                </Text>
                {result.description && (
                  <Text fontSize="sm" color={textColor} noOfLines={2}>
                    {AtomSearchUtils.highlightSearchTerms(result.description, searchTerm)}
                  </Text>
                )}
              </VStack>
            </HStack>
            
            <VStack align="end" spacing={1">
              <Badge
                display="flex"
                alignItems="center"
                gap={1}
                size="sm"
                style={{ backgroundColor: getIntegrationColor(result.source), color: 'white' }}
              >
                <Icon as={SourceIcon} w={3} h={3} />
                {result.source}
              </Badge>
              {result.score && (
                <Badge colorScheme="green" size="sm">
                  {Math.round(result.score)}%
                </Badge>
              )}
              <Text fontSize="xs" color={textColor}>
                {Math.abs(resultAge / (1000 * 60 * 60 * 24)).toFixed(0)}d ago
              </Text>
            </VStack>
          </HStack>
          
          {result.author && (
            <HStack justify="space-between">
              <HStack>
                <Avatar
                  size="xs"
                  name={result.author.name}
                  src={result.author.avatar}
                />
                <Text fontSize="sm" color={textColor}>
                  {result.author.name}
                </Text>
              </HStack>
              
              <HStack spacing={2}>
                {result.highlights?.map((highlight, index) => (
                  <Tag key={index} size="sm" colorScheme="blue" variant="subtle">
                    {highlight}
                  </Tag>
                ))}
              </HStack>
            </HStack>
          )}

          {/* Platform-specific metadata */}
          {(result.metadata.local || result.metadata.system) && (
            <HStack spacing={2}>
              {result.metadata.local && (
                <Tag size="sm" colorScheme="blue" variant="subtle">
                  <DesktopIcon w={3} h={3} />
                  <TagLabel ml={1}>Local</TagLabel>
                </Tag>
              )}
              {result.metadata.system && (
                <Tag size="sm" colorScheme="green" variant="subtle">
                  <CpuIcon w={3} h={3} />
                  <TagLabel ml={1}>System</TagLabel>
                </Tag>
              )}
            </HStack>
          )}
        </VStack>
      </Box>
    );
  };

  // Render platform-specific actions
  const renderPlatformActions = () => {
    if (platformConfig.isDesktop) {
      return (
        <HStack spacing={2}>
          {/* Native menu */}
          <Menu>
            <MenuButton
              as={Button}
              size="sm"
              variant="ghost"
              leftIcon={<HamburgerIcon />}
            >
              Menu
            </MenuButton>
            <MenuList>
              <MenuItem onClick={() => setShowFileChooser(true)}>
                <DesktopIcon mr={2} />
                Open File
              </MenuItem>
              <MenuItem onClick={() => setShowSystemTray(!showSystemTray)}>
                <DesktopIcon mr={2} />
                {showSystemTray ? 'Hide' : 'Show'} System Tray
              </MenuItem>
              <MenuItem onClick={() => setShowNotifications(!showNotifications)}>
                <BellIcon mr={2} />
                {showNotifications ? 'Disable' : 'Enable'} Notifications
              </MenuItem>
              <MenuItem onClick={() => setShowSettings(true)}>
                <SettingsIcon mr={2} />
                Settings
              </MenuItem>
            </MenuList>
          </Menu>

          {/* Platform-specific integrations */}
          {platformConfig.capabilities.fileSystem && (
            <Tooltip label="Search Local Files">
              <IconButton
                size="sm"
                variant="ghost"
                aria-label="Search local files"
                icon={<DesktopIcon />}
                onClick={() => {
                  setSearchMode(prev => prev === 'semantic' ? 'keyword' : 'semantic');
                }}
              />
            </Tooltip>
          )}
        </HStack>
      );
    }

    return null;
  };

  return (
    <Box minH="100vh" bg={bgColor} ref={searchContainerRef}>
      {/* Search Header */}
      <Box
        position="sticky"
        top={0}
        zIndex={1000}
        bg={bgColor}
        borderBottom="1px"
        borderColor={borderColor}
        p={4}
      >
        <VStack spacing={4} align="stretch">
          {/* Platform Header */}
          <HStack justify="space-between" align="center">
            <HStack spacing={4}>
              <Heading size="lg" display="flex" alignItems="center" gap={2}>
                {platformConfig.isDesktop ? (
                  <DesktopIcon color="blue.500" />
                ) : (
                  <SearchIcon color="blue.500" />
                )}
                ATOM Search
                <Badge colorScheme="green" size="sm" variant="outline">
                  {platformConfig.platform}
                </Badge>
              </Heading>
              
              {/* Platform Status */}
              <HStack spacing={2}>
                {isOffline && (
                  <Badge colorScheme="red" size="sm">
                    Offline
                  </Badge>
                )}
                {offlineMode && (
                  <Badge colorScheme="orange" size="sm">
                    Offline Mode
                  </Badge>
                )}
                <Badge colorScheme="blue" size="sm">
                  {appConfig.environment}
                </Badge>
              </HStack>
            </HStack>
            
            <HStack spacing={4}>
              {renderPlatformActions()}
              
              {/* Search Mode Toggle */}
              <Menu>
                <MenuButton
                  as={Button}
                  size="sm"
                  variant="outline"
                  rightIcon={<ChevronDownIcon />}
                >
                  {searchMode === 'hybrid' && <ZapIcon mr={2} />}
                  {searchMode === 'semantic' && <BrainIcon mr={2} />}
                  {searchMode === 'keyword' && <SearchIcon mr={2} />}
                  {searchMode === 'ai' && <CpuIcon mr={2} />}
                  {searchMode === 'voice' && <Edit2Icon mr={2} />}
                  {searchMode.charAt(0).toUpperCase() + searchMode.slice(1)}
                </MenuButton>
                <MenuList>
                  <MenuItem
                    icon={<ZapIcon />}
                    onClick={() => setSearchMode('hybrid')}
                    bg={searchMode === 'hybrid' ? 'blue.50' : 'transparent'}
                  >
                    Hybrid Search
                  </MenuItem>
                  {vectorSearchEnabled && (
                    <MenuItem
                      icon={<BrainIcon />}
                      onClick={() => setSearchMode('semantic')}
                      bg={searchMode === 'semantic' ? 'blue.50' : 'transparent'}
                    >
                      Semantic Search
                    </MenuItem>
                  )}
                  {aiSearchEnabled && (
                    <MenuItem
                      icon={<CpuIcon />}
                      onClick={() => setSearchMode('ai')}
                      bg={searchMode === 'ai' ? 'blue.50' : 'transparent'}
                    >
                      AI Search
                    </MenuItem>
                  )}
                  {voiceSearchEnabled && (
                    <MenuItem
                      icon={<Edit2Icon />}
                      onClick={() => setSearchMode('voice')}
                      bg={searchMode === 'voice' ? 'blue.50' : 'transparent'}
                    >
                      Voice Search
                    </MenuItem>
                  )}
                  <MenuItem
                    icon={<SearchIcon />}
                    onClick={() => setSearchMode('keyword')}
                    bg={searchMode === 'keyword' ? 'blue.50' : 'transparent'}
                  >
                    Keyword Search
                  </MenuItem>
                </MenuList>
              </Menu>

              {/* View Mode Toggle */}
              <Menu>
                <MenuButton
                  as={Button}
                  size="sm"
                  variant="ghost"
                  rightIcon={<ChevronDownIcon />}
                >
                  {viewMode === 'list' && <HStack justify="space-between" w="100px"><span>List</span></HStack>}
                  {viewMode === 'grid' && <HStack justify="space-between" w="100px"><span>Grid</span></HStack>}
                  {viewMode === 'table' && <HStack justify="space-between" w="100px"><span>Table</span></HStack>}
                  {viewMode === 'cards' && <HStack justify="space-between" w="100px"><span>Cards</span></HStack>}
                </MenuButton>
                <MenuList>
                  <MenuItem onClick={() => setViewMode('list')}>
                    List View
                  </MenuItem>
                  <MenuItem onClick={() => setViewMode('grid')}>
                    Grid View
                  </MenuItem>
                  <MenuItem onClick={() => setViewMode('table')}>
                    Table View
                  </MenuItem>
                  <MenuItem onClick={() => setViewMode('cards')}>
                    Card View
                  </MenuItem>
                </MenuList>
              </Menu>

              {/* Keyboard Shortcuts Help */}
              <Tooltip label="Keyboard Shortcuts (⌘/)">
                <IconButton
                  size="sm"
                  variant="ghost"
                  aria-label="Keyboard shortcuts"
                  icon={<CommandIcon />}
                  onClick={() => setShowKeyboardShortcuts(true)}
                />
              </Tooltip>
            </HStack>
          </HStack>

          {/* Main Search Bar */}
          <InputGroup size={isMobile ? 'md' : 'lg'}>
            <InputLeftElement>
              <Icon as={SearchIcon} color="gray.400" />
            </InputLeftElement>
            <Input
              ref={searchInputRef}
              placeholder={`Search ${platformConfig.isDesktop ? 'everywhere' : 'across integrations'}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  performSearch();
                }
              }}
              onFocus={() => {
                if (recentSearches.length > 0) {
                  setShowSearchHistory(true);
                }
              }}
              onBlur={() => {
                setTimeout(() => setShowSearchHistory(false), 200);
              }}
            />
            <InputRightElement width="auto">
              <HStack spacing={2} mr={2}>
                {isSearching && <Spinner size="sm" />}
                {searchQuery && (
                  <IconButton
                    size="sm"
                    variant="ghost"
                    aria-label="Clear search"
                    icon={<CloseIcon />}
                    onClick={() => {
                      setSearchQuery('');
                      setSearchTerm('');
                      setSearchResults([]);
                    }}
                  />
                )}
                {platformConfig.isDesktop && (
                  <Tooltip label="Voice Search (if enabled)">
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Voice search"
                      icon={<Edit2Icon />}
                      onClick={() => voiceSearchEnabled && setSearchMode('voice')}
                      isDisabled={!voiceSearchEnabled}
                    />
                  </Tooltip>
                )}
              </HStack>
            </InputRightElement>
          </InputGroup>

          {/* Search History Dropdown */}
          {showSearchHistory && recentSearches.length > 0 && (
            <Box
              position="absolute"
              top="100%"
              left={0}
              right={0}
              bg={bgColor}
              border="1px"
              borderColor={borderColor}
              borderTop="none"
              borderRadius="0 0 md md"
              boxShadow="lg"
              zIndex={1001}
            >
              <VStack spacing={1} align="stretch" p={2}>
                <Text fontSize="sm" fontWeight="bold" px={2}>
                  Recent Searches
                </Text>
                {recentSearches.map((search, index) => (
                  <MenuItem
                    key={index}
                    onClick={() => {
                      setSearchQuery(search);
                      setSearchTerm(search);
                      setShowSearchHistory(false);
                    }}
                    bg={selectedSuggestionIndex === index ? hoverBgColor : 'transparent'}
                  >
                    <HStack>
                      <HistoryIcon color="gray.500" />
                      <Text>{search}</Text>
                    </HStack>
                  </MenuItem>
                ))}
              </VStack>
            </Box>
          )}

          {/* Quick Filters */}
          <HStack spacing={4} wrap="wrap" justify="space-between">
            <HStack spacing={4} wrap="wrap">
              {/* Source Filter */}
              <Select
                placeholder="All Sources"
                w={isMobile ? '120px' : '150px'}
                value={filters.sources.join(',')}
                onChange={(e) => {
                  const selected = e.target.value;
                  updateFilters({
                    sources: selected ? selected.split(',') : []
                  });
                }}
              >
                {integrations.map(integration => (
                  <option key={integration} value={integration}>
                    {integration.charAt(0).toUpperCase() + integration.slice(1)}
                  </option>
                ))}
                {platformConfig.isDesktop && (
                  <option value="local_files">Local Files</option>
                )}
                {platformConfig.isDesktop && (
                  <option value="system_content">System Content</option>
                )}
              </Select>

              {/* Type Filter */}
              <Select
                placeholder="All Types"
                w={isMobile ? '120px' : '150px'}
                value={filters.types.join(',')}
                onChange={(e) => {
                  const selected = e.target.value;
                  updateFilters({
                    types: selected ? selected.split(',') : []
                  });
                }}
              >
                <option value="file">Files</option>
                <option value="issue">Issues</option>
                <option value="commit">Commits</option>
                <option value="message">Messages</option>
                <option value="task">Tasks</option>
              </Select>

              {/* Sort Options */}
              <Select
                placeholder="Sort by..."
                w={isMobile ? '120px' : '150px'}
                value={sort.field}
                onChange={(e) => updateSort(e.target.value)}
              >
                <option value="relevance">Relevance</option>
                <option value="updated_at">Last Updated</option>
                <option value="created_at">Created</option>
                <option value="title">Title</option>
                <option value="source">Source</option>
              </Select>

              <Button
                variant="outline"
                leftIcon={sort.direction === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />}
                onClick={() => updateSort(sort.field)}
                size={isMobile ? 'sm' : 'md'}
              >
                {sort.direction === 'asc' ? 'Ascending' : 'Descending'}
              </Button>
            </HStack>

            <HStack spacing={4}>
              <Button
                variant="outline"
                leftIcon={<FilterIcon />}
                rightIcon={showAdvancedFilters ? <ChevronUpIcon /> : <ChevronDownIcon />}
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                size={isMobile ? 'sm' : 'md'}
              >
                Filters
                {activeFilters.length > 0 && (
                  <Badge ml={2} colorScheme="blue" size="sm">
                    {activeFilters.length}
                  </Badge>
                )}
              </Button>

              <Menu>
                <MenuButton
                  as={Button}
                  variant="outline"
                  rightIcon={<ChevronDownIcon />}
                  size={isMobile ? 'sm' : 'md'}
                >
                  <MoreIcon />
                </MenuButton>
                <MenuList>
                  <MenuItem onClick={() => setShowSavedSearchModal(true)}>
                    <BookmarkIcon mr={2} />
                    Saved Searches
                  </MenuItem>
                  <MenuItem onClick={shareResults}>
                    <ShareIcon mr={2} />
                    Share Results
                  </MenuItem>
                  <MenuItem onClick={() => setShowSearchStats(true)}>
                    <InfoIcon mr={2} />
                    Search Stats
                  </MenuItem>
                  <MenuItem onClick={clearFilters}>
                    <FilterOffIcon mr={2} />
                    Clear Filters
                  </MenuItem>
                  <MenuItem onClick={() => setShowKeyboardShortcuts(true)}>
                    <CommandIcon mr={2} />
                    Keyboard Shortcuts
                  </MenuItem>
                </MenuList>
              </Menu>
            </HStack>
          </HStack>
        </VStack>
      </Box>

      {/* Advanced Filters */}
      <Collapse in={showAdvancedFilters} animateOpacity>
        <Box bg="gray.50" p={4} borderBottom="1px" borderColor={borderColor}>
          <Accordion allowMultiple>
            {/* Source Filter */}
            <AccordionItem>
              <h2>
                <AccordionButton>
                  <Box flex="1" textAlign="left">
                    <Text fontWeight="bold">Sources</Text>
                  </Box>
                  <AccordionIcon />
                </AccordionButton>
              </h2>
              <AccordionPanel>
                <SimpleGrid columns={{ base: 2, md: 3, lg: 4 }} spacing={4}>
                  {[...integrations, ...(platformConfig.isDesktop ? ['local_files', 'system_content'] : [])].map(source => {
                    const Icon = getIntegrationIcon(source);
                    const color = getIntegrationColor(source);
                    
                    return (
                      <Checkbox
                        key={source}
                        isChecked={filters.sources.includes(source)}
                        onChange={(e) => {
                          const newSources = e.target.checked
                            ? [...filters.sources, source]
                            : filters.sources.filter(s => s !== source);
                          updateFilters({ sources: newSources });
                        }}
                      >
                        <HStack>
                          <Icon as={Icon} w={4} h={4} color={color} />
                          <Text>
                            {source === 'local_files' ? 'Local Files' :
                             source === 'system_content' ? 'System Content' :
                             source.charAt(0).toUpperCase() + source.slice(1)}
                          </Text>
                        </HStack>
                      </Checkbox>
                    );
                  })}
                </SimpleGrid>
              </AccordionPanel>
            </AccordionItem>

            {/* Type Filter */}
            <AccordionItem>
              <h2>
                <AccordionButton>
                  <Box flex="1" textAlign="left">
                    <Text fontWeight="bold">Types</Text>
                  </Box>
                  <AccordionIcon />
                </AccordionButton>
              </h2>
              <AccordionPanel>
                <SimpleGrid columns={{ base: 2, md: 3, lg: 4 }} spacing={4}>
                  {['file', 'issue', 'commit', 'message', 'task', 'document', 'project', 'user'].map(type => {
                    const Icon = getTypeIcon(type);
                    const color = getTypeColor(type);
                    
                    return (
                      <Checkbox
                        key={type}
                        isChecked={filters.types.includes(type)}
                        onChange={(e) => {
                          const newTypes = e.target.checked
                            ? [...filters.types, type]
                            : filters.types.filter(t => t !== type);
                          updateFilters({ types: newTypes });
                        }}
                      >
                        <HStack>
                          <Icon as={Icon} w={4} h={4} color={color} />
                          <Text>{type.charAt(0).toUpperCase() + type.slice(1)}</Text>
                        </HStack>
                      </Checkbox>
                    );
                  })}
                </SimpleGrid>
              </AccordionPanel>
            </AccordionItem>

            {/* Date Range Filter */}
            <AccordionItem>
              <h2>
                <AccordionButton>
                  <Box flex="1" textAlign="left">
                    <Text fontWeight="bold">Date Range</Text>
                  </Box>
                  <AccordionIcon />
                </AccordionButton>
              </h2>
              <AccordionPanel>
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                  <FormControl>
                    <FormLabel>From</FormLabel>
                    <Input
                      type="date"
                      value={filters.dateRange.from}
                      onChange={(e) => updateFilters({
                        dateRange: { ...filters.dateRange, from: e.target.value }
                      })}
                    />
                  </FormControl>
                  <FormControl>
                    <FormLabel>To</FormLabel>
                    <Input
                      type="date"
                      value={filters.dateRange.to}
                      onChange={(e) => updateFilters({
                        dateRange: { ...filters.dateRange, to: e.target.value }
                      })}
                    />
                  </FormControl>
                </SimpleGrid>
              </AccordionPanel>
            </AccordionItem>
          </Accordion>
        </Box>
      </Collapse>

      {/* Search Statistics */}
      {searchResults.length > 0 && (
        <Box bg="gray.50" p={4} borderBottom="1px" borderColor={borderColor}>
          <HStack justify="space-between" align="center">
            <HStack>
              <Text fontWeight="bold">
                {searchStats.total} results
              </Text>
              <Text fontSize="sm" color={textColor}>
                Found in {AtomSearchUtils.formatSearchTime(searchStats.time)}
              </Text>
              <Text fontSize="sm" color={textColor}>
                from {searchStats.sources} sources, {searchStats.types} types
              </Text>
            </HStack>
            
            <HStack>
              <Text fontSize="sm" color={textColor}>
                {activeFilters.length} filters active
              </Text>
              
              {/* Platform-specific actions */}
              <Menu>
                <MenuButton
                  as={Button}
                  size="sm"
                  variant="outline"
                  rightIcon={<ChevronDownIcon />}
                >
                  Actions
                </MenuButton>
                <MenuList>
                  <MenuItem onClick={() => exportResults('json')}>
                    <DownloadIcon mr={2} />
                    Export JSON
                  </MenuItem>
                  <MenuItem onClick={() => exportResults('csv')}>
                    <DownloadIcon mr={2} />
                    Export CSV
                  </MenuItem>
                  <MenuItem onClick={() => exportResults('html')}>
                    <DownloadIcon mr={2} />
                    Export HTML
                  </MenuItem>
                  <MenuItem onClick={shareResults}>
                    <ShareIcon mr={2} />
                    Share Results
                  </MenuItem>
                </MenuList>
              </Menu>
            </HStack>
          </HStack>
        </Box>
      )}

      {/* Search Results */}
      <Box p={4}>
        {isSearching ? (
          <VStack spacing={4}>
            {Array.from({ length: 5 }).map((_, index) => (
              <Box key={index} w="full">
                <Skeleton height="100px" w="full" />
              </Box>
            ))}
          </VStack>
        ) : searchResults.length > 0 ? (
          <VStack spacing={4} align="stretch">
            {searchResults.map(renderSearchResult)}
          </VStack>
        ) : searchTerm.trim() ? (
          <VStack spacing={4} py={8}>
            <Icon as={SearchIcon} w={12} h={12} color="gray.400" />
            <Text fontSize="lg" color={textColor} textAlign="center">
              No results found for "{searchTerm}"
            </Text>
            <Text fontSize="sm" color={textColor} textAlign="center">
              Try adjusting your filters, search terms, or switching search modes
            </Text>
            <Button
              variant="outline"
              onClick={clearFilters}
            >
              Clear Filters
            </Button>
          </VStack>
        ) : (
          <VStack spacing={4} py={8}>
            <Icon as={SearchIcon} w={12} h={12} color="gray.400" />
            <Text fontSize="lg" color={textColor} textAlign="center">
              {platformConfig.isDesktop ? 'Search across your integrations and local content' : 'Search across your integrations'}
            </Text>
            <Text fontSize="sm" color={textColor} textAlign="center">
              {platformConfig.isDesktop ? 'Try "Ctrl+K" to focus search' : 'Try "/" to focus search'}
            </Text>
            
            {/* Feature showcase */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4} mt={8}>
              <Card variant="outline">
                <CardBody textAlign="center">
                  <BrainIcon w={8} h={8} color="purple.500" mb={2} />
                  <Text fontWeight="bold">Semantic Search</Text>
                  <Text fontSize="sm" color={textColor}>
                    Understand meaning, not just keywords
                  </Text>
                </CardBody>
              </Card>
              
              <Card variant="outline">
                <CardBody textAlign="center">
                  <DesktopIcon w={8} h={8} color="blue.500" mb={2} />
                  <Text fontWeight="bold">Local Search</Text>
                  <Text fontSize="sm" color={textColor}>
                    Search your files and system content
                  </Text>
                </CardBody>
              </Card>
              
              <Card variant="outline">
                <CardBody textAlign="center">
                  <ZapIcon w={8} h={8" color="orange.500" mb={2} />
                  <Text fontWeight="bold">Hybrid Search</Text>
                  <Text fontSize="sm" color={textColor}>
                    Combine vector and keyword search
                  </Text>
                </CardBody>
              </Card>
              
              <Card variant="outline">
                <CardBody textAlign="center">
                  <CpuIcon w={8} h={8} color="green.500" mb={2} />
                  <Text fontWeight="bold">AI Search</Text>
                  <Text fontSize="sm" color={textColor}>
                    Powered by advanced AI models
                  </Text>
                </CardBody>
              </Card>
            </SimpleGrid>
          </VStack>
        )}
      </Box>

      {/* Keyboard Shortcuts Modal */}
      <Modal isOpen={showKeyboardShortcuts} onClose={() => setShowKeyboardShortcuts(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <CommandIcon color="blue.500" />
              <Text>Keyboard Shortcuts</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Text>Focus Search</Text>
                <Badge>⌘K / Ctrl+K</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Clear Search</Text>
                <Badge>Escape</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Next Suggestion</Text>
                <Badge>↓</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Previous Suggestion</Text>
                <Badge>↑</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Accept Suggestion</Text>
                <Badge>Enter</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Toggle Filters</Text>
                <Badge>⌘F / Ctrl+F</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Export Results</Text>
                <Badge>⌘E / Ctrl+E</Badge>
              </HStack>
              <HStack justify="space-between">
                <Text>Share Results</Text>
                <Badge>⌘S / Ctrl+S</Badge>
              </HStack>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button onClick={() => setShowKeyboardShortcuts(false)}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Search Stats Modal */}
      <Modal isOpen={showSearchStats} onClose={() => setShowSearchStats(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <InfoIcon color="blue.500" />
              <Text>Search Statistics</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              <Stat>
                <StatLabel>Total Results</StatLabel>
                <StatNumber>{searchStats.total}</StatNumber>
                <StatHelpText>
                  {searchStats.time}ms search time
                </StatHelpText>
              </Stat>
              
              <Stat>
                <StatLabel>Sources Searched</StatLabel>
                <StatNumber>{searchStats.sources}</StatNumber>
                <StatHelpText>
                  {searchStats.types} result types
                </StatHelpText>
              </Stat>
              
              <Stat>
                <StatLabel>Search Mode</StatLabel>
                <StatNumber>{searchMode}</StatNumber>
                <StatHelpText>
                  {vectorSearchEnabled && 'Vector search enabled'}
                </StatHelpText>
              </Stat>
              
              <Stat>
                <StatLabel>Platform</StatLabel>
                <StatNumber>{platformConfig.platform}</StatNumber>
                <StatHelpText>
                  {appConfig.environment} environment
                </StatHelpText>
              </Stat>
            </SimpleGrid>
          </ModalBody>
          <ModalFooter>
            <Button onClick={() => setShowSearchStats(false)}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Saved Searches Modal */}
      <Modal isOpen={showSavedSearchModal} onClose={() => setShowSavedSearchModal(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <BookmarkIcon color="blue.500" />
              <Text>Saved Searches</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {savedSearches.length > 0 ? (
                savedSearches.map((savedSearch, index) => (
                  <Box
                    key={index}
                    p={4}
                    border="1px"
                    borderColor={borderColor}
                    borderRadius="md"
                    cursor="pointer"
                    _hover={{ bg: hoverBgColor }}
                    onClick={() => {
                      setSearchQuery(savedSearch.query);
                      setSearchTerm(savedSearch.query);
                      setFilters(savedSearch.filters);
                      setSort(savedSearch.sort);
                      setShowSavedSearchModal(false);
                    }}
                  >
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold">{savedSearch.name}</Text>
                        <Text fontSize="sm" color={textColor}>
                          {savedSearch.query || 'No search term'}
                        </Text>
                        <Text fontSize="xs" color={textColor}>
                          Created: {new Date(savedSearch.createdAt).toLocaleDateString()}
                        </Text>
                      </VStack>
                      <HStack>
                        <Badge colorScheme="blue">
                          {savedSearch.query ? 'Keyword' : 'Filters'}
                        </Badge>
                        <IconButton
                          size="sm"
                          variant="ghost"
                          aria-label="Delete saved search"
                          icon={<TrashIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            // Handle delete
                            onDeleteOpen();
                          }}
                        />
                      </HStack>
                    </HStack>
                  </Box>
                ))
              ) : (
                <Box textAlign="center" py={8}>
                  <Icon as={BookmarkIcon} w={12} h={12} color="gray.400" />
                  <Text color={textColor}>No saved searches found</Text>
                </Box>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack spacing={4}>
              <Button
                variant="outline"
                onClick={() => {
                  // Save current search
                  const searchName = prompt('Enter a name for this search:');
                  if (searchName) {
                    toast({
                      title: 'Search Saved',
                      description: `"${searchName}" has been saved`,
                      status: 'success',
                      duration: 2000
                    });
                  }
                }}
              >
                Save Current Search
              </Button>
              <Button onClick={() => setShowSavedSearchModal(false)}>
                Close
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Platform-specific components */}
      {platformConfig.isDesktop && (
        <>
          {/* File Chooser */}
          <Modal isOpen={showFileChooser} onClose={() => setShowFileChooser(false)} size="lg">
            <ModalOverlay />
            <ModalContent>
              <ModalHeader>Choose File to Search</ModalHeader>
              <ModalCloseButton />
              <ModalBody>
                <VStack spacing={4}>
                  <Text>File chooser will be implemented here for desktop</Text>
                </VStack>
              </ModalBody>
              <ModalFooter>
                <Button onClick={() => setShowFileChooser(false)}>
                  Cancel
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>

          {/* Settings Modal */}
          <Modal isOpen={showSettings} onClose={() => setShowSettings(false)} size="xl">
            <ModalOverlay />
            <ModalContent>
              <ModalHeader>
                <HStack>
                  <SettingsIcon color="blue.500" />
                  <Text>Search Settings</Text>
                </HStack>
              </ModalHeader>
              <ModalCloseButton />
              <ModalBody>
                <Tabs>
                  <TabList>
                    <Tab>General</Tab>
                    <Tab>Performance</Tab>
                    <Tab>Integrations</Tab>
                    <Tab>Advanced</Tab>
                  </TabList>
                  <TabPanels>
                    <TabPanel>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center">
                          <FormLabel mb="0">Enable Notifications</FormLabel>
                          <Switch
                            isChecked={showNotifications}
                            onChange={(e) => setShowNotifications(e.target.checked)}
                          />
                        </FormControl>
                        <FormControl display="flex" alignItems="center">
                          <FormLabel mb="0">Show in System Tray</FormLabel>
                          <Switch
                            isChecked={showSystemTray}
                            onChange={(e) => setShowSystemTray(e.target.checked)}
                          />
                        </FormControl>
                        <FormControl display="flex" alignItems="center">
                          <FormLabel mb="0">Enable Offline Mode</FormLabel>
                          <Switch
                            isChecked={offlineMode}
                            onChange={(e) => {/* handle */}}
                          />
                        </FormControl>
                      </VStack>
                    </TabPanel>
                    <TabPanel>
                      <VStack spacing={4} align="stretch">
                        <FormControl>
                          <FormLabel>Max Results</FormLabel>
                          <NumberInput
                            value={appConfig.performance.maxResults}
                            onChange={(value) => {/* handle */}}
                            min={10}
                            max={1000}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                        <FormControl>
                          <FormLabel>Search Timeout (ms)</FormLabel>
                          <NumberInput
                            value={appConfig.performance.searchTimeout}
                            onChange={(value) => {/* handle */}}
                            min={1000}
                            max={30000}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </TabPanel>
                    <TabPanel>
                      <VStack spacing={4} align="stretch">
                        <Text>Integration settings will be implemented here</Text>
                      </VStack>
                    </TabPanel>
                    <TabPanel>
                      <VStack spacing={4} align="stretch">
                        <Text>Advanced settings will be implemented here</Text>
                      </VStack>
                    </TabPanel>
                  </TabPanels>
                </Tabs>
              </ModalBody>
              <ModalFooter>
                <Button onClick={() => setShowSettings(false)}>
                  Close
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </>
      )}
    </Box>
  );
};

export default AtomUnifiedSearch;