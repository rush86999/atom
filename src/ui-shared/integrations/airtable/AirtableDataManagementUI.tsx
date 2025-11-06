/**
 * Airtable Data Management UI
 * Complete Airtable data management interface
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
  Container,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Code,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Tag,
  TagLabel,
  TagLeftIcon,
  Checkbox,
  CheckboxGroup,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  RangeSlider,
  RangeSliderTrack,
  RangeSliderFilledTrack,
  RangeSliderThumb,
  useBreakpointValue
} from '@chakra-ui/react';
import {
  FiDatabase,
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
  FiGrid,
  FiList,
  FiEye,
  FiEdit2,
  FiTrash2,
  FiDownload,
  FiUpload,
  FiCopy,
  FiLink,
  FiBarChart2,
  FiColumns,
  FiFolder,
  FiFolderOpen,
  FiMoreHorizontal,
  FiCpu,
  FiZap,
  FiActivity,
  FiTrendingUp,
  FiLayers,
  FiTable,
  FiAlignLeft,
  FiAlignCenter,
  FiAlignRight,
  FiBold,
  FiItalic,
  FiUnderline,
  FiType,
  FiHash,
  FiDollarSign,
  FiPercent,
  FiCheckSquare,
  FiSquare,
  FiPaperclip,
  FiImage,
  FiVideo,
  FiMusic,
  FiArchive,
  FiLock,
  FiUnlock,
  FiKey,
  FiShield,
  FiAlertCircle,
  FiInfo,
  FiHelpCircle,
  FiChevronDown,
  FiChevronRight,
  FiChevronUp,
  FiChevronLeft,
  FiArrowUp,
  FiArrowDown,
  FiCornerUpLeft,
  FiCornerUpRight,
  FiCornerDownLeft,
  FiCornerDownRight,
  FiMove,
  FiPackage,
  FiBox,
  FiInbox,
  FiSend,
  FiShare2,
  FiBookmark,
  FiStar,
  FiFlag,
  FiBell,
  FiMessageSquare,
  FiFilter as FiFilterIcon
} from 'react-icons/fi';

// Mock Airtable skills (would be imported from actual skills)
const airtableSkills = {
  airtableGetBases: async (userId, apiKey) => {
    // Mock implementation
    return {
      success: true,
      bases: [
        {
          id: 'base1',
          name: 'Product Development',
          permission_level: 'owner',
          sharing: 'workspace',
          created_time: new Date(Date.now() - 86400000 * 30).toISOString(),
          last_modified_time: new Date(Date.now() - 86400000).toISOString(),
          base_icon_url: '',
          base_color_theme: 'blue',
          workspace_id: 'ws1',
          workspace_name: 'Product Team',
          total_tables: 8,
          total_records: 2450,
          total_fields: 65,
          total_views: 24,
          total_collaborators: 12,
          collaboration: { users: [], groups: [] }
        },
        {
          id: 'base2',
          name: 'Marketing Campaigns',
          permission_level: 'editor',
          sharing: 'workspace',
          created_time: new Date(Date.now() - 86400000 * 60).toISOString(),
          last_modified_time: new Date(Date.now() - 3600000 * 2).toISOString(),
          base_icon_url: '',
          base_color_theme: 'green',
          workspace_id: 'ws1',
          workspace_name: 'Product Team',
          total_tables: 5,
          total_records: 1240,
          total_fields: 42,
          total_views: 15,
          total_collaborators: 8,
          collaboration: { users: [], groups: [] }
        }
      ]
    };
  },
  airtableGetTables: async (userId, apiKey, baseId) => {
    // Mock implementation
    return {
      success: true,
      tables: [
        {
          id: 'table1',
          name: 'Features',
          primary_field_id: 'field1',
          primary_field_name: 'Feature Name',
          description: 'Product feature tracking',
          records_count: 125,
          views_count: 6,
          fields: [
            { id: 'field1', name: 'Feature Name', type: 'single_line_text' },
            { id: 'field2', name: 'Status', type: 'single_select' },
            { id: 'field3', name: 'Priority', type: 'single_select' },
            { id: 'field4', name: 'Due Date', type: 'date' },
            { id: 'field5', name: 'Assigned To', type: 'multiple_record_links' }
          ],
          views: [
            { id: 'view1', name: 'All Features', type: 'grid' },
            { id: 'view2', name: 'Sprint Backlog', type: 'kanban' },
            { id: 'view3', name: 'Timeline', type: 'calendar' }
          ],
          created_time: new Date(Date.now() - 86400000 * 15).toISOString(),
          last_modified_time: new Date(Date.now() - 3600000).toISOString(),
          icon_emoji: '🎯',
          icon_url: ''
        },
        {
          id: 'table2',
          name: 'User Stories',
          primary_field_id: 'field6',
          primary_field_name: 'Story Title',
          description: 'User story management',
          records_count: 340,
          views_count: 4,
          fields: [
            { id: 'field6', name: 'Story Title', type: 'single_line_text' },
            { id: 'field7', name: 'Description', type: 'long_text' },
            { id: 'field8', name: 'Points', type: 'number' },
            { id: 'field9', name: 'Epic', type: 'single_select' },
            { id: 'field10', name: 'Sprint', type: 'single_select' }
          ],
          views: [
            { id: 'view4', name: 'All Stories', type: 'grid' },
            { id: 'view5', name: 'Sprint Board', type: 'kanban' }
          ],
          created_time: new Date(Date.now() - 86400000 * 20).toISOString(),
          last_modified_time: new Date(Date.now() - 7200000).toISOString(),
          icon_emoji: '📝',
          icon_url: ''
        }
      ]
    };
  },
  airtableGetRecords: async (userId, apiKey, baseId, tableId, options = {}) => {
    // Mock implementation
    return {
      success: true,
      records: [
        {
          id: 'record1',
          created_time: new Date(Date.now() - 86400000 * 5).toISOString(),
          fields: {
            'Feature Name': 'Dark Mode Support',
            'Status': 'In Progress',
            'Priority': 'High',
            'Due Date': '2024-02-15',
            'Assigned To': ['user1', 'user2']
          },
          field_values: {
            'Feature Name': 'Dark Mode Support',
            'Status': 'In Progress',
            'Priority': 'High',
            'Due Date': '2024-02-15',
            'Assigned To': ['user1', 'user2']
          },
          table_id: tableId,
          table_name: 'Features',
          base_id: baseId,
          base_name: 'Product Development',
          attachments: [],
          linked_records: [],
          comments_count: 3,
          last_modified_time: new Date(Date.now() - 3600000).toISOString()
        },
        {
          id: 'record2',
          created_time: new Date(Date.now() - 86400000 * 3).toISOString(),
          fields: {
            'Feature Name': 'Real-time Collaboration',
            'Status': 'Planned',
            'Priority': 'Medium',
            'Due Date': '2024-03-01',
            'Assigned To': ['user3']
          },
          field_values: {
            'Feature Name': 'Real-time Collaboration',
            'Status': 'Planned',
            'Priority': 'Medium',
            'Due Date': '2024-03-01',
            'Assigned To': ['user3']
          },
          table_id: tableId,
          table_name: 'Features',
          base_id: baseId,
          base_name: 'Product Development',
          attachments: [
            { id: 'att1', name: 'design.png', type: 'image/png', size: 245760, url: '' }
          ],
          linked_records: [],
          comments_count: 1,
          last_modified_time: new Date(Date.now() - 7200000).toISOString()
        }
      ],
      offset: null,
      total: 2
    };
  },
  airtableCreateRecord: async (userId, apiKey, baseId, tableId, fields) => {
    // Mock implementation
    return {
      success: true,
      record: {
        id: 'newrecord1',
        created_time: new Date().toISOString(),
        fields: fields,
        table_id: tableId,
        base_id: baseId
      }
    };
  },
  airtableSearchRecords: async (userId, apiKey, baseId, tableId, searchQuery, options = {}) => {
    // Mock implementation
    return {
      success: true,
      records: [
        {
          id: 'record1',
          created_time: new Date(Date.now() - 86400000 * 5).toISOString(),
          fields: {
            'Feature Name': 'Dark Mode Support',
            'Status': 'In Progress'
          },
          table_id: tableId,
          table_name: 'Features',
          base_id: baseId
        }
      ],
      total: 1
    };
  },
  airtableGetMemorySettings: async (userId) => {
    // Mock implementation
    return {
      success: true,
      settings: {
        userId: userId,
        ingestionEnabled: true,
        syncFrequency: 'hourly',
        dataRetentionDays: 365,
        includeBases: [],
        excludeBases: [],
        includeArchivedBases: false,
        includeTables: true,
        includeRecords: true,
        includeFields: true,
        includeViews: true,
        includeAttachments: true,
        includeWebhooks: true,
        maxRecordsPerSync: 1000,
        maxTableRecordsPerSync: 500,
        syncDeletedRecords: true,
        syncRecordAttachments: true,
        indexRecordContent: true,
        searchEnabled: true,
        semanticSearchEnabled: true,
        metadataExtractionEnabled: true,
        baseTrackingEnabled: true,
        tableAnalysisEnabled: true,
        fieldAnalysisEnabled: true,
        lastSyncTimestamp: new Date(Date.now() - 3600000).toISOString(),
        nextSyncTimestamp: new Date(Date.now() + 3600000).toISOString(),
        syncInProgress: false,
        errorMessage: null,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString()
      }
    };
  },
  airtableUpdateMemorySettings: async (userId, settings) => {
    // Mock implementation
    return {
      success: true,
      settings: { ...settings, updatedAt: new Date().toISOString() }
    };
  },
  airtableStartIngestion: async (userId, apiKey, baseIds, forceSync) => {
    // Mock implementation
    return {
      success: true,
      ingestionResult: {
        basesIngested: baseIds.length || 2,
        tablesIngested: 13,
        recordsIngested: 3690,
        fieldsIngested: 107,
        viewsIngested: 39,
        webhooksIngested: 4,
        attachmentsIngested: 156,
        totalSizeMb: 18.5,
        batchId: `batch-${Date.now()}`,
        nextSync: new Date(Date.now() + 3600000).toISOString(),
        syncFrequency: 'hourly'
      }
    };
  },
  airtableGetSyncStatus: async (userId) => {
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
          totalBasesIngested: 8,
          totalTablesIngested: 24,
          totalRecordsIngested: 14520,
          totalFieldsIngested: 286,
          totalViewsIngested: 72,
          totalWebhooksIngested: 12,
          totalAttachmentsIngested: 892,
          lastIngestionTimestamp: new Date(Date.now() - 3600000).toISOString(),
          totalSizeMb: 45.7,
          failedIngestions: 0,
          lastErrorMessage: null,
          avgRecordsPerTable: 605,
          avgFieldsPerTable: 11.9,
          avgProcessingTimeMs: 2450.5
        }
      }
    };
  },
  airtableSearchMemoryBases: async (userId, query, sharing, limit) => {
    // Mock implementation
    return {
      success: true,
      bases: [
        {
          id: 'base1',
          user_id: userId,
          base_id: 'base1',
          name: 'Product Development',
          permission_level: 'owner',
          sharing: 'workspace',
          created_time: new Date(Date.now() - 86400000 * 30).toISOString(),
          last_modified_time: new Date(Date.now() - 86400000).toISOString(),
          total_tables: 8,
          total_records: 2450,
          processed_at: new Date().toISOString()
        }
      ],
      count: 1
    };
  },
  airtableSearchMemoryRecords: async (userId, query, baseId, tableId, limit) => {
    // Mock implementation
    return {
      success: true,
      records: [
        {
          id: 'record1',
          user_id: userId,
          record_id: 'record1',
          table_id: tableId || 'table1',
          table_name: 'Features',
          base_id: baseId || 'base1',
          base_name: 'Product Development',
          created_time: new Date(Date.now() - 86400000 * 5).toISOString(),
          fields: {
            'Feature Name': 'Dark Mode Support',
            'Status': 'In Progress'
          },
          search_content: 'Dark Mode Support In Progress',
          processed_at: new Date().toISOString()
        }
      ],
      count: 1
    };
  }
};

// Airtable data models
interface AirtableBase {
  id: string;
  name: string;
  permission_level: string;
  sharing: string;
  created_time: string;
  last_modified_time: string;
  base_icon_url: string;
  base_color_theme: string;
  workspace_id: string;
  workspace_name: string;
  total_tables: number;
  total_records: number;
  total_fields: number;
  total_views: number;
  total_collaborators: number;
  collaboration: any;
}

interface AirtableTable {
  id: string;
  name: string;
  primary_field_id: string;
  primary_field_name: string;
  description: string;
  records_count: number;
  views_count: number;
  fields: any[];
  views: any[];
  created_time: string;
  last_modified_time: string;
  icon_emoji: string;
  icon_url: string;
}

interface AirtableField {
  id: string;
  name: string;
  type: string;
  description: string;
  options: any;
  required: boolean;
  unique: boolean;
  hidden: boolean;
  formula: string;
  validation: any;
  lookup: any;
  rollup: any;
  multiple_record_links: any;
}

interface AirtableView {
  id: string;
  name: string;
  type: string;
  personal: boolean;
  description: string;
  filters: any;
  sorts: any;
  field_options: any;
}

interface AirtableRecord {
  id: string;
  created_time: string;
  fields: Record<string, any>;
  field_values: Record<string, any>;
  table_id: string;
  table_name: string;
  base_id: string;
  base_name: string;
  attachments: any[];
  linked_records: any[];
  comments_count: number;
  last_modified_time: string;
}

interface AirtableMemorySettings {
  userId: string;
  ingestionEnabled: boolean;
  syncFrequency: string;
  dataRetentionDays: number;
  includeBases: string[];
  excludeBases: string[];
  includeArchivedBases: boolean;
  includeTables: boolean;
  includeRecords: boolean;
  includeFields: boolean;
  includeViews: boolean;
  includeAttachments: boolean;
  includeWebhooks: boolean;
  maxRecordsPerSync: number;
  maxTableRecordsPerSync: number;
  syncDeletedRecords: boolean;
  syncRecordAttachments: boolean;
  indexRecordContent: boolean;
  searchEnabled: boolean;
  semanticSearchEnabled: boolean;
  metadataExtractionEnabled: boolean;
  baseTrackingEnabled: boolean;
  tableAnalysisEnabled: boolean;
  fieldAnalysisEnabled: boolean;
  lastSyncTimestamp?: string;
  nextSyncTimestamp?: string;
  syncInProgress: boolean;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Utility functions
const airtableUtils = {
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

  getFieldTypeIcon: (fieldType: string) => {
    const iconMap: Record<string, any> = {
      'single_line_text': FiAlignLeft,
      'long_text': FiAlignLeft,
      'rich_text': FiAlignLeft,
      'email': FiAlignLeft,
      'url': FiLink,
      'number': FiHash,
      'percent': FiPercent,
      'currency': FiDollarSign,
      'rating': FiStar,
      'duration': FiClock,
      'date': FiCalendar,
      'datetime': FiCalendar,
      'checkbox': FiCheckSquare,
      'single_select': FiTag,
      'multiple_selects': FiTag,
      'multiple_record_links': FiLink,
      'lookup': FiSearch,
      'rollup': FiBarChart2,
      'formula': FiCpu,
      'attachment': FiPaperclip,
      'created_time': FiClock,
      'modified_time': FiClock,
      'created_by': FiUser,
      'modified_by': FiUser,
      'barcode': FiHash,
      'default': FiType
    };
    
    return iconMap[fieldType] || iconMap['default'];
  },

  getFieldTypeColor: (fieldType: string): string => {
    const colorMap: Record<string, string> = {
      'single_line_text': 'blue',
      'long_text': 'blue',
      'rich_text': 'blue',
      'email': 'blue',
      'url': 'blue',
      'number': 'green',
      'percent': 'green',
      'currency': 'green',
      'rating': 'yellow',
      'duration': 'purple',
      'date': 'orange',
      'datetime': 'orange',
      'checkbox': 'teal',
      'single_select': 'pink',
      'multiple_selects': 'pink',
      'multiple_record_links': 'indigo',
      'lookup': 'cyan',
      'rollup': 'red',
      'formula': 'gray',
      'attachment': 'yellow',
      'created_time': 'blue',
      'modified_time': 'blue',
      'created_by': 'green',
      'modified_by': 'green',
      'barcode': 'gray',
      'default': 'gray'
    };
    
    return colorMap[fieldType] || colorMap['default'];
  },

  getViewTypeIcon: (viewType: string) => {
    const iconMap: Record<string, any> = {
      'grid': FiGrid,
      'form': FiFileText,
      'kanban': FiColumns,
      'gallery': FiImage,
      'calendar': FiCalendar,
      'gantt': FiBarChart2,
      'timeline': FiBarChart2,
      'default': FiGrid
    };
    
    return iconMap[viewType] || iconMap['default'];
  },

  getViewTypeColor: (viewType: string): string => {
    const colorMap: Record<string, string> = {
      'grid': 'blue',
      'form': 'green',
      'kanban': 'orange',
      'gallery': 'purple',
      'calendar': 'red',
      'gantt': 'yellow',
      'timeline': 'cyan',
      'default': 'gray'
    };
    
    return colorMap[viewType] || colorMap['default'];
  },

  formatFileSize: (sizeInBytes: number): string => {
    if (sizeInBytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(sizeInBytes) / Math.log(k));
    
    return parseFloat((sizeInBytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  getPermissionLevelColor: (permissionLevel: string): string => {
    const colorMap: Record<string, string> = {
      'owner': 'red',
      'creator': 'orange',
      'editor': 'green',
      'commenter': 'blue',
      'reader': 'gray',
      'default': 'gray'
    };
    
    return colorMap[permissionLevel] || colorMap['default'];
  },

  getSharingIcon: (sharing: string) => {
    const iconMap: Record<string, any> = {
      'workspace': FiUsers,
      'private': FiLock,
      'shared': FiShare2,
      'public': FiUnlock,
      'default': FiLock
    };
    
    return iconMap[sharing] || iconMap['default'];
  }
};

// Main Component
interface AirtableDataManagementUIProps {
  userId: string;
  apiKey?: string;
  height?: string;
  showMemoryControls?: boolean;
  enableRealtimeSync?: boolean;
  onBaseChange?: (base: AirtableBase) => void;
  onTableChange?: (table: AirtableTable) => void;
  onRecordChange?: (record: AirtableRecord) => void;
  onSettingsChange?: (settings: AirtableMemorySettings) => void;
  className?: string;
}

export const AirtableDataManagementUI: React.FC<AirtableDataManagementUIProps> = ({
  userId,
  apiKey,
  height = "800px",
  showMemoryControls = true,
  enableRealtimeSync = true,
  onBaseChange,
  onTableChange,
  onRecordChange,
  onSettingsChange,
  className
}) => {
  // State
  const [bases, setBases] = useState<AirtableBase[]>([]);
  const [tables, setTables] = useState<AirtableTable[]>([]);
  const [fields, setFields] = useState<AirtableField[]>([]);
  const [views, setViews] = useState<AirtableView[]>([]);
  const [records, setRecords] = useState<AirtableRecord[]>([]);
  const [selectedBase, setSelectedBase] = useState<AirtableBase | null>(null);
  const [selectedTable, setSelectedTable] = useState<AirtableTable | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<AirtableRecord | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<AirtableRecord[]>([]);
  const [baseSearchResults, setBaseSearchResults] = useState<AirtableBase[]>([]);
  const [viewMode, setViewMode] = useState<'bases' | 'tables' | 'records' | 'schema' | 'analytics'>('bases');
  const [sortBy, setSortBy] = useState<'name' | 'records' | 'tables' | 'modified'>('modified');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [realtimeEnabled, setRealtimeEnabled] = useState(enableRealtimeSync);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [memorySettings, setMemorySettings] = useState<AirtableMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [recordLoading, setRecordLoading] = useState(false);

  // Form states
  const [createRecordData, setCreateRecordData] = useState({
    fields: {} as Record<string, any>
  });

  // Modal disclosures
  const { isOpen: createRecordOpen, onOpen: createRecordOnOpen, onClose: createRecordOnClose } = useDisclosure();
  const { isOpen: recordDetailsOpen, onOpen: recordDetailsOnOpen, onClose: recordDetailsOnClose } = useDisclosure();
  const { isOpen: memorySettingsOpen, onOpen: memorySettingsOnOpen, onClose: memorySettingsOnClose } = useDisclosure();
  const { isOpen: syncStatusOpen, onOpen: syncStatusOnOpen, onClose: syncStatusOnClose } = useDisclosure();
  const { isOpen: schemaModalOpen, onOpen: schemaModalOnOpen, onClose: schemaModalOnClose } = useDisclosure();

  const toast = useToast();

  // Color mode values
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Responsive values
  const isMobile = useBreakpointValue({ base: true, md: false });
  const gridColumns = useBreakpointValue({ base: 1, sm: 1, md: 2, lg: 3, xl: 4 });

  // Fetch functions
  const fetchBases = useCallback(async () => {
    try {
      setLoading(true);
      const result = await airtableSkills.airtableGetBases(userId, apiKey);
      
      if (result.success) {
        setBases(result.bases);
        setConnected(true);
      } else {
        setConnected(false);
        toast({
          title: 'Error loading bases',
          description: result.error || 'Failed to load Airtable bases',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Airtable bases:', error);
      setConnected(false);
      toast({
        title: 'Connection Error',
        description: 'Failed to connect to Airtable',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, apiKey, toast]);

  const fetchTables = useCallback(async (baseId: string) => {
    try {
      setTableLoading(true);
      const result = await airtableSkills.airtableGetTables(userId, apiKey, baseId);
      
      if (result.success) {
        setTables(result.tables);
      } else {
        toast({
          title: 'Error loading tables',
          description: result.error || 'Failed to load Airtable tables',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Airtable tables:', error);
      toast({
        title: 'Error loading tables',
        description: 'Failed to load tables',
        status: 'error',
      });
    } finally {
      setTableLoading(false);
    }
  }, [userId, apiKey, toast]);

  const fetchRecords = useCallback(async (baseId: string, tableId: string, options: any = {}) => {
    try {
      setRecordLoading(true);
      const result = await airtableSkills.airtableGetRecords(userId, apiKey, baseId, tableId, options);
      
      if (result.success) {
        setRecords(result.records);
      } else {
        toast({
          title: 'Error loading records',
          description: result.error || 'Failed to load Airtable records',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Airtable records:', error);
      toast({
        title: 'Error loading records',
        description: 'Failed to load records',
        status: 'error',
      });
    } finally {
      setRecordLoading(false);
    }
  }, [userId, apiKey, toast]);

  const fetchMemorySettings = useCallback(async () => {
    try {
      const result = await airtableSkills.airtableGetMemorySettings(userId);
      
      if (result.success) {
        setMemorySettings(result.settings);
        onSettingsChange?.(result.settings);
      }
    } catch (error) {
      console.error('Error fetching Airtable memory settings:', error);
    }
  }, [userId, onSettingsChange]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const result = await airtableSkills.airtableGetSyncStatus(userId);
      
      if (result.success) {
        setSyncStatus(result.memoryStatus);
      }
    } catch (error) {
      console.error('Error fetching Airtable sync status:', error);
    }
  }, [userId]);

  // Effects
  useEffect(() => {
    if (userId && apiKey) {
      fetchBases();
      fetchMemorySettings();
      fetchSyncStatus();
    }
  }, [userId, apiKey, fetchBases, fetchMemorySettings, fetchSyncStatus]);

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
        setBaseSearchResults([]);
      }
    }, 300);
    
    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Event handlers
  const handleBaseSelect = useCallback((base: AirtableBase) => {
    setSelectedBase(base);
    setViewMode('tables');
    fetchTables(base.id);
    onBaseChange?.(base);
  }, [fetchTables, onBaseChange]);

  const handleTableSelect = useCallback((table: AirtableTable) => {
    setSelectedTable(table);
    setViewMode('records');
    if (selectedBase) {
      fetchRecords(selectedBase.id, table.id);
    }
    onTableChange?.(table);
  }, [selectedBase, fetchRecords, onTableChange]);

  const handleRecordSelect = useCallback((record: AirtableRecord) => {
    setSelectedRecord(record);
    onRecordChange?.(record);
    recordDetailsOnOpen();
  }, [onRecordChange, recordDetailsOnOpen]);

  const handleCreateRecord = useCallback(async () => {
    try {
      setCreateRecordData({ fields: createRecordData.fields });
      
      if (!selectedBase || !selectedTable) return;
      
      const result = await airtableSkills.airtableCreateRecord(
        userId,
        apiKey,
        selectedBase.id,
        selectedTable.id,
        createRecordData.fields
      );
      
      if (result.success) {
        toast({
          title: 'Record Created',
          description: 'Record created successfully',
          status: 'success',
          duration: 3000,
        });
        
        // Refresh records
        if (selectedBase && selectedTable) {
          fetchRecords(selectedBase.id, selectedTable.id);
        }
        
        createRecordOnClose();
      } else {
        toast({
          title: 'Create Failed',
          description: result.error || 'Failed to create record',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error creating Airtable record:', error);
      toast({
        title: 'Create Error',
        description: 'Failed to create record',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, apiKey, selectedBase, selectedTable, createRecordData.fields, fetchRecords, toast, createRecordOnClose]);

  const handleSearch = useCallback(async (query: string) => {
    try {
      if (!query || query.trim() === '') {
        setSearchResults([]);
        setBaseSearchResults([]);
        return;
      }
      
      if (viewMode === 'records' && selectedBase && selectedTable) {
        const result = await airtableSkills.airtableSearchRecords(
          userId,
          apiKey,
          selectedBase.id,
          selectedTable.id,
          query
        );
        
        if (result.success) {
          setSearchResults(result.records);
        } else {
          toast({
            title: 'Search Error',
            description: result.error || 'Failed to search records',
            status: 'error',
            duration: 5000,
          });
        }
      } else if (viewMode === 'bases') {
        const result = await airtableSkills.airtableSearchMemoryBases(
          userId,
          query
        );
        
        if (result.success) {
          setBaseSearchResults(result.bases);
        } else {
          toast({
            title: 'Search Error',
            description: result.error || 'Failed to search bases',
            status: 'error',
            duration: 5000,
          });
        }
      }
    } catch (error) {
      console.error('Error searching Airtable:', error);
      toast({
        title: 'Search Error',
        description: 'Failed to search',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, apiKey, viewMode, selectedBase, selectedTable, toast]);

  const handleStartIngestion = useCallback(async (baseIds?: string[]) => {
    try {
      setSyncInProgress(true);
      setSyncResult(null);
      
      const result = await airtableSkills.airtableStartIngestion(
        userId,
        apiKey,
        baseIds || [],
        false
      );
      
      setSyncResult(result);
      
      if (result.success) {
        // Refresh sync status
        await fetchSyncStatus();
        
        toast({
          title: 'Ingestion Complete',
          description: `Ingested ${result.ingestionResult.basesIngested} bases and ${result.ingestionResult.tablesIngested} tables`,
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
      console.error('Error starting Airtable ingestion:', error);
      toast({
        title: 'Ingestion Error',
        description: 'Failed to start ingestion',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setSyncInProgress(false);
    }
  }, [userId, apiKey, fetchSyncStatus, toast]);

  // Memoized filtered items
  const filteredBases = useMemo(() => {
    let filtered = searchQuery ? baseSearchResults : bases;
    
    // Sort bases
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'records':
          comparison = b.total_records - a.total_records;
          break;
        case 'tables':
          comparison = b.total_tables - a.total_tables;
          break;
        case 'modified':
          comparison = new Date(b.last_modified_time).getTime() - new Date(a.last_modified_time).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [bases, baseSearchResults, searchQuery, sortBy, sortOrder]);

  const filteredTables = useMemo(() => {
    let filtered = tables;
    
    // Sort tables
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'records':
          comparison = b.records_count - a.records_count;
          break;
        case 'modified':
          comparison = new Date(b.last_modified_time).getTime() - new Date(a.last_modified_time).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [tables, sortBy, sortOrder]);

  const filteredRecords = useMemo(() => {
    let filtered = searchQuery ? searchResults : records;
    
    // Sort records
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          const aName = a.fields[Object.keys(a.fields)[0]] || '';
          const bName = b.fields[Object.keys(b.fields)[0]] || '';
          comparison = aName.localeCompare(bName);
          break;
        case 'modified':
          comparison = new Date(b.last_modified_time).getTime() - new Date(a.last_modified_time).getTime();
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [records, searchResults, searchQuery, sortBy, sortOrder]);

  return (
    <Box className={className} height={height} display="flex" borderWidth={1} borderRadius="lg" overflow="hidden">
      <VStack flex={1} spacing={0} align="stretch">
        {/* Header */}
        <HStack 
          p={4} 
          borderBottomWidth={1} 
          bg="airtable.green.50" 
          justify="space-between"
        >
          <HStack spacing={3} flex={1}>
            <Icon as={FiDatabase} boxSize={5} color="airtable.500" />
            <VStack spacing={0} align="start" flex={1}>
              <HStack spacing={2}>
                <Text fontWeight="bold">Airtable Data Management</Text>
                <Badge colorScheme="airtable">Bases</Badge>
                {realtimeEnabled && (
                  <Badge colorScheme="green" variant="outline">
                    <Icon as={FiZap} boxSize={3} mr={1} />
                    Live
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="gray.500">
                {connected ? 'Connected to Airtable' : 'Not connected'} › {viewMode} view
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Tooltip label="Create Record">
              <IconButton 
                icon={<FiPlus />} 
                variant="ghost" 
                size="sm"
                onClick={createRecordOnOpen}
                colorScheme="airtable"
                isDisabled={!selectedTable}
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
                  if (viewMode === 'bases') fetchBases();
                  else if (viewMode === 'tables' && selectedBase) fetchTables(selectedBase.id);
                  else if (viewMode === 'records' && selectedBase && selectedTable) fetchRecords(selectedBase.id, selectedTable.id);
                }}
                isLoading={loading || tableLoading || recordLoading}
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
              variant={viewMode === 'bases' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'bases' ? 'airtable' : 'gray'}
              onClick={() => setViewMode('bases')}
              leftIcon={<FiDatabase />}
            >
              Bases
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'tables' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'tables' ? 'airtable' : 'gray'}
              onClick={() => setViewMode('tables')}
              leftIcon={<FiGrid />}
              isDisabled={!selectedBase}
            >
              Tables
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'records' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'records' ? 'airtable' : 'gray'}
              onClick={() => setViewMode('records')}
              leftIcon={<FiList />}
              isDisabled={!selectedTable}
            >
              Records
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'schema' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'schema' ? 'airtable' : 'gray'}
              onClick={() => setViewMode('schema')}
              leftIcon={<FiLayers />}
              isDisabled={!selectedTable}
            >
              Schema
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'analytics' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'analytics' ? 'airtable' : 'gray'}
              onClick={() => setViewMode('analytics')}
              leftIcon={<FiBarChart2 />}
              isDisabled={!selectedBase}
            >
              Analytics
            </Button>
          </HStack>
          
          <Divider orientation="vertical" h={6} />
          
          {/* Search Input */}
          <Input
            placeholder={viewMode === 'records' ? "Search records..." : viewMode === 'bases' ? "Search bases..." : "Search..."}
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
              <MenuItem onClick={() => setSortBy('name')}>Name</MenuItem>
              {viewMode === 'bases' && (
                <>
                  <MenuItem onClick={() => setSortBy('records')}>Records</MenuItem>
                  <MenuItem onClick={() => setSortBy('tables')}>Tables</MenuItem>
                </>
              )}
              {viewMode === 'tables' && <MenuItem onClick={() => setSortBy('records')}>Records</MenuItem>}
              <MenuItem onClick={() => setSortBy('modified')}>Modified</MenuItem>
              <Divider />
              <MenuItem onClick={() => setSortOrder('desc')}>Newest First</MenuItem>
              <MenuItem onClick={() => setSortOrder('asc')}>Oldest First</MenuItem>
            </MenuList>
          </Menu>
        </HStack>

        {/* Main Content */}
        <VStack flex={1} spacing={0} align="stretch" overflow="hidden">
          {/* Breadcrumb */}
          {(selectedBase || selectedTable) && (
            <HStack px={4} py={2} bg="gray.50" borderBottomWidth={1}>
              <HStack spacing={2} flex={1} overflow="hidden">
                {selectedBase && (
                  <HStack spacing={1}>
                    <Icon as={FiDatabase} boxSize={4} color="airtable.500" />
                    <Text fontSize="sm" fontWeight="medium" color="gray.700">
                      {selectedBase.name}
                    </Text>
                  </HStack>
                )}
                {selectedBase && selectedTable && (
                  <Icon as={FiChevronRight} boxSize={3} color="gray.400" />
                )}
                {selectedTable && (
                  <HStack spacing={1}>
                    <Icon as={FiGrid} boxSize={4} color="airtable.500" />
                    <Text fontSize="sm" fontWeight="medium" color="gray.700">
                      {selectedTable.name}
                    </Text>
                  </HStack>
                )}
              </HStack>
            </HStack>
          )}
          
          {/* Content Area */}
          <Box flex={1} overflow="auto" p={4}>
            {/* Bases View */}
            {viewMode === 'bases' && (
              <SimpleGrid columns={gridColumns} spacing={4}>
                {connected && filteredBases.length > 0 ? (
                  filteredBases.map((base) => (
                    <BaseCard
                      key={base.id}
                      base={base}
                      selected={selectedBase?.id === base.id}
                      onSelect={() => handleBaseSelect(base)}
                      onMemorySync={() => handleStartIngestion([base.id])}
                    />
                  ))
                ) : (
                  <VStack spacing={4} align="center" py={8} w="100%" gridColumn={`1 / -1`}>
                    <Icon as={FiDatabase} boxSize={12} color="gray.400" />
                    <Text color="gray.500" textAlign="center" fontSize="lg">
                      {connected ? 'No bases found' : 'Connect to Airtable'}
                    </Text>
                    {connected && (
                      <Button
                        size="sm"
                        colorScheme="airtable"
                        onClick={() => fetchBases()}
                      >
                        Refresh
                      </Button>
                    )}
                  </VStack>
                )}
              </SimpleGrid>
            )}

            {/* Tables View */}
            {viewMode === 'tables' && selectedBase && (
              <VStack spacing={4} align="stretch">
                {filteredTables.length > 0 ? (
                  filteredTables.map((table) => (
                    <TableCard
                      key={table.id}
                      table={table}
                      baseId={selectedBase.id}
                      baseName={selectedBase.name}
                      selected={selectedTable?.id === table.id}
                      onSelect={() => handleTableSelect(table)}
                      onSchemaView={() => {
                        setSelectedTable(table);
                        setFields(table.fields);
                        setViews(table.views);
                        schemaModalOnOpen();
                      }}
                      onMemorySync={() => handleStartIngestion([selectedBase.id])}
                    />
                  ))
                ) : (
                  <VStack spacing={4} align="center" py={8} w="100%">
                    <Icon as={FiGrid} boxSize={8} color="gray.400" />
                    <Text color="gray.500" textAlign="center">
                      No tables found
                    </Text>
                  </VStack>
                )}
              </VStack>
            )}

            {/* Records View */}
            {viewMode === 'records' && selectedBase && selectedTable && (
              <VStack spacing={4} align="stretch">
                {filteredRecords.length > 0 ? (
                  <TableContainer>
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>Status</Th>
                          <Th>Modified</Th>
                          <Th>Actions</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {filteredRecords.map((record) => (
                          <RecordRow
                            key={record.id}
                            record={record}
                            onSelect={() => handleRecordSelect(record)}
                          />
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                ) : (
                  <VStack spacing={4} align="center" py={8}>
                    <Icon as={FiList} boxSize={8} color="gray.400" />
                    <Text color="gray.500" textAlign="center">
                      No records found
                    </Text>
                  </VStack>
                )}
              </VStack>
            )}

            {/* Schema View */}
            {viewMode === 'schema' && selectedTable && (
              <Tabs>
                <TabList>
                  <Tab>Fields</Tab>
                  <Tab>Views</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {selectedTable.fields.map((field) => (
                        <FieldCard
                          key={field.id}
                          field={field}
                        />
                      ))}
                    </VStack>
                  </TabPanel>
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {selectedTable.views.map((view) => (
                        <ViewCard
                          key={view.id}
                          view={view}
                        />
                      ))}
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            )}

            {/* Analytics View */}
            {viewMode === 'analytics' && selectedBase && (
              <VStack spacing={6} align="stretch">
                <Text fontSize="lg" fontWeight="medium">
                  Analytics - {selectedBase.name}
                </Text>
                
                <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
                  <StatCard
                    title="Tables"
                    value={selectedBase.total_tables}
                    icon={FiGrid}
                    color="blue"
                  />
                  <StatCard
                    title="Records"
                    value={selectedBase.total_records}
                    icon={FiList}
                    color="green"
                  />
                  <StatCard
                    title="Fields"
                    value={selectedBase.total_fields}
                    icon={FiLayers}
                    color="purple"
                  />
                  <StatCard
                    title="Views"
                    value={selectedBase.total_views}
                    icon={FiEye}
                    color="orange"
                  />
                </SimpleGrid>
                
                <Text color="gray.500">
                  Detailed analytics coming soon...
                </Text>
              </VStack>
            )}
          </Box>
        </VStack>
      </VStack>

      {/* Create Record Modal */}
      <Modal 
        isOpen={createRecordOpen} 
        onClose={createRecordOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiPlus} />
              <Text>Create Record</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {selectedTable && selectedTable.fields.map((field) => (
                <FormControl key={field.id}>
                  <FormLabel>{field.name}</FormLabel>
                  {field.type === 'single_line_text' && (
                    <Input
                      placeholder={`Enter ${field.name}`}
                      value={createRecordData.fields[field.name] || ''}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.value
                        }
                      }))}
                    />
                  )}
                  {field.type === 'long_text' && (
                    <Textarea
                      placeholder={`Enter ${field.name}`}
                      value={createRecordData.fields[field.name] || ''}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.value
                        }
                      }))}
                    />
                  )}
                  {field.type === 'single_select' && (
                    <Select
                      placeholder={`Select ${field.name}`}
                      value={createRecordData.fields[field.name] || ''}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.value
                        }
                      }))}
                    >
                      {field.options?.choices?.map((choice: any) => (
                        <option key={choice.id} value={choice.name}>
                          {choice.name}
                        </option>
                      ))}
                    </Select>
                  )}
                  {field.type === 'multiple_selects' && (
                    <CheckboxGroup
                      value={createRecordData.fields[field.name] || []}
                      onChange={(values) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: values
                        }
                      }))}
                    >
                      {field.options?.choices?.map((choice: any) => (
                        <Checkbox key={choice.id} value={choice.name}>
                          {choice.name}
                        </Checkbox>
                      ))}
                    </CheckboxGroup>
                  )}
                  {field.type === 'number' && (
                    <NumberInput
                      value={createRecordData.fields[field.name] || 0}
                      onChange={(value) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: value
                        }
                      }))}
                    >
                      <NumberInputField />
                      <NumberInputStepper>
                        <NumberIncrementStepper />
                        <NumberDecrementStepper />
                      </NumberInputStepper>
                    </NumberInput>
                  )}
                  {field.type === 'date' && (
                    <Input
                      type="date"
                      value={createRecordData.fields[field.name] || ''}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.value
                        }
                      }))}
                    />
                  )}
                  {field.type === 'datetime' && (
                    <Input
                      type="datetime-local"
                      value={createRecordData.fields[field.name] || ''}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.value
                        }
                      }))}
                    />
                  )}
                  {field.type === 'checkbox' && (
                    <Checkbox
                      isChecked={createRecordData.fields[field.name] || false}
                      onChange={(e) => setCreateRecordData(prev => ({
                        ...prev,
                        fields: {
                          ...prev.fields,
                          [field.name]: e.target.checked
                        }
                      }))}
                    >
                      {field.name}
                    </Checkbox>
                  )}
                </FormControl>
              ))}
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={createRecordOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="airtable"
                onClick={handleCreateRecord}
                isDisabled={!selectedTable}
              >
                Create Record
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Record Details Modal */}
      <Modal 
        isOpen={recordDetailsOpen} 
        onClose={recordDetailsOnClose}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiList} />
              <Text>{selectedRecord?.fields[Object.keys(selectedRecord?.fields || {})[0]] || 'Record Details'}</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {selectedRecord && (
              <VStack spacing={4} align="stretch">
                {/* Record Header */}
                <HStack justify="space-between" align="start">
                  <VStack align="start" spacing={2} flex={1}>
                    <Text fontSize="sm" fontWeight="medium">Table: {selectedRecord.table_name}</Text>
                    <Text fontSize="xs" color="gray.500">
                      Created {airtableUtils.formatRelativeTime(selectedRecord.created_time)}
                    </Text>
                  </VStack>
                  
                  <HStack spacing={1}>
                    <IconButton
                      icon={<FiEdit2 />}
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        recordDetailsOnClose();
                        createRecordOnOpen();
                      }}
                    />
                  </HStack>
                </HStack>
                
                <Divider />
                
                {/* Record Content */}
                <VStack spacing={3} align="stretch">
                  {Object.entries(selectedRecord.fields).map(([fieldName, fieldValue]) => (
                    <Box key={fieldName}>
                      <Text fontSize="sm" fontWeight="medium" color="gray.700" mb={1}>
                        {fieldName}
                      </Text>
                      <Box p={2} bg="gray.50" borderRadius="md">
                        {Array.isArray(fieldValue) ? (
                          <Wrap>
                            {fieldValue.map((item, index) => (
                              <WrapItem key={index}>
                                <Tag size="sm">
                                  {typeof item === 'string' ? item : item.name || ''}
                                </Tag>
                              </WrapItem>
                            ))}
                          </Wrap>
                        ) : typeof fieldValue === 'boolean' ? (
                          <Checkbox isChecked={fieldValue} isDisabled>
                            {fieldValue ? 'Yes' : 'No'}
                          </Checkbox>
                        ) : typeof fieldValue === 'object' && fieldValue !== null ? (
                          <Code p={2} fontSize="sm" bg="gray.100" borderRadius="md" w="full">
                            {JSON.stringify(fieldValue, null, 2)}
                          </Code>
                        ) : (
                          <Text fontSize="sm">
                            {fieldValue !== null && fieldValue !== undefined ? fieldValue.toString() : ''}
                          </Text>
                        )}
                      </Box>
                    </Box>
                  ))}
                </VStack>
                
                {/* Attachments */}
                {selectedRecord.attachments && selectedRecord.attachments.length > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Attachments</Text>
                    <Wrap>
                      {selectedRecord.attachments.map((attachment, index) => (
                        <WrapItem key={index}>
                          <HStack p={2} bg="gray.50" borderRadius="md" spacing={2}>
                            <Icon as={FiPaperclip} color="gray.500" />
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm">{attachment.name}</Text>
                              <Text fontSize="xs" color="gray.500">
                                {airtableUtils.formatFileSize(attachment.size || 0)}
                              </Text>
                            </VStack>
                          </HStack>
                        </WrapItem>
                      ))}
                    </Wrap>
                  </VStack>
                )}
                
                {/* Linked Records */}
                {selectedRecord.linked_records && selectedRecord.linked_records.length > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Linked Records</Text>
                    {selectedRecord.linked_records.map((link, index) => (
                      <HStack key={index} p={2} bg="gray.50" borderRadius="md" spacing={2}>
                        <Icon as={FiLink} color="gray.500" />
                        <Text fontSize="sm">{link.field}: {link.record_ids?.join(', ')}</Text>
                      </HStack>
                    ))}
                  </VStack>
                )}
                
                {/* Comments */}
                {selectedRecord.comments_count > 0 && (
                  <VStack align="start" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Comments</Text>
                    <HStack p={2} bg="gray.50" borderRadius="md" spacing={2}>
                      <Icon as={FiMessageSquare} color="gray.500" />
                      <Text fontSize="sm">{selectedRecord.comments_count} comments</Text>
                    </HStack>
                  </VStack>
                )}
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={recordDetailsOnClose}
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
              <Text>Airtable Memory Settings</Text>
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
                          <FormLabel htmlFor="airtable-ingestion-enabled">
                            Enable Data Memory
                          </FormLabel>
                          <Switch
                            id="airtable-ingestion-enabled"
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
                  
                  {/* Base Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Base Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-archived">
                            Include Archived Bases
                          </FormLabel>
                          <Switch
                            id="airtable-include-archived"
                            isChecked={memorySettings.includeArchivedBases}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeArchivedBases: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Records per Sync</FormLabel>
                          <NumberInput
                            value={memorySettings.maxRecordsPerSync}
                            min={100}
                            max={10000}
                            onChange={(value) => setMemorySettings(prev => prev ? { ...prev, maxRecordsPerSync: parseInt(value) || 1000 } : prev)}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Table Records per Sync</FormLabel>
                          <NumberInput
                            value={memorySettings.maxTableRecordsPerSync}
                            min={100}
                            max={10000}
                            onChange={(value) => setMemorySettings(prev => prev ? { ...prev, maxTableRecordsPerSync: parseInt(value) || 500 } : prev)}
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
                          <FormLabel htmlFor="airtable-include-tables">
                            Include Tables
                          </FormLabel>
                          <Switch
                            id="airtable-include-tables"
                            isChecked={memorySettings.includeTables}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeTables: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-records">
                            Include Records
                          </FormLabel>
                          <Switch
                            id="airtable-include-records"
                            isChecked={memorySettings.includeRecords}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeRecords: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-fields">
                            Include Fields
                          </FormLabel>
                          <Switch
                            id="airtable-include-fields"
                            isChecked={memorySettings.includeFields}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeFields: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-views">
                            Include Views
                          </FormLabel>
                          <Switch
                            id="airtable-include-views"
                            isChecked={memorySettings.includeViews}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeViews: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-attachments">
                            Include Attachments
                          </FormLabel>
                          <Switch
                            id="airtable-include-attachments"
                            isChecked={memorySettings.includeAttachments}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeAttachments: e.target.checked } : prev)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="airtable-include-webhooks">
                            Include Webhooks
                          </FormLabel>
                          <Switch
                            id="airtable-include-webhooks"
                            isChecked={memorySettings.includeWebhooks}
                            onChange={(e) => setMemorySettings(prev => prev ? { ...prev, includeWebhooks: e.target.checked } : prev)}
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
                colorScheme="airtable"
                onClick={() => {
                  if (memorySettings) {
                    airtableSkills.airtableUpdateMemorySettings(userId, memorySettings);
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
              <Text>Airtable Sync Status</Text>
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
                        {syncStatus.lastSyncTimestamp ? airtableUtils.formatRelativeTime(syncStatus.lastSyncTimestamp) : 'Never'}
                      </Text>
                    </Box>
                  </GridItem>
                  <GridItem>
                    <Box p={4} bg="gray.50" borderRadius="md">
                      <Text fontSize="sm" color="gray.600">Next Sync</Text>
                      <Text fontSize="lg" fontWeight="medium">
                        {syncStatus.nextSyncTimestamp ? airtableUtils.formatRelativeTime(syncStatus.nextSyncTimestamp) : 'Manual'}
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
                        <Icon as={FiDatabase} boxSize={6} color="blue.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="blue.700">
                          {syncStatus.stats.totalBasesIngested}
                        </Text>
                        <Text fontSize="sm" color="blue.600">Bases</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="green.50" borderRadius="md" textAlign="center">
                        <Icon as={FiGrid} boxSize={6} color="green.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="green.700">
                          {syncStatus.stats.totalTablesIngested}
                        </Text>
                        <Text fontSize="sm" color="green.600">Tables</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="purple.50" borderRadius="md" textAlign="center">
                        <Icon as={FiList} boxSize={6} color="purple.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="purple.700">
                          {syncStatus.stats.totalRecordsIngested}
                        </Text>
                        <Text fontSize="sm" color="purple.600">Records</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="orange.50" borderRadius="md" textAlign="center">
                        <Icon as={FiLayers} boxSize={6} color="orange.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="orange.700">
                          {syncStatus.stats.totalFieldsIngested}
                        </Text>
                        <Text fontSize="sm" color="orange.600">Fields</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="teal.50" borderRadius="md" textAlign="center">
                        <Icon as={FiEye} boxSize={6} color="teal.500" mb={2} />
                        <Text fontSize="lg" fontWeight="bold" color="teal.700">
                          {syncStatus.stats.totalViewsIngested}
                        </Text>
                        <Text fontSize="sm" color="teal.600">Views</Text>
                      </Box>
                    </GridItem>
                    <GridItem>
                      <Box p={3} bg="pink.50" borderRadius="md" textAlign="center">
                        <Icon as={FiPaperclip} boxSize={6} color="pink.500" mb={2} />
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
                colorScheme="airtable"
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

      {/* Schema Modal */}
      <Modal 
        isOpen={schemaModalOpen} 
        onClose={schemaModalOnClose}
        size="xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiLayers} />
              <Text>Schema - {selectedTable?.name}</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {selectedTable && (
              <Tabs>
                <TabList>
                  <Tab>Fields ({selectedTable.fields.length})</Tab>
                  <Tab>Views ({selectedTable.views.length})</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {selectedTable.fields.map((field) => (
                        <FieldCard
                          key={field.id}
                          field={field}
                        />
                      ))}
                    </VStack>
                  </TabPanel>
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {selectedTable.views.map((view) => (
                        <ViewCard
                          key={view.id}
                          view={view}
                        />
                      ))}
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            )}
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={schemaModalOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

// Card Components
const BaseCard: React.FC<{
  base: AirtableBase;
  selected: boolean;
  onSelect: () => void;
  onMemorySync: () => void;
}> = ({ base, selected, onSelect, onMemorySync }) => {
  return (
    <Card
      bg={cardBg}
      borderWidth={1}
      borderColor={selected ? 'airtable.500' : borderColor}
      boxShadow={selected ? 'md' : 'sm'}
      cursor="pointer"
      onClick={onSelect}
      _hover={{ transform: 'translateY(-2px)', boxShadow: 'md' }}
      transition="all 0.2s"
    >
      <CardBody>
        <VStack spacing={3} align="start">
          <HStack justify="space-between" w="100%">
            <VStack spacing={0} align="start" flex={1}>
              <Text fontSize="md" fontWeight="bold" noOfLines={2}>
                {base.name}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {base.workspace_name}
              </Text>
            </VStack>
            
            <VStack spacing={1} align="end">
              <Badge colorScheme={airtableUtils.getPermissionLevelColor(base.permission_level)}>
                {base.permission_level}
              </Badge>
              <Icon as={airtableUtils.getSharingIcon(base.sharing)} color="gray.500" boxSize={3} />
            </VStack>
          </HStack>
          
          <HStack justify="space-between" w="100%">
            <HStack spacing={3} fontSize="xs" color="gray.500">
              <HStack spacing={1}>
                <Icon as={FiGrid} boxSize={3} />
                <Text>{base.total_tables}</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiList} boxSize={3} />
                <Text>{base.total_records}</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiLayers} boxSize={3} />
                <Text>{base.total_fields}</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiEye} boxSize={3} />
                <Text>{base.total_views}</Text>
              </HStack>
            </HStack>
            
            <Tooltip label="Sync to Memory">
              <IconButton
                icon={<FiDatabase />}
                variant="ghost"
                size="xs"
                colorScheme="airtable"
                onClick={(e) => {
                  e.stopPropagation();
                  onMemorySync();
                }}
              />
            </Tooltip>
          </HStack>
          
          <HStack justify="space-between" w="100%">
            <Text fontSize="xs" color="gray.500">
              {airtableUtils.formatRelativeTime(base.last_modified_time)}
            </Text>
            
            <HStack spacing={1}>
              <HStack spacing={1} fontSize="xs" color="gray.500">
                <Icon as={FiUsers} boxSize={3} />
                <Text>{base.total_collaborators}</Text>
              </HStack>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

const TableCard: React.FC<{
  table: AirtableTable;
  baseId: string;
  baseName: string;
  selected: boolean;
  onSelect: () => void;
  onSchemaView: () => void;
  onMemorySync: () => void;
}> = ({ table, baseId, baseName, selected, onSelect, onSchemaView, onMemorySync }) => {
  return (
    <Card
      bg={cardBg}
      borderWidth={1}
      borderColor={selected ? 'airtable.500' : borderColor}
      boxShadow={selected ? 'md' : 'sm'}
      cursor="pointer"
      onClick={onSelect}
      _hover={{ transform: 'translateY(-1px)', boxShadow: 'md' }}
      transition="all 0.2s"
    >
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <HStack spacing={2}>
              {table.icon_emoji && <Text fontSize="lg">{table.icon_emoji}</Text>}
              <Text fontSize="md" fontWeight="medium">
                {table.name}
              </Text>
            </HStack>
            
            {table.description && (
              <Text fontSize="sm" color="gray.600" noOfLines={2}>
                {table.description}
              </Text>
            )}
            
            <HStack spacing={3} fontSize="sm" color="gray.500">
              <HStack spacing={1}>
                <Icon as={FiList} boxSize={4} />
                <Text>{table.records_count} records</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiLayers} boxSize={4} />
                <Text>{table.fields.length} fields</Text>
              </HStack>
              <HStack spacing={1}>
                <Icon as={FiEye} boxSize={4} />
                <Text>{table.views_count} views</Text>
              </HStack>
            </HStack>
          </VStack>
          
          <VStack spacing={1}>
            <Tooltip label="View Records">
              <IconButton
                icon={<FiList />}
                variant="ghost"
                size="sm"
                colorScheme="airtable"
              />
            </Tooltip>
            <Tooltip label="View Schema">
              <IconButton
                icon={<FiLayers />}
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onSchemaView();
                }}
              />
            </Tooltip>
            <Tooltip label="Sync to Memory">
              <IconButton
                icon={<FiDatabase />}
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onMemorySync();
                }}
              />
            </Tooltip>
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

const RecordRow: React.FC<{
  record: AirtableRecord;
  onSelect: () => void;
}> = ({ record, onSelect }) => {
  const primaryFieldName = Object.keys(record.fields)[0];
  const primaryFieldValue = record.fields[primaryFieldName];
  
  return (
    <Tr
      cursor="pointer"
      onClick={onSelect}
      _hover={{ bg: 'gray.50' }}
      transition="bg 0.2s"
    >
      <Td>
        <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
          {primaryFieldValue}
        </Text>
      </Td>
      <Td>
        {record.attachments && record.attachments.length > 0 && (
          <HStack spacing={1}>
            <Icon as={FiPaperclip} boxSize={3} color="gray.500" />
            <Text fontSize="xs" color="gray.500">
              {record.attachments.length}
            </Text>
          </HStack>
        )}
      </Td>
      <Td>
        <Text fontSize="xs" color="gray.500">
          {airtableUtils.formatRelativeTime(record.last_modified_time)}
        </Text>
      </Td>
      <Td>
        <HStack spacing={1} justify="flex-end">
          {record.comments_count > 0 && (
            <HStack spacing={1}>
              <Icon as={FiMessageSquare} boxSize={3} color="gray.500" />
              <Text fontSize="xs" color="gray.500">
                {record.comments_count}
              </Text>
            </HStack>
          )}
          <IconButton
            icon={<FiEye />}
            variant="ghost"
            size="xs"
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
          />
        </HStack>
      </Td>
    </Tr>
  );
};

const FieldCard: React.FC<{
  field: AirtableField;
}> = ({ field }) => {
  const fieldIcon = airtableUtils.getFieldTypeIcon(field.type);
  const fieldColor = airtableUtils.getFieldTypeColor(field.type);
  
  return (
    <HStack
      p={3}
      bg="gray.50"
      borderRadius="md"
      borderWidth={1}
      borderColor="gray.200"
      align="start"
    >
      <Icon as={fieldIcon} color={`${fieldColor}.500`} boxSize={5} />
      <VStack align="start" spacing={1} flex={1}>
        <HStack spacing={2}>
          <Text fontSize="sm" fontWeight="medium">
            {field.name}
          </Text>
          <Badge colorScheme={fieldColor} size="sm">
            {field.type}
          </Badge>
        </HStack>
        
        {field.description && (
          <Text fontSize="xs" color="gray.500">
            {field.description}
          </Text>
        )}
        
        <HStack spacing={3} fontSize="xs" color="gray.500">
          {field.required && (
            <Tag size="sm" colorScheme="red">
              Required
            </Tag>
          )}
          {field.unique && (
            <Tag size="sm" colorScheme="orange">
              Unique
            </Tag>
          )}
        </HStack>
      </VStack>
    </HStack>
  );
};

const ViewCard: React.FC<{
  view: AirtableView;
}> = ({ view }) => {
  const viewIcon = airtableUtils.getViewTypeIcon(view.type);
  const viewColor = airtableUtils.getViewTypeColor(view.type);
  
  return (
    <HStack
      p={3}
      bg="gray.50"
      borderRadius="md"
      borderWidth={1}
      borderColor="gray.200"
      align="start"
    >
      <Icon as={viewIcon} color={`${viewColor}.500`} boxSize={5} />
      <VStack align="start" spacing={1} flex={1}>
        <HStack spacing={2}>
          <Text fontSize="sm" fontWeight="medium">
            {view.name}
          </Text>
          <Badge colorScheme={viewColor} size="sm">
            {view.type}
          </Badge>
          {view.personal && (
            <Tag size="sm" colorScheme="blue">
              Personal
            </Tag>
          )}
        </HStack>
        
        {view.description && (
          <Text fontSize="xs" color="gray.500">
            {view.description}
          </Text>
        )}
        
        <HStack spacing={3} fontSize="xs" color="gray.500">
          {view.filters && Object.keys(view.filters).length > 0 && (
            <HStack spacing={1}>
              <Icon as={FiFilterIcon} boxSize={3} />
              <Text>Filters</Text>
            </HStack>
          )}
          {view.sorts && view.sorts.length > 0 && (
            <HStack spacing={1}>
              <Icon as={FiArrowUpDown} boxSize={3} />
              <Text>Sorted</Text>
            </HStack>
          )}
        </HStack>
      </VStack>
    </HStack>
  );
};

const StatCard: React.FC<{
  title: string;
  value: number;
  icon: any;
  color: string;
}> = ({ title, value, icon, color }) => {
  return (
    <Box p={4} bg="white" borderRadius="md" borderWidth={1} borderColor="gray.200">
      <VStack spacing={2} align="center">
        <Icon as={icon} boxSize={6} color={`${color}.500`} />
        <Text fontSize="lg" fontWeight="bold">
          {value.toLocaleString()}
        </Text>
        <Text fontSize="sm" color="gray.600" textAlign="center">
          {title}
        </Text>
      </VStack>
    </Box>
  );
};

// Icon components
const FiZapOff = (props: any) => <FiX {...props} />;
const FiArrowUpDown = (props: any) => <FiFilterIcon {...props} />;

export default AirtableDataManagementUI;