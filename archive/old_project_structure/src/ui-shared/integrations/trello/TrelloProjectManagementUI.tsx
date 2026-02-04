/**
 * Trello Project Management UI
 * Complete Trello project management interface
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Button,
  Text,
  Icon,
  Avatar,
  Badge,
  Tooltip,
  Progress,
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
  Select,
  Switch,
  Divider,
  SimpleGrid,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Stack,
  Wrap,
  WrapItem,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  IconButton,
  useDisclosure,
  useToast,
  useColorModeValue,
  Grid,
  GridItem,
  Flex,
  Spacer,
  Container
} from '@chakra-ui/react';
import {
  FiTrello,
  FiPlus,
  FiSearch,
  FiFilter,
  FiSettings,
  FiRefreshCw,
  FiCheck,
  FiX,
  FiClock,
  FiCalendar,
  FiUser,
  FiUsers,
  FiTag,
  FiFileText,
  FiCheckSquare,
  FiSquare,
  FiMoreHorizontal,
  FiEdit2,
  FiTrash2,
  FiArchive,
  FiEye,
  FiLink,
  FiBell,
  FiAlertCircle,
  FiZap,
  FiDatabase,
  FiTrendingUp,
  FiActivity,
  FiDownload,
  FiUpload,
  FiMove,
  FiCopy,
  FiShare2,
  FiBookmark,
  FiStar,
  FiFlag,
  FiMessageSquare,
  FiPaperclip,
  FiChevronDown,
  FiChevronRight,
  FiLayers,
  FiGrid,
  FiList,
  FiPackage
} from 'react-icons/fi';

// Mock Trello skills (would be imported from actual skills)
const trelloSkills = {
  trelloGetBoards: async (userId, apiKey, oauthToken, filter) => {
    // Mock implementation
    return {
      success: true,
      boards: [
        {
          id: 'board1',
          name: 'Project Alpha',
          description: 'Main project development',
          closed: false,
          url: 'https://trello.com/b/board1',
          shortUrl: 'https://trello.com/b/board1',
          shortLink: 'board1',
          dateLastActivity: new Date().toISOString(),
          pinned: false,
          starred: false,
          subscribed: false,
          totalCards: 25,
          totalLists: 5,
          totalMembers: 8,
          totalChecklists: 12
        },
        {
          id: 'board2',
          name: 'Marketing Campaign',
          description: 'Q4 marketing initiatives',
          closed: false,
          url: 'https://trello.com/b/board2',
          shortUrl: 'https://trello.com/b/board2',
          shortLink: 'board2',
          dateLastActivity: new Date(Date.now() - 86400000).toISOString(),
          pinned: false,
          starred: true,
          subscribed: true,
          totalCards: 18,
          totalLists: 4,
          totalMembers: 5,
          totalChecklists: 8
        }
      ]
    };
  },
  trelloGetCards: async (userId, apiKey, oauthToken, boardId, listId, filter) => {
    // Mock implementation
    return {
      success: true,
      cards: [
        {
          id: 'card1',
          idBoard: boardId,
          idList: listId,
          name: 'Implement authentication',
          description: 'Add OAuth 2.0 authentication to the application',
          closed: false,
          due: new Date(Date.now() + 604800000).toISOString(),
          dueComplete: false,
          start: new Date(Date.now() - 86400000).toISOString(),
          url: 'https://trello.com/c/card1',
          shortUrl: 'https://trello.com/c/card1',
          shortLink: 'card1',
          subscribed: true,
          labels: [
            { id: 'label1', name: 'Feature', color: 'green' },
            { id: 'label2', name: 'High Priority', color: 'red' }
          ],
          members: [
            { id: 'member1', username: 'john_doe', fullName: 'John Doe' }
          ],
          checklists: [
            { id: 'checklist1', name: 'Development Tasks', checkItems: [
              { state: 'complete', name: 'Design API' },
              { state: 'incomplete', name: 'Implement backend' },
              { state: 'incomplete', name: 'Create frontend' }
            ]}
          ],
          badges: { comments: 3, attachments: 2, checkItems: 3, checkItemsChecked: 1 },
          dateLastActivity: new Date().toISOString()
        },
        {
          id: 'card2',
          idBoard: boardId,
          idList: listId,
          name: 'Design database schema',
          description: 'Create efficient database structure',
          closed: false,
          due: new Date(Date.now() + 259200000).toISOString(),
          dueComplete: false,
          url: 'https://trello.com/c/card2',
          shortUrl: 'https://trello.com/c/card2',
          shortLink: 'card2',
          subscribed: false,
          labels: [
            { id: 'label3', name: 'Design', color: 'blue' }
          ],
          members: [],
          checklists: [],
          badges: { comments: 0, attachments: 1, checkItems: 0, checkItemsChecked: 0 },
          dateLastActivity: new Date(Date.now() - 3600000).toISOString()
        }
      ]
    };
  },
  trelloCreateCard: async (userId, apiKey, oauthToken, name, idList, desc, due, idMembers, idLabels) => {
    // Mock implementation
    return {
      success: true,
      card: {
        id: 'newcard1',
        name: name,
        description: desc,
        due: due,
        url: 'https://trello.com/c/newcard1',
        shortUrl: 'https://trello.com/c/newcard1',
        shortLink: 'newcard1'
      }
    };
  },
  trelloGetLists: async (userId, apiKey, oauthToken, boardId, includeCards) => {
    // Mock implementation
    return {
      success: true,
      lists: [
        {
          id: 'list1',
          name: 'To Do',
          closed: false,
          pos: 1,
          subscribed: false,
          totalCards: 5,
          cards: includeCards ? [
            { id: 'card1', name: 'Implement authentication', pos: 1 },
            { id: 'card2', name: 'Design database schema', pos: 2 }
          ] : []
        },
        {
          id: 'list2',
          name: 'In Progress',
          closed: false,
          pos: 2,
          subscribed: false,
          totalCards: 3,
          cards: includeCards ? [] : []
        },
        {
          id: 'list3',
          name: 'Done',
          closed: false,
          pos: 3,
          subscribed: false,
          totalCards: 8,
          cards: includeCards ? [] : []
        }
      ]
    };
  },
  trelloGetMemorySettings: async (userId) => {
    // Mock implementation
    return {
      success: true,
      settings: {
        userId: userId,
        ingestionEnabled: true,
        syncFrequency: 'hourly',
        dataRetentionDays: 365,
        includeBoards: [],
        excludeBoards: [],
        includeArchivedBoards: false,
        includeCards: true,
        includeLists: true,
        includeMembers: true,
        includeChecklists: true,
        includeLabels: true,
        includeAttachments: true,
        includeActivities: true,
        maxCardsPerSync: 1000,
        maxActivitiesPerSync: 500,
        syncArchivedCards: false,
        syncCardAttachments: true,
        indexCardContent: true,
        searchEnabled: true,
        semanticSearchEnabled: true,
        metadataExtractionEnabled: true,
        boardTrackingEnabled: true,
        memberAnalysisEnabled: true,
        lastSyncTimestamp: new Date(Date.now() - 3600000).toISOString(),
        nextSyncTimestamp: new Date(Date.now() + 3600000).toISOString(),
        syncInProgress: false,
        errorMessage: null,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString()
      }
    };
  },
  trelloUpdateMemorySettings: async (userId, settings) => {
    // Mock implementation
    return {
      success: true,
      settings: { ...settings, updatedAt: new Date().toISOString() }
    };
  },
  trelloStartIngestion: async (userId, apiKey, oauthToken, boardIds, forceSync) => {
    // Mock implementation
    return {
      success: true,
      ingestionResult: {
        boardsIngested: boardIds.length || 2,
        cardsIngested: 25,
        listsIngested: 8,
        membersIngested: 6,
        activitiesIngested: 45,
        checklistsIngested: 12,
        attachmentsIngested: 15,
        totalSizeMb: 2.5,
        batchId: `batch-${Date.now()}`,
        nextSync: new Date(Date.now() + 3600000).toISOString(),
        syncFrequency: 'hourly'
      }
    };
  },
  trelloGetSyncStatus: async (userId) => {
    // Mock implementation
    return {
      success: true,
      memoryStatus: {
        userId: userId,
        ingestionEnabled: true,
        syncFrequency: 'hourly',
        syncInProgress: false,
        lastSyncTimestamp: new Date(Date.now() - 3600000).toISOString(),
        nextSyncTimestamp: new Date(Date.now() + 3600000).toISOString(),
        shouldSyncNow: false,
        errorMessage: null,
        stats: {
          totalBoardsIngested: 12,
          totalCardsIngested: 245,
          totalListsIngested: 48,
          totalMembersIngested: 18,
          totalActivitiesIngested: 892,
          totalChecklistsIngested: 156,
          totalAttachmentsIngested: 234,
          lastIngestionTimestamp: new Date(Date.now() - 3600000).toISOString(),
          totalSizeMb: 15.7,
          failedIngestions: 0,
          lastErrorMessage: null,
          avgCardsPerBoard: 20.4,
          avgProcessingTimeMs: 1250.5
        }
      }
    };
  },
  trelloSearchMemoryCards: async (userId, query, boardId, listId, memberId, labelName, closed, limit) => {
    // Mock implementation
    return {
      success: true,
      cards: [
        {
          id: 'card1',
          name: 'Implement authentication',
          description: 'Add OAuth 2.0 authentication to the application',
          boardId: 'board1',
          boardName: 'Project Alpha',
          listId: 'list1',
          listName: 'To Do',
          closed: false,
          due: new Date(Date.now() + 604800000).toISOString(),
          url: 'https://trello.com/c/card1',
          labels: ['Feature', 'High Priority'],
          members: ['john_doe'],
          commentsCount: 3,
          checklistsCount: 1,
          attachmentsCount: 2,
          dateLastActivity: new Date().toISOString()
        }
      ],
      count: 1
    };
  }
};

// Trello data models
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

interface TrelloMemorySettings {
  userId: string;
  ingestionEnabled: boolean;
  syncFrequency: string;
  dataRetentionDays: number;
  includeBoards: string[];
  excludeBoards: string[];
  includeArchivedBoards: boolean;
  includeCards: boolean;
  includeLists: boolean;
  includeMembers: boolean;
  includeChecklists: boolean;
  includeLabels: boolean;
  includeAttachments: boolean;
  includeActivities: boolean;
  maxCardsPerSync: number;
  maxActivitiesPerSync: number;
  syncArchivedCards: boolean;
  syncCardAttachments: boolean;
  indexCardContent: boolean;
  searchEnabled: boolean;
  semanticSearchEnabled: boolean;
  metadataExtractionEnabled: boolean;
  boardTrackingEnabled: boolean;
  memberAnalysisEnabled: boolean;
  lastSyncTimestamp?: string;
  nextSyncTimestamp?: string;
  syncInProgress: boolean;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Utility functions
const trelloUtils = {
  formatDateTime: (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (error) {
      return dateString;
    }
  },

  formatRelativeTime: (dateString: string): string => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      
      if (diffMins < 1) return 'just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays < 7) return `${diffDays}d ago`;
      
      return date.toLocaleDateString();
    } catch (error) {
      return dateString;
    }
  },

  getLabelColor: (color: string): string => {
    const colorMap: Record<string, string> = {
      'green': 'green',
      'yellow': 'yellow',
      'orange': 'orange',
      'red': 'red',
      'purple': 'purple',
      'blue': 'blue',
      'sky': 'blue',
      'lime': 'green',
      'pink': 'pink',
      'black': 'black',
      'null': 'gray'
    };
    
    return colorMap[color] || 'gray';
  },

  getCardUrl: (cardId: string): string => {
    return `https://trello.com/c/${cardId}`;
  },

  getBoardUrl: (boardId: string): string => {
    return `https://trello.com/b/${boardId}`;
  },

  getDueDateStatus: (dueDate: string, dueComplete: boolean): { status: string; color: string } => {
    if (dueComplete) {
      return { status: 'Complete', color: 'green' };
    }
    
    if (!dueDate) {
      return { status: 'No due date', color: 'gray' };
    }
    
    const now = new Date();
    const due = new Date(dueDate);
    const diffMs = due.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) {
      return { status: `Overdue by ${Math.abs(diffDays)} days`, color: 'red' };
    } else if (diffDays <= 1) {
      return { status: 'Due soon', color: 'orange' };
    } else if (diffDays <= 7) {
      return { status: `Due in ${diffDays} days`, color: 'yellow' };
    } else {
      return { status: `Due in ${diffDays} days`, color: 'green' };
    }
  },

  getProgressPercentage: (checkItemsChecked: number, checkItemsTotal: number): number => {
    return checkItemsTotal > 0 ? Math.round((checkItemsChecked / checkItemsTotal) * 100) : 0;
  }
};

// Main Component
interface TrelloProjectManagementUIProps {
  userId: string;
  apiKey?: string;
  oauthToken?: string;
  height?: string;
  showMemoryControls?: boolean;
  enableRealtimeSync?: boolean;
  onBoardChange?: (board: TrelloBoard) => void;
  onCardChange?: (card: TrelloCard) => void;
  onSettingsChange?: (settings: TrelloMemorySettings) => void;
  className?: string;
}

export const TrelloProjectManagementUI: React.FC<TrelloProjectManagementUIProps> = ({
  userId,
  apiKey,
  oauthToken,
  height = "800px",
  showMemoryControls = true,
  enableRealtimeSync = true,
  onBoardChange,
  onCardChange,
  onSettingsChange,
  className
}) => {
  // State
  const [boards, setBoards] = useState<TrelloBoard[]>([]);
  const [cards, setCards] = useState<TrelloCard[]>([]);
  const [lists, setLists] = useState<TrelloList[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<TrelloBoard | null>(null);
  const [selectedCard, setSelectedCard] = useState<TrelloCard | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<TrelloCard[]>([]);
  const [viewMode, setViewMode] = useState<'boards' | 'cards' | 'lists' | 'timeline'>('boards');
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'cards' | 'members'>('date');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [realtimeEnabled, setRealtimeEnabled] = useState(enableRealtimeSync);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [memorySettings, setMemorySettings] = useState<TrelloMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);

  // Form states
  const [createCardData, setCreateCardData] = useState({
    name: '',
    description: '',
    idList: '',
    due: '',
    idMembers: [] as string[],
    idLabels: [] as string[]
  });

  // Modal disclosures
  const { isOpen: createCardOpen, onOpen: createCardOnOpen, onClose: createCardOnClose } = useDisclosure();
  const { isOpen: cardDetailsOpen, onOpen: cardDetailsOnOpen, onClose: cardDetailsOnClose } = useDisclosure();
  const { isOpen: memorySettingsOpen, onOpen: memorySettingsOnOpen, onClose: memorySettingsOnClose } = useDisclosure();
  const { isOpen: syncStatusOpen, onOpen: syncStatusOnOpen, onClose: syncStatusOnClose } = useDisclosure();

  const toast = useToast();

  // Color mode values
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Fetch functions
  const fetchBoards = useCallback(async () => {
    try {
      setLoading(true);
      const result = await trelloSkills.trelloGetBoards(
        userId,
        apiKey,
        oauthToken,
        'open'
      );
      
      if (result.success) {
        setBoards(result.boards);
        setConnected(true);
      } else {
        setConnected(false);
        toast({
          title: 'Error loading boards',
          description: result.error || 'Failed to load Trello boards',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Trello boards:', error);
      setConnected(false);
      toast({
        title: 'Connection Error',
        description: 'Failed to connect to Trello',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, apiKey, oauthToken, toast]);

  const fetchCards = useCallback(async (boardId: string, listId?: string) => {
    try {
      setLoading(true);
      const result = await trelloSkills.trelloGetCards(
        userId,
        apiKey,
        oauthToken,
        boardId,
        listId,
        'open'
      );
      
      if (result.success) {
        setCards(result.cards);
      } else {
        toast({
          title: 'Error loading cards',
          description: result.error || 'Failed to load Trello cards',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Trello cards:', error);
      toast({
        title: 'Error loading cards',
        description: 'Failed to load cards',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, apiKey, oauthToken, toast]);

  const fetchLists = useCallback(async (boardId: string, includeCards = false) => {
    try {
      setLoading(true);
      const result = await trelloSkills.trelloGetLists(
        userId,
        apiKey,
        oauthToken,
        boardId,
        includeCards
      );
      
      if (result.success) {
        setLists(result.lists);
      } else {
        toast({
          title: 'Error loading lists',
          description: result.error || 'Failed to load Trello lists',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Trello lists:', error);
      toast({
        title: 'Error loading lists',
        description: 'Failed to load lists',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, apiKey, oauthToken, toast]);

  const fetchMemorySettings = useCallback(async () => {
    try {
      const result = await trelloSkills.trelloGetMemorySettings(userId);
      
      if (result.success) {
        setMemorySettings(result.settings);
        onSettingsChange?.(result.settings);
      }
    } catch (error) {
      console.error('Error fetching Trello memory settings:', error);
    }
  }, [userId, onSettingsChange]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const result = await trelloSkills.trelloGetSyncStatus(userId);
      
      if (result.success) {
        setSyncStatus(result.memoryStatus);
      }
    } catch (error) {
      console.error('Error fetching Trello sync status:', error);
    }
  }, [userId]);

  // Effects
  useEffect(() => {
    if (userId && apiKey && oauthToken) {
      fetchBoards();
      fetchMemorySettings();
      fetchSyncStatus();
    }
  }, [userId, apiKey, oauthToken, fetchBoards, fetchMemorySettings, fetchSyncStatus]);

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
        handleSearch(searchQuery);
      } else {
        setSearchResults([]);
      }
    }, 300);
    
    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Event handlers
  const handleBoardSelect = useCallback((board: TrelloBoard) => {
    setSelectedBoard(board);
    setViewMode('cards');
    fetchCards(board.id);
    fetchLists(board.id);
    onBoardChange?.(board);
  }, [fetchCards, fetchLists, onBoardChange]);

  const handleCardSelect = useCallback((card: TrelloCard) => {
    setSelectedCard(card);
    onCardChange?.(card);
    cardDetailsOnOpen();
  }, [onCardChange, cardDetailsOnOpen]);

  const handleCreateCard = useCallback(async () => {
    try {
      setCreateCardData({ ...createCardData });
      
      const result = await trelloSkills.trelloCreateCard(
        userId,
        apiKey,
        oauthToken,
        createCardData.name,
        createCardData.idList,
        createCardData.description,
        createCardData.due,
        createCardData.idMembers,
        createCardData.idLabels
      );
      
      if (result.success) {
        toast({
          title: 'Card Created',
          description: 'Card created successfully',
          status: 'success',
          duration: 3000,
        });
        
        // Refresh cards
        if (selectedBoard) {
          fetchCards(selectedBoard.id);
        }
        
        createCardOnClose();
      } else {
        toast({
          title: 'Create Failed',
          description: result.error || 'Failed to create card',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error creating Trello card:', error);
      toast({
        title: 'Create Error',
        description: 'Failed to create card',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, apiKey, oauthToken, createCardData, selectedBoard, fetchCards, toast, createCardOnClose]);

  const handleSearch = useCallback(async (query: string) => {
    try {
      if (!query || query.trim() === '') {
        setSearchResults([]);
        return;
      }
      
      const result = await trelloSkills.trelloSearchMemoryCards(
        userId,
        query,
        selectedBoard?.id,
        undefined,
        undefined,
        undefined,
        undefined,
        50
      );
      
      if (result.success) {
        setSearchResults(result.cards);
      } else {
        toast({
          title: 'Search Error',
          description: result.error || 'Failed to search cards',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error searching Trello cards:', error);
      toast({
        title: 'Search Error',
        description: 'Failed to search cards',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, selectedBoard, toast]);

  const handleStartIngestion = useCallback(async (boardIds?: string[]) => {
    try {
      setSyncInProgress(true);
      setSyncResult(null);
      
      const result = await trelloSkills.trelloStartIngestion(
        userId,
        apiKey,
        oauthToken,
        boardIds || [],
        false
      );
      
      setSyncResult(result);
      
      if (result.success) {
        // Refresh sync status
        await fetchSyncStatus();
        
        toast({
          title: 'Ingestion Complete',
          description: `Ingested ${result.ingestionResult.boardsIngested} boards and ${result.ingestionResult.cardsIngested} cards`,
          status: 'success',
          duration: 5000,
        });
      } else {
        toast({
          title: 'Ingestion Failed',
          description: result.error || 'Failed to start ingestion',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error starting Trello ingestion:', error);
      toast({
        title: 'Ingestion Error',
        description: 'Failed to start ingestion',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setSyncInProgress(false);
    }
  }, [userId, apiKey, oauthToken, fetchSyncStatus, toast]);

  // Memoized filtered items
  const filteredBoards = useMemo(() => {
    let filtered = boards;
    
    // Sort boards
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'date':
          comparison = new Date(b.dateLastActivity).getTime() - new Date(a.dateLastActivity).getTime();
          break;
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'cards':
          comparison = b.totalCards - a.totalCards;
          break;
        case 'members':
          comparison = b.totalMembers - a.totalMembers;
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [boards, sortBy, sortOrder]);

  const filteredCards = useMemo(() => {
    let filtered = searchQuery ? searchResults : cards;
    
    // Sort cards
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'date':
          comparison = new Date(b.dateLastActivity).getTime() - new Date(a.dateLastActivity).getTime();
          break;
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'due':
          if (!a.due && !b.due) comparison = 0;
          else if (!a.due) comparison = 1;
          else if (!b.due) comparison = -1;
          else comparison = new Date(a.due).getTime() - new Date(b.due).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [cards, searchResults, searchQuery, sortBy, sortOrder]);

  return (
    <Box className={className} height={height} display="flex" borderWidth={1} borderRadius="lg" overflow="hidden">
      <VStack flex={1} spacing={0} align="stretch">
        {/* Header */}
        <HStack 
          p={4} 
          borderBottomWidth={1} 
          bg="trello.dark.50" 
          justify="space-between"
        >
          <HStack spacing={3} flex={1}>
            <Icon as={FiTrello} boxSize={5} color="trello.500" />
            <VStack spacing={0} align="start" flex={1}>
              <HStack spacing={2}>
                <Text fontWeight="bold">Trello Project Management</Text>
                <Badge colorScheme="trello">Projects</Badge>
                {realtimeEnabled && (
                  <Badge colorScheme="green" variant="outline">
                    <Icon as={FiZap} boxSize={3} mr={1} />
                    Live
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="gray.500">
                {connected ? 'Connected to Trello' : 'Not connected'} › {viewMode} view
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Tooltip label="Create Card">
              <IconButton 
                icon={<FiPlus />} 
                variant="ghost" 
                size="sm"
                onClick={createCardOnOpen}
                colorScheme="trello"
                isDisabled={!selectedBoard}
              />
            </Tooltip>
            
            <Tooltip label="Search">
              <IconButton 
                icon={<FiSearch />} 
                variant="ghost" 
                size="sm"
                onClick={() => setSearchQuery(searchQuery)}
              />
            </Tooltip>
            
            <Tooltip label="Refresh">
              <IconButton 
                icon={<FiRefreshCw />} 
                variant="ghost" 
                size="sm"
                onClick={() => {
                  if (viewMode === 'boards') fetchBoards();
                  else if (viewMode === 'cards' && selectedBoard) fetchCards(selectedBoard.id);
                  else if (viewMode === 'lists' && selectedBoard) fetchLists(selectedBoard.id);
                }}
                isLoading={loading}
              />
            </Tooltip>
            
            {showMemoryControls && (
              <>
                <Tooltip label="Memory Settings">
                  <IconButton 
                    icon={<FiSettings />} 
                    variant="ghost" 
                    size="sm"
                    onClick={memorySettingsOnOpen}
                  />
                </Tooltip>
                
                <Tooltip label="Sync Status">
                  <IconButton 
                    icon={<FiDatabase />} 
                    variant="ghost" 
                    size="sm"
                    onClick={syncStatusOnOpen}
                  />
                </Tooltip>
                
                <Tooltip label="Start Ingestion">
                  <IconButton 
                    icon={<FiZap />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => handleStartIngestion()}
                    isLoading={syncInProgress}
                  />
                </Tooltip>
              </>
            )}
            
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

        {/* Toolbar */}
        <HStack p={3} borderBottomWidth={1} bg="gray.50">
          {/* View Mode Tabs */}
          <HStack spacing={1}>
            <Button
              size="sm"
              variant={viewMode === 'boards' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'boards' ? 'trello' : 'gray'}
              onClick={() => setViewMode('boards')}
              leftIcon={<FiGrid />}
            >
              Boards
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'cards' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'cards' ? 'trello' : 'gray'}
              onClick={() => setViewMode('cards')}
              leftIcon={<FiPackage />}
              isDisabled={!selectedBoard}
            >
              Cards
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'lists' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'lists' ? 'trello' : 'gray'}
              onClick={() => setViewMode('lists')}
              leftIcon={<FiList />}
              isDisabled={!selectedBoard}
            >
              Lists
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'timeline' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'timeline' ? 'trello' : 'gray'}
              onClick={() => setViewMode('timeline')}
              leftIcon={<FiCalendar />}
              isDisabled={!selectedBoard}
            >
              Timeline
            </Button>
          </HStack>
          
          <Divider orientation="vertical" h={6} />
          
          {/* Search Input */}
          <Input
            placeholder="Search cards..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
            maxW="300px"
            leftIcon={<FiSearch />}
          />
          
          {/* Sort Controls */}
          <Menu>
            <MenuButton as={Button} variant="ghost" size="sm" rightIcon={<FiChevronDown />}>
              Sort: {sortBy}
            </MenuButton>
            <MenuList>
              <MenuItem onClick={() => setSortBy('date')}>Date</MenuItem>
              <MenuItem onClick={() => setSortBy('name')}>Name</MenuItem>
              {viewMode === 'boards' && (
                <>
                  <MenuItem onClick={() => setSortBy('cards')}>Cards</MenuItem>
                  <MenuItem onClick={() => setSortBy('members')}>Members</MenuItem>
                </>
              )}
              {viewMode === 'cards' && <MenuItem onClick={() => setSortBy('due')}>Due Date</MenuItem>}
              <Divider />
              <MenuItem onClick={() => setSortOrder('desc')}>Newest First</MenuItem>
              <MenuItem onClick={() => setSortOrder('asc')}>Oldest First</MenuItem>
            </MenuList>
          </Menu>
        </HStack>

        {/* Main Content */}
        <HStack flex={1} spacing={0} align="stretch">
          {/* Boards View */}
          {viewMode === 'boards' && (
            <ScrollArea flex={1}>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3, xl: 4 }} spacing={4} p={4}>
                {connected && filteredBoards.length > 0 ? (
                  filteredBoards.map((board) => (
                    <BoardCard
                      key={board.id}
                      board={board}
                      selected={selectedBoard?.id === board.id}
                      onSelect={() => handleBoardSelect(board)}
                      onMemorySync={() => handleStartIngestion([board.id])}
                    />
                  ))
                ) : (
                  <VStack spacing={4} align="center" py={8} w="100%">
                    <Icon as={FiTrello} boxSize={12} color="gray.400" />
                    <Text color="gray.500" textAlign="center" fontSize="lg">
                      {connected ? 'No boards found' : 'Connect to Trello'}
                    </Text>
                    {connected && (
                      <Button
                        size="sm"
                        colorScheme="trello"
                        onClick={() => fetchBoards()}
                      >
                        Refresh
                      </Button>
                    )}
                  </VStack>
                )}
              </SimpleGrid>
            </ScrollArea>
          )}

          {/* Cards View */}
          {viewMode === 'cards' && selectedBoard && (
            <HStack flex={1} spacing={0}>
              {/* Lists Sidebar */}
              <Box w="250px" borderRightWidth={1} bg="gray.50" p={3}>
                <VStack spacing={2} align="stretch">
                  <Text fontSize="sm" fontWeight="medium" color="gray.700">
                    Lists ({lists.length})
                  </Text>
                  {lists.map((list) => (
                    <Box
                      key={list.id}
                      p={2}
                      bg="white"
                      borderRadius="md"
                      cursor="pointer"
                      _hover={{ bg: 'gray.100' }}
                      onClick={() => fetchCards(selectedBoard.id, list.id)}
                    >
                      <Text fontSize="sm" fontWeight="medium">
                        {list.name}
                      </Text>
                      <Text fontSize="xs" color="gray.500">
                        {list.totalCards} cards
                      </Text>
                    </Box>
                  ))}
                </VStack>
              </Box>
              
              {/* Cards Grid */}
              <ScrollArea flex={1}>
                <VStack spacing={4} align="stretch" p={4}>
                  {filteredCards.length > 0 ? (
                    filteredCards.map((card) => (
                      <CardCard
                        key={card.id}
                        card={card}
                        onSelect={() => handleCardSelect(card)}
                        onEdit={() => {
                          setCreateCardData({
                            name: card.name,
                            description: card.description,
                            idList: card.idList,
                            due: card.due || '',
                            idMembers: card.members.map(m => m.id),
                            idLabels: card.labels.map(l => l.id)
                          });
                          createCardOnOpen();
                        }}
                        onMemorySync={() => handleStartIngestion([card.idBoard])}
                      />
                    ))
                  ) : (
                    <VStack spacing={4} align="center" py={8}>
                      <Icon as={FiPackage} boxSize={8} color="gray.400" />
                      <Text color="gray.500" textAlign="center">
                        No cards found
                      </Text>
                    </VStack>
                  )}
                </VStack>
              </ScrollArea>
            </HStack>
          )}

          {/* Lists View */}
          {viewMode === 'lists' && selectedBoard && (
            <ScrollArea flex={1}>
              <VStack spacing={4} align="stretch" p={4}>
                {lists.length > 0 ? (
                  lists.map((list) => (
                    <ListCard
                      key={list.id}
                      list={list}
                      boardId={selectedBoard.id}
                      onSelect={() => fetchCards(selectedBoard.id, list.id)}
                    />
                  ))
                ) : (
                  <VStack spacing={4} align="center" py={8}>
                    <Icon as={FiList} boxSize={8} color="gray.400" />
                    <Text color="gray.500" textAlign="center">
                      No lists found
                    </Text>
                  </VStack>
                )}
              </VStack>
            </ScrollArea>
          )}

          {/* Timeline View */}
          {viewMode === 'timeline' && selectedBoard && (
            <ScrollArea flex={1}>
              <VStack spacing={4} align="stretch" p={4}>
                <Text fontSize="lg" fontWeight="medium">
                  Timeline - {selectedBoard.name}
                </Text>
                <Text color="gray.500">
                  Timeline view coming soon...
                </Text>
              </VStack>
            </ScrollArea>
          )}
        </HStack>
      </VStack>

      {/* Create Card Modal */}
      <Modal 
        isOpen={createCardOpen} 
        onClose={createCardOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiPlus} />
              <Text>Create Card</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>Card Name</FormLabel>
                <Input
                  value={createCardData.name}
                  onChange={(e) => setCreateCardData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter card name"
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={createCardData.description}
                  onChange={(e) => setCreateCardData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Enter card description"
                  h="100px"
                />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>List</FormLabel>
                <Select
                  value={createCardData.idList}
                  onChange={(e) => setCreateCardData(prev => ({ ...prev, idList: e.target.value }))}
                  placeholder="Select a list"
                >
                  {lists.map((list) => (
                    <option key={list.id} value={list.id}>
                      {list.name}
                    </option>
                  ))}
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>Due Date</FormLabel>
                <Input
                  type="datetime-local"
                  value={createCardData.due}
                  onChange={(e) => setCreateCardData(prev => ({ ...prev, due: e.target.value }))}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={createCardOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="trello"
                onClick={handleCreateCard}
                isDisabled={!createCardData.name || !createCardData.idList}
              >
                Create Card
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Card Details Modal */}
      <Modal 
        isOpen={cardDetailsOpen} 
        onClose={cardDetailsOnClose}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiPackage} />
              <Text>{selectedCard?.name || 'Card Details'}</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {selectedCard && (
              <VStack spacing={4} align="stretch">
                {/* Card Header */}
                <HStack justify="space-between" align="start">
                  <VStack align="start" spacing={2} flex={1}>
                    <Text fontSize="sm" fontWeight="medium">Board: {selectedBoard?.name}</Text>
                    <Text fontSize="xs" color="gray.500">
                      Created {trelloUtils.formatRelativeTime(selectedCard.dateLastActivity)}
                    </Text>
                  </VStack>
                  
                  <HStack spacing={1}>
                    <IconButton
                      icon={<FiEdit2 />}
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCreateCardData({
                          name: selectedCard.name,
                          description: selectedCard.description,
                          idList: selectedCard.idList,
                          due: selectedCard.due || '',
                          idMembers: selectedCard.members.map(m => m.id),
                          idLabels: selectedCard.labels.map(l => l.id)
                        });
                        cardDetailsOnClose();
                        createCardOnOpen();
                      }}
                    />
                    <IconButton
                      icon={<FiLink />}
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(trelloUtils.getCardUrl(selectedCard.id), '_blank')}
                    />
                  </HStack>
                </HStack>
                
                <Divider />
                
                {/* Card Content */}
                <Box p={4} bg="gray.50" borderRadius="md">
                  <Text fontSize="sm" whiteSpace="pre-wrap">
                    {selectedCard.description || 'No description'}
                  </Text>
                </Box>
                
                {/* Labels */}
                {selectedCard.labels.length > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Labels</Text>
                    <Wrap>
                      {selectedCard.labels.map((label) => (
                        <WrapItem key={label.id}>
                          <Badge colorScheme={trelloUtils.getLabelColor(label.color)}>
                            {label.name}
                          </Badge>
                        </WrapItem>
                      ))}
                    </Wrap>
                  </VStack>
                )}
                
                {/* Due Date */}
                {selectedCard.due && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Due Date</Text>
                    <Text fontSize="sm" color={trelloUtils.getDueDateStatus(selectedCard.due, selectedCard.dueComplete).color}>
                      {trelloUtils.getDueDateStatus(selectedCard.due, selectedCard.dueComplete).status}
                    </Text>
                  </VStack>
                )}
                
                {/* Members */}
                {selectedCard.members.length > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Members</Text>
                    <HStack>
                      {selectedCard.members.map((member) => (
                        <HStack key={member.id} spacing={2}>
                          <Avatar size="sm" name={member.fullName || member.username} />
                          <Text fontSize="sm">{member.fullName || member.username}</Text>
                        </HStack>
                      ))}
                    </HStack>
                  </VStack>
                )}
                
                {/* Checklists */}
                {selectedCard.checklists.length > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Checklists</Text>
                    {selectedCard.checklists.map((checklist) => (
                      <Box key={checklist.id} p={3} bg="gray.50" borderRadius="md" w="100%">
                        <Text fontSize="sm" fontWeight="medium" mb={2}>
                          {checklist.name}
                        </Text>
                        <Progress
                          value={trelloUtils.getProgressPercentage(
                            checklist.checkItems.filter(item => item.state === 'complete').length,
                            checklist.checkItems.length
                          )}
                          colorScheme="trello"
                          size="sm"
                          mb={2}
                        />
                        <VStack spacing={1} align="stretch">
                          {checklist.checkItems.map((checkItem, index) => (
                            <HStack key={index}>
                              <Icon
                                as={checkItem.state === 'complete' ? FiCheckSquare : FiSquare}
                                color={checkItem.state === 'complete' ? 'green.500' : 'gray.400'}
                              />
                              <Text fontSize="sm">{checkItem.name}</Text>
                            </HStack>
                          ))}
                        </VStack>
                      </Box>
                    ))}
                  </VStack>
                )}
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={cardDetailsOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Memory Settings Modal */}
      <Modal 
        isOpen={memorySettingsOpen} 
        onClose={memorySettingsOnClose}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiDatabase} />
              <Text>Trello Memory Settings</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {memorySettings && (
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
                          <FormLabel htmlFor="trello-ingestion-enabled">
                            Enable Project Memory
                          </FormLabel>
                          <Switch
                            id="trello-ingestion-enabled"
                            isChecked={memorySettings.ingestionEnabled}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, ingestionEnabled: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Sync Frequency</FormLabel>
                          <Select
                            value={memorySettings.syncFrequency}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, syncFrequency: e.target.value } : prev)}
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
                            value={memorySettings.dataRetentionDays}
                            min={1}
                            max={3650}
                            onChange={(value) => setMemorySettings(prev => prev ? { ...prev, dataRetentionDays: parseInt(value) || 365 } : prev)}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Board Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Board Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-archived">
                            Include Archived Boards
                          </FormLabel>
                          <Switch
                            id="trello-include-archived"
                            isChecked={memorySettings.includeArchivedBoards}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeArchivedBoards: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Cards per Sync</FormLabel>
                          <NumberInput
                            value={memorySettings.maxCardsPerSync}
                            min={100}
                            max={10000}
                            onChange={(value) => setMemorySettings(prev => prev ? { ...prev, maxCardsPerSync: parseInt(value) || 1000 } : prev)}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Content Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Content Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-cards">
                            Include Cards
                          </FormLabel>
                          <Switch
                            id="trello-include-cards"
                            isChecked={memorySettings.includeCards}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeCards: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-lists">
                            Include Lists
                          </FormLabel>
                          <Switch
                            id="trello-include-lists"
                            isChecked={memorySettings.includeLists}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeLists: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-members">
                            Include Members
                          </FormLabel>
                          <Switch
                            id="trello-include-members"
                            isChecked={memorySettings.includeMembers}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeMembers: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-checklists">
                            Include Checklists
                          </FormLabel>
                          <Switch
                            id="trello-include-checklists"
                            isChecked={memorySettings.includeChecklists}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeChecklists: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-labels">
                            Include Labels
                          </FormLabel>
                          <Switch
                            id="trello-include-labels"
                            isChecked={memorySettings.includeLabels}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeLabels: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-attachments">
                            Include Attachments
                          </FormLabel>
                          <Switch
                            id="trello-include-attachments"
                            isChecked={memorySettings.includeAttachments}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeAttachments: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="trello-include-activities">
                            Include Activities
                          </FormLabel>
                          <Switch
                            id="trello-include-activities"
                            isChecked={memorySettings.includeActivities}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeActivities: e.target.checked } : prev)}
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
                onClick={memorySettingsOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="trello"
                onClick={() => {
                  if (memorySettings) {
                    trelloSkills.trelloUpdateMemorySettings(userId, memorySettings);
                    onSettingsChange?.(memorySettings);
                  }
                  memorySettingsOnClose();
                }}
                isDisabled={!memorySettings}
              >
                Save Changes
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Sync Status Modal */}
      <Modal 
        isOpen={syncStatusOpen} 
        onClose={syncStatusOnClose}
        size="xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiDatabase} />
              <Text>Trello Sync Status</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {syncStatus && (
              <VStack spacing={6} align="stretch">
                {/* Sync Overview */}
                <HStack justify="space-between" align="center">
                  <Text fontSize="lg" fontWeight="medium">Sync Overview</Text>
                  <HStack>
                    <Badge colorScheme={syncStatus.ingestionEnabled ? 'green' : 'red'}>
                      {syncStatus.ingestionEnabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                    <Badge colorScheme={syncStatus.syncInProgress ? 'yellow' : 'green'}>
                      {syncStatus.syncInProgress ? 'In Progress' : 'Idle'}
                    </Badge>
                  </HStack>
                </HStack>
                
                <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                  <GridItem>
                    <Box p={4} bg="gray.50" borderRadius="md">
                      <Text fontSize="sm" color="gray.600">Last Sync</Text>
                      <Text fontSize="lg" fontWeight="medium">
                        {syncStatus.lastSyncTimestamp ? trelloUtils.formatRelativeTime(syncStatus.lastSyncTimestamp) : 'Never'}
                      </Text>
                    </Box>
                  </GridItem>
                  <GridItem>
                    <Box p={4} bg="gray.50" borderRadius="md">
                      <Text fontSize="sm" color="gray.600">Next Sync</Text>
                      <Text fontSize="lg" fontWeight="medium">
                        {syncStatus.nextSyncTimestamp ? trelloUtils.formatRelativeTime(syncStatus.nextSyncTimestamp) : 'Manual'}
                      </Text>
                    </Box>
                  </GridItem>
                </Grid>
                
                {/* Statistics */}
                <VStack align="start" spacing={4}>
                  <Text fontSize="lg" fontWeight="medium">Ingestion Statistics</Text>
                  <Grid templateColumns="repeat(3, 1fr)" gap={4}>
                    <GridItem>
                      <Box p={3} bg="blue.50" borderRadius="md" textAlign="center">
                        <Icon as={FiGrid} boxSize={6} color="blue.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="blue.700">
                          {syncStatus.stats.totalBoardsIngested}
                        </Text>
                        <Text fontSize="sm" color="blue.600">Boards</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="green.50" borderRadius="md" textAlign="center">
                        <Icon as={FiPackage} boxSize={6} color="green.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="green.700">
                          {syncStatus.stats.totalCardsIngested}
                        </Text>
                        <Text fontSize="sm" color="green.600">Cards</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="purple.50" borderRadius="md" textAlign="center">
                        <Icon as={FiList} boxSize={6} color="purple.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="purple.700">
                          {syncStatus.stats.totalListsIngested}
                        </Text>
                        <Text fontSize="sm" color="purple.600">Lists</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="orange.50" borderRadius="md" textAlign="center">
                        <Icon as={FiUsers} boxSize={6} color="orange.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="orange.700">
                          {syncStatus.stats.totalMembersIngested}
                        </Text>
                        <Text fontSize="sm" color="orange.600">Members</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="teal.50" borderRadius="md" textAlign="center">
                        <Icon as={FiActivity} boxSize={6} color="teal.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="teal.700">
                          {syncStatus.stats.totalActivitiesIngested}
                        </Text>
                        <Text fontSize="sm" color="teal.600">Activities</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="pink.50" borderRadius="md" textAlign="center">
                        <Icon as={FiFileText} boxSize={6} color="pink.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="pink.700">
                          {syncStatus.stats.totalAttachmentsIngested}
                        </Text>
                        <Text fontSize="sm" color="pink.600">Attachments</Text>
                      </Box>
                    </GridItem>
                  </Grid>
                </VStack>
                
                {/* Sync Result */}
                {syncResult && (
                  <Alert status="success" borderRadius="md">
                    <AlertIcon />
                    <AlertTitle>Sync Completed Successfully</AlertTitle>
                    <AlertDescription>
                      Batch ID: {syncResult.ingestionResult?.batchId}
                    </AlertDescription>
                  </Alert>
                )}
                
                {syncStatus.errorMessage && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    <AlertTitle>Sync Error</AlertTitle>
                    <AlertDescription>
                      {syncStatus.errorMessage}
                    </AlertDescription>
                  </Alert>
                )}
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={syncStatusOnClose}
              >
                Close
              </Button>
              
              <Button
                colorScheme="trello"
                onClick={() => {
                  handleStartIngestion();
                }}
                isLoading={syncInProgress}
                leftIcon={<FiZap />}
              >
                Start Ingestion
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

// Card Components
const BoardCard: React.FC<{
  board: TrelloBoard;
  selected: boolean;
  onSelect: () => void;
  onMemorySync: () => void;
}> = ({ board, selected, onSelect, onMemorySync }) => {
  const bgColor = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  
  return (
    <Card
      bg={bgColor}
      borderWidth={1}
      borderColor={selected ? 'trello.500' : borderColor}
      boxShadow={selected ? 'md' : 'sm'}
      cursor="pointer"
      onClick={onSelect}
      _hover={{ transform: 'translateY(-2px)', boxShadow: 'md' }}
      transition="all 0.2s"
    >
      <CardBody>
        <VStack spacing={3} align="start">
          <HStack justify="space-between" w="100%">
            <Text fontSize="md" fontWeight="bold" noOfLines={2}>
              {board.name}
            </Text>
            {board.starred && <Icon as={FiStar} color="yellow.500" />}
          </HStack>
          
          <Text fontSize="sm" color="gray.600" noOfLines={2}>
            {board.description || 'No description'}
          </Text>
          
          <HStack justify="space-between" w="100%">
            <HStack spacing={3} fontSize="xs" color="gray.500">
              <HStack spacing={1}>
                <Icon as={FiPackage} boxSize={3} />
                <Text>{board.totalCards}</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiList} boxSize={3} />
                <Text>{board.totalLists}</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiUsers} boxSize={3} />
                <Text>{board.totalMembers}</Text>
              </HStack>
            </HStack>
            
            <HStack spacing={1}>
              {board.pinned && <Icon as={FiFlag} color="red.500" boxSize={3} />}
              {board.subscribed && <Icon as={FiBell} color="blue.500" boxSize={3} />}
            </HStack>
          </HStack>
          
          <HStack justify="space-between" w="100%">
            <Text fontSize="xs" color="gray.500">
              {trelloUtils.formatRelativeTime(board.dateLastActivity)}
            </Text>
            
            <Tooltip label="Sync to Memory">
              <IconButton
                icon={<FiDatabase />}
                variant="ghost"
                size="xs"
                colorScheme="trello"
                onClick={(e) => {
                  e.stopPropagation();
                  onMemorySync();
                }}
              />
            </Tooltip>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

const CardCard: React.FC<{
  card: TrelloCard;
  selected: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onMemorySync: () => void;
}> = ({ card, selected, onSelect, onEdit, onMemorySync }) => {
  const bgColor = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  
  const dueStatus = card.due ? trelloUtils.getDueDateStatus(card.due, card.dueComplete) : null;
  const progressPercentage = trelloUtils.getProgressPercentage(card.badges.checkItemsChecked, card.badges.checkItems);
  
  return (
    <Card
      bg={bgColor}
      borderWidth={1}
      borderColor={selected ? 'trello.500' : borderColor}
      boxShadow={selected ? 'md' : 'sm'}
      cursor="pointer"
      onClick={onSelect}
      _hover={{ transform: 'translateY(-1px)', boxShadow: 'md' }}
      transition="all 0.2s"
    >
      <CardBody p={4}>
        <VStack spacing={3} align="start">
          {/* Labels */}
          {card.labels.length > 0 && (
            <Wrap spacing={1}>
              {card.labels.map((label) => (
                <WrapItem key={label.id}>
                  <Badge colorScheme={trelloUtils.getLabelColor(label.color)} size="sm">
                    {label.name}
                  </Badge>
                </WrapItem>
              ))}
            </Wrap>
          )}
          
          {/* Card Name */}
          <Text fontSize="md" fontWeight="medium" noOfLines={2}>
            {card.name}
          </Text>
          
          {/* Description */}
          {card.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {card.description}
            </Text>
          )}
          
          {/* Progress Bar */}
          {card.badges.checkItems > 0 && (
            <Box w="100%">
              <Progress
                value={progressPercentage}
                colorScheme="trello"
                size="sm"
              />
              <Text fontSize="xs" color="gray.500" mt={1}>
                {card.badges.checkItemsChecked}/{card.badges.checkItems} complete
              </Text>
            </Box>
          )}
          
          {/* Due Date */}
          {dueStatus && (
            <HStack>
              <Icon as={FiCalendar} boxSize={3} color={dueStatus.color} />
              <Text fontSize="xs" color={dueStatus.color}>
                {dueStatus.status}
              </Text>
            </HStack>
          )}
          
          {/* Footer */}
          <HStack justify="space-between" w="100%">
            <HStack spacing={2} fontSize="xs" color="gray.500">
              {card.badges.comments > 0 && (
                <HStack spacing={1}>
                  <Icon as={FiMessageSquare} boxSize={3} />
                  <Text>{card.badges.comments}</Text>
                </HStack>
              )}
              {card.badges.attachments > 0 && (
                <HStack spacing={1}>
                  <Icon as={FiPaperclip} boxSize={3} />
                  <Text>{card.badges.attachments}</Text>
                </HStack>
              )}
              {card.members.length > 0 && (
                <HStack spacing={1}>
                  <Icon as={FiUser} boxSize={3} />
                  <Text>{card.members.length}</Text>
                </HStack>
              )}
            </HStack>
            
            <HStack spacing={1}>
              {card.subscribed && <Icon as={FiBell} color="blue.500" boxSize={3} />}
              <Tooltip label="Edit Card">
                <IconButton
                  icon={<FiEdit2 />}
                  variant="ghost"
                  size="xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit();
                  }}
                />
              </Tooltip>
              <Tooltip label="Sync to Memory">
                <IconButton
                  icon={<FiDatabase />}
                  variant="ghost"
                  size="xs"
                  colorScheme="trello"
                  onClick={(e) => {
                    e.stopPropagation();
                    onMemorySync();
                  }}
                />
              </Tooltip>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

const ListCard: React.FC<{
  list: TrelloList;
  boardId: string;
  onSelect: () => void;
}> = ({ list, boardId, onSelect }) => {
  const bgColor = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  
  return (
    <Card
      bg={bgColor}
      borderWidth={1}
      borderColor={borderColor}
      cursor="pointer"
      onClick={onSelect}
      _hover={{ bg: 'gray.50' }}
      transition="all 0.2s"
    >
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <Text fontSize="md" fontWeight="medium">
              {list.name}
            </Text>
            <HStack spacing={4} fontSize="sm" color="gray.500">
              <HStack spacing={1}>
                <Icon as={FiPackage} boxSize={4} />
                <Text>{list.totalCards} cards</Text>
              </HStack>
              {list.subscribed && (
                <HStack spacing={1}>
                  <Icon as={FiBell} boxSize={4} />
                  <Text>Subscribed</Text>
                </HStack>
              )}
            </HStack>
          </VStack>
          
          <IconButton
            icon={<FiChevronRight />}
            variant="ghost"
            size="sm"
          />
        </HStack>
      </CardBody>
    </Card>
  );
};

// Mock ScrollArea component
const ScrollArea: React.FC<{ children: React.ReactNode; flex?: number }> = ({ children, flex = 1 }) => (
  <Box flex={flex} overflowY="auto">
    {children}
  </Box>
);

// Mock Accordion components
const Accordion: React.FC<{ children: React.ReactNode; allowToggle?: boolean; defaultIndex?: number[] }> = ({ children }) => (
  <Box>{children}</Box>
);

const AccordionItem: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box>{children}</Box>
);

const AccordionButton: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box>{children}</Box>
);

const AccordionPanel: React.FC<{ children: React.ReactNode; pb?: number }> = ({ children }) => (
  <Box>{children}</Box>
);

const AccordionIcon: React.FC = () => <span>▼</span>;

export default TrelloProjectManagementUI;