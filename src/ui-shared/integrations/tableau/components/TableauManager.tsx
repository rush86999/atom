import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Stack,
  Badge,
  Progress,
  Alert,
  AlertIcon,
  Divider,
  Flex,
  Icon,
  Tooltip,
  useToast,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Select,
  Switch,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useColorModeValue,
  SimpleGrid,
  Avatar,
  useBreakpointValue,
  Tabs,
  TabList,
  TabPanels,
  TabPanel,
  Tag,
  TagLabel,
  TagLeftIcon,
  useClipboard,
  Textarea,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Spinner,
  Checkbox,
  RadioGroup,
  Radio,
  CheckboxGroup,
  Stack as CheckboxStack,
  Code,
  Text as ChakraText,
  Link,
  Stat,
  StatLabel,
  StatNumber,
  StatArrow,
  StatHelpText,
  StatGroup,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  InfoIcon,
  ViewListIcon,
  ArchiveIcon,
  UserIcon,
  CopyIcon,
  DesktopIcon,
  CheckIcon,
  CloseIcon,
  CommentIcon,
  CalendarIcon,
  ClockIcon,
  UserGroupIcon,
  TeamIcon,
  FolderIcon,
  FilterIcon,
  SearchIcon,
  EditIcon as EditTaskIcon,
  DeleteIcon,
  PlusIcon,
  StarIcon,
  RepeatIcon,
  BarChartIcon,
  DashboardIcon,
  DatabaseIcon,
  RefreshIcon,
  DownloadIcon,
  EmbedIcon,
  PlayIcon,
  PauseIcon,
  SettingsIcon as SettingsIcon2,
  ChevronDownIcon,
  ChevronRightIcon,
  ViewIcon as ViewIcon2,
  EditIcon as EditIcon2,
  LinkIcon,
  CopyIcon as CopyIcon2,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface TableauIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface TableauWorkbook {
  id: string;
  name: string;
  description: string;
  content_url: string;
  show_tabs: boolean;
  size: number;
  created_at: string;
  updated_at: string;
  project_id: string;
  project_name: string;
  owner_id: string;
  owner_name: string;
  tags: string[];
  views: Array<{
    id: string;
    name: string;
    content_url: string;
    view_url: string;
  }>;
  datasources: Array<{
    id: string;
    name: string;
    type: string;
    connection_type: string;
  }>;
  webpage_url: string;
  embed_code: string;
  thumbnail_url: string;
  download_url: string;
  refreshable: boolean;
  data_acceleration_enabled: boolean;
  data_acceleration_configured: boolean;
  encrypt_extracts: boolean;
  default_view_id: string;
  revision: number;
  status: string;
  user_permissions: {
    read: boolean;
    write: boolean;
    download: boolean;
    share: boolean;
    delete: boolean;
  };
  is_published: boolean;
  extracts_refreshed_at: string;
  extract_incremental_schedule: {
    frequency: string;
    time?: string;
    minute?: number;
    timezone: string;
  };
}

interface TableauDatasource {
  id: string;
  name: string;
  description: string;
  content_url: string;
  type: string;
  connection_type: string;
  size: number;
  created_at: string;
  updated_at: string;
  project_id: string;
  project_name: string;
  owner_id: string;
  owner_name: string;
  tags: string[];
  connections: Array<{
    id: string;
    name: string;
    type: string;
    server: string;
    database: string;
    username: string;
    connected_at: string;
  }>;
  extracts_enabled: boolean;
  extracts_refreshed_at: string;
  extract_refresh_schedule: {
    frequency: string;
    time: string;
    timezone: string;
  };
  query_time: number;
  is_embedded: boolean;
  webpage_url: string;
  user_permissions: {
    read: boolean;
    write: boolean;
    download: boolean;
    refresh: boolean;
    delete: boolean;
  };
  status: string;
  last_refresh: string;
  data_freshness: string;
  connection_speed: string;
}

interface TableauView {
  id: string;
  name: string;
  content_url: string;
  created_at: string;
  updated_at: string;
  workbook_id: string;
  workbook_name: string;
  owner_id: string;
  owner_name: string;
  view_url: string;
  embed_code: string;
  thumbnail_url: string;
  sheet_type: string;
  sheet_number: number;
  tags: string[];
  user_permissions: {
    read: boolean;
    write: boolean;
    export: boolean;
    share: boolean;
    comment: boolean;
    filter: boolean;
  };
  total_views: number;
  last_viewed: string;
  favorite_count: number;
  comment_count: number;
  sheet_size: number;
  data_source_count: number;
  sheet_name: string;
}

interface TableauProject {
  id: string;
  name: string;
  description: string;
  content_url: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
  owner_name: string;
  parent_project_id: string;
  project_permission: string;
  workbook_count: number;
  datasource_count: number;
  user_permissions: {
    read: boolean;
    write: boolean;
    publish: boolean;
    delete: boolean;
  };
  is_default: boolean;
  webpage_url: string;
}

interface TableauUser {
  id: string;
  name: string;
  email: string;
  role: string;
  site_role: string;
  auth_setting: string;
  last_login: string;
  workbook_count: number;
  datasource_count: number;
  view_count: number;
  favorite_count: number;
}

// Tableau scopes constant
const TABLEAU_SCOPES = [
  'workbooks:read',
  'workbooks:write',
  'datasources:read',
  'datasources:write',
  'flows:read',
  'flows:write',
  'views:read',
  'views:write',
  'metrics:read',
  'metrics:write',
  'projects:read',
  'projects:write',
  'sites:read',
  'sites:write',
  'users:read',
  'users:write',
  'groups:read',
  'groups:write',
  'tasks:read',
  'tasks:write',
  'subscriptions:read',
  'subscriptions:write',
  'connections:read',
  'connections:write',
  'tableau:readonly'
];

/**
 * Enhanced Tableau Integration Manager
 * Complete Tableau data visualization and business intelligence system
 */
export const TableauIntegrationManager: React.FC<TableauIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Tableau',
    platform: 'tableau',
    enabled: true,
    settings: {
      contentTypes: ['workbooks', 'datasources', 'views', 'projects'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeExtracts: true,
      includeEmbedded: true,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['refresh_complete', 'extract_failed', 'view_published'],
      siteIds: [],
      projectIds: [],
      ownerIds: [],
      searchQueries: {
        workbooks: '',
        datasources: '',
        views: '',
        projects: ''
      },
      filters: {
        workbooks: {
          owner_id: '',
          project_id: '',
          connection_type: '',
          type_filter: '',
          sort: 'updated',
          direction: 'desc'
        },
        datasources: {
          owner_id: '',
          project_id: '',
          connection_type: '',
          type_filter: '',
          sort: 'updated',
          direction: 'desc'
        },
        views: {
          workbook_id: '',
          owner_id: '',
          sheet_type: '',
          sort: 'updated',
          direction: 'desc'
        }
      }
    }
  });

  // Data states
  const [workbooks, setWorkbooks] = useState<TableauWorkbook[]>([]);
  const [datasources, setDatasources] = useState<TableauDatasource[]>([]);
  const [views, setViews] = useState<TableauView[]>([]);
  const [projects, setProjects] = useState<TableauProject[]>([]);
  const [currentUser, setCurrentUser] = useState<TableauUser | null>(null);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    workbooksProcessed: 0,
    datasourcesProcessed: 0,
    viewsProcessed: 0,
    errors: []
  });

  // Modal states
  const [createWorkbookModalOpen, setCreateWorkbookModalOpen] = useState(false);
  const [createDatasourceModalOpen, setCreateDatasourceModalOpen] = useState(false);
  const [embedViewModalOpen, setEmbedViewModalOpen] = useState(false);
  const [refreshModalOpen, setRefreshModalOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  
  // Form states
  const [workbookForm, setWorkbookForm] = useState({
    name: '',
    description: '',
    project_id: '',
    project_name: 'Default Project',
    show_tabs: true,
    publish: false
  });
  
  const [datasourceForm, setDatasourceForm] = useState({
    name: '',
    description: '',
    type: 'sqlserver',
    connection_type: 'live',
    project_id: '',
    project_name: 'Default Project'
  });
  
  const [embedForm, setEmbedForm] = useState({
    view_id: '',
    width: '1200',
    height: '800',
    toolbar: 'yes',
    show_share_options: 'true'
  });
  
  const [refreshForm, setRefreshForm] = useState({
    item_id: '',
    item_type: 'workbook', // 'workbook' or 'datasource'
    refresh_type: 'full' // 'full' or 'incremental'
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('tableau_access_token_placeholder');

  useEffect(() => {
    checkTableauHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadTableauData();
    }
  }, [health]);

  const checkTableauHealth = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setHealth({
          connected: true,
          lastSync: new Date().toISOString(),
          errors: []
        });
      } else {
        setHealth({
          connected: false,
          lastSync: new Date().toISOString(),
          errors: [data.error || 'Tableau service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Tableau service health']
      });
    }
  };

  const loadTableauData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadWorkbooks(),
        loadDatasources(),
        loadViews(),
        loadProjects(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Tableau data');
      toast({
        title: 'Error',
        description: 'Failed to load Tableau data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadWorkbooks = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/workbooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          owner_id: config.settings.filters.workbooks.owner_id,
          project_id: config.settings.filters.workbooks.project_id,
          sort: config.settings.filters.workbooks.sort,
          direction: config.settings.filters.workbooks.direction,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setWorkbooks(data.data.workbooks || []);
      }
    } catch (err) {
      console.error('Error loading workbooks:', err);
    }
  };

  const loadDatasources = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/datasources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          owner_id: config.settings.filters.datasources.owner_id,
          project_id: config.settings.filters.datasources.project_id,
          connection_type: config.settings.filters.datasources.connection_type,
          type_filter: config.settings.filters.datasources.type_filter,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setDatasources(data.data.datasources || []);
      }
    } catch (err) {
      console.error('Error loading datasources:', err);
    }
  };

  const loadViews = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/views', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workbook_id: config.settings.filters.views.workbook_id,
          owner_id: config.settings.filters.views.owner_id,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setViews(data.data.views || []);
      }
    } catch (err) {
      console.error('Error loading views:', err);
    }
  };

  const loadProjects = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setProjects(data.data.projects || []);
      }
    } catch (err) {
      console.error('Error loading projects:', err);
    }
  };

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/tableau/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCurrentUser(data.data.user);
      }
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  };

  const createWorkbook = async () => {
    if (!workbookForm.name.trim()) {
      toast({
        title: 'Error',
        description: 'Workbook name is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/tableau/workbooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: workbookForm
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Workbook created successfully',
          status: 'success',
          duration: 3000
        });
        
        setWorkbookForm({
          name: '',
          description: '',
          project_id: '',
          project_name: 'Default Project',
          show_tabs: true,
          publish: false
        });
        setCreateWorkbookModalOpen(false);
        await loadWorkbooks();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create workbook',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create workbook',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const refreshItem = async () => {
    if (!refreshForm.item_id.trim()) {
      toast({
        title: 'Error',
        description: 'Item ID is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/tableau/' + refreshForm.item_type + 's', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'refresh',
          item_id: refreshForm.item_id,
          refresh_type: refreshForm.refresh_type
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: `${refreshForm.item_type} refresh initiated successfully`,
          status: 'success',
          duration: 3000
        });
        
        setRefreshForm({
          item_id: '',
          item_type: 'workbook',
          refresh_type: 'full'
        });
        setRefreshModalOpen(false);
        
        // Reload data after a short delay
        setTimeout(async () => {
          await Promise.all([
            loadWorkbooks(),
            loadDatasources()
          ]);
        }, 2000);
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to refresh item',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to refresh item',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const embedView = async () => {
    if (!embedForm.view_id.trim()) {
      toast({
        title: 'Error',
        description: 'View ID is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    try {
      // First get view details to generate embed code
      const response = await fetch('/api/integrations/tableau/views', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'embed',
          view_id: embedForm.view_id,
          width: embedForm.width,
          height: embedForm.height,
          toolbar: embedForm.toolbar,
          show_share_options: embedForm.show_share_options
        })
      });

      const result = await response.json();
      
      if (result.ok) {
        const embedCode = `<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script>
<div class="tableauPlaceholder" style="width:${embedForm.width}px;height:${embedForm.height}px;">
  <object class="tableauViz" width="${embedForm.width}" height="${embedForm.height}" style="display:none;">
    <param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" />
    <param name="embed_code_version" value="3" />
    <param name="site_root" value="" />
    <param name="name" value="${embedForm.view_id}" />
    <param name="toolbar" value="${embedForm.toolbar}" />
    <param name="showShareOptions" value="${embedForm.show_share_options}" />
  </object>
</div>`;
        
        setEmbedForm({
          view_id: '',
          width: '1200',
          height: '800',
          toolbar: 'yes',
          show_share_options: 'true'
        });
        setEmbedViewModalOpen(false);
        
        // Copy to clipboard
        navigator.clipboard.writeText(embedCode);
        
        toast({
          title: 'Success',
          description: 'Embed code copied to clipboard',
          status: 'success',
          duration: 3000
        });
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to generate embed code',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to generate embed code',
        status: 'error',
        duration: 3000
      });
    }
  };

  const searchTableau = async () => {
    if (!searchQuery.trim()) {
      await Promise.all([
        loadWorkbooks(),
        loadDatasources(),
        loadViews(),
        loadProjects()
      ]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/tableau/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          type: 'all', // Can be 'workbooks', 'datasources', 'views', 'projects', 'all'
          limit: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        const searchResults = result.data.results || [];
        
        // Update data based on search results
        const workbookResults = searchResults.filter((r: any) => r.type === 'workbook');
        const datasourceResults = searchResults.filter((r: any) => r.type === 'datasource');
        const viewResults = searchResults.filter((r: any) => r.type === 'view');
        const projectResults = searchResults.filter((r: any) => r.type === 'project');
        
        if (workbookResults.length > 0) {
          const searchWorkbooks = workbookResults.map((r: any) => ({
            id: r.id,
            name: r.name,
            description: r.description || `Workbook matching search: ${searchQuery}`,
            content_url: r.content_url,
            show_tabs: true,
            size: 1000000,
            created_at: r.created_at || new Date().toISOString(),
            updated_at: r.updated_at || new Date().toISOString(),
            project_id: 'proj123',
            project_name: r.project_name || 'Search Results',
            owner_id: 'user123',
            owner_name: r.owner_name || 'Unknown',
            tags: r.tags || [],
            views: [],
            datasources: [],
            webpage_url: r.webpage_url || 'https://10ax.online.tableau.com',
            embed_code: r.embed_code || '',
            thumbnail_url: r.thumbnail_url || 'https://10ax.online.tableau.com/static/images/default-thumbnail.png',
            download_url: r.download_url || 'https://10ax.online.tableau.com',
            refreshable: true,
            data_acceleration_enabled: false,
            data_acceleration_configured: false,
            encrypt_extracts: false,
            default_view_id: null,
            revision: 1,
            status: 'active',
            user_permissions: {
              read: true,
              write: true,
              download: true,
              share: true,
              delete: false
            },
            is_published: true,
            extracts_refreshed_at: null,
            extract_incremental_schedule: null
          }));
          setWorkbooks(searchWorkbooks);
        }
        
        if (datasourceResults.length > 0) {
          const searchDatasources = datasourceResults.map((r: any) => ({
            id: r.id,
            name: r.name,
            description: r.description || `Datasource matching search: ${searchQuery}`,
            content_url: r.content_url,
            type: r.type || 'sqlserver',
            connection_type: r.connection_type || 'live',
            size: 1000000,
            created_at: r.created_at || new Date().toISOString(),
            updated_at: r.updated_at || new Date().toISOString(),
            project_id: 'proj123',
            project_name: r.project_name || 'Search Results',
            owner_id: 'user123',
            owner_name: r.owner_name || 'Unknown',
            tags: r.tags || [],
            connections: [],
            extracts_enabled: false,
            extracts_refreshed_at: null,
            extract_refresh_schedule: null,
            query_time: 1.0,
            is_embedded: true,
            webpage_url: r.webpage_url || 'https://10ax.online.tableau.com',
            user_permissions: {
              read: true,
              write: true,
              download: true,
              refresh: true,
              delete: false
            },
            status: 'active',
            last_refresh: null,
            data_freshness: 'unknown',
            connection_speed: 'good'
          }));
          setDatasources(searchDatasources);
        }
        
        if (viewResults.length > 0) {
          const searchViews = viewResults.map((r: any) => ({
            id: r.id,
            name: r.name,
            content_url: r.content_url,
            created_at: r.created_at || new Date().toISOString(),
            updated_at: r.updated_at || new Date().toISOString(),
            workbook_id: r.workbook_id || 'wb123',
            workbook_name: r.workbook_name || 'Search Results',
            owner_id: 'user123',
            owner_name: r.owner_name || 'Unknown',
            view_url: r.view_url || 'https://10ax.online.tableau.com',
            embed_code: r.embed_code || '',
            thumbnail_url: r.thumbnail_url || 'https://10ax.online.tableau.com/static/images/default-thumbnail.png',
            sheet_type: r.sheet_type || 'dashboard',
            sheet_number: 1,
            tags: r.tags || [],
            user_permissions: {
              read: true,
              write: true,
              export: true,
              share: true,
              comment: true,
              filter: true
            },
            total_views: r.total_views || 0,
            last_viewed: null,
            favorite_count: 0,
            comment_count: 0,
            sheet_size: 500000,
            data_source_count: 1,
            sheet_name: r.name
          }));
          setViews(searchViews);
        }
        
        if (projectResults.length > 0) {
          const searchProjects = projectResults.map((r: any) => ({
            id: r.id,
            name: r.name,
            description: r.description || `Project matching search: ${searchQuery}`,
            content_url: r.content_url,
            created_at: r.created_at || new Date().toISOString(),
            updated_at: r.updated_at || new Date().toISOString(),
            owner_id: 'user123',
            owner_name: r.owner_name || 'Unknown',
            parent_project_id: null,
            project_permission: 'Allow',
            workbook_count: r.workbook_count || 0,
            datasource_count: r.datasource_count || 0,
            user_permissions: {
              read: true,
              write: true,
              publish: true,
              delete: false
            },
            is_default: false,
            webpage_url: r.webpage_url || 'https://10ax.online.tableau.com'
          }));
          setProjects(searchProjects);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Tableau',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startTableauOAuth = async () => {
    try {
      const response = await fetch('/api/auth/tableau/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: TABLEAU_SCOPES,
          redirect_uri: 'http://localhost:3000/oauth/tableau/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        const popup = window.open(
          data.authorization_url,
          'tableau-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkTableauHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Tableau OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Tableau OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderWorkbookCard = (workbook: TableauWorkbook) => (
    <Card key={workbook.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={DashboardIcon} color="blue.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  <Link href={workbook.webpage_url} target="_blank" color="blue.600">
                    {workbook.name}
                  </Link>
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {workbook.project_name} by {workbook.owner_name}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              {workbook.is_published && <Badge colorScheme="green">Published</Badge>}
              {workbook.data_acceleration_enabled && <Badge colorScheme="purple">Accelerated</Badge>}
              {workbook.encrypt_extracts && <Badge colorScheme="orange">Encrypted</Badge>}
            </HStack>
          </HStack>
          
          {workbook.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {workbook.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>📊 {workbook.views.length} views</Text>
            <Text>💾 {workbook.datasources.length} datasources</Text>
            <Text>📏 {(workbook.size / 1000000).toFixed(1)} MB</Text>
          </HStack>
          
          {workbook.tags && workbook.tags.length > 0 && (
            <HStack spacing={2} flexWrap="wrap">
              {workbook.tags.slice(0, 3).map((tag) => (
                <Tag key={tag} size="sm" colorScheme="gray">
                  <TagLabel>{tag}</TagLabel>
                </Tag>
              ))}
              {workbook.tags.length > 3 && (
                <Text fontSize="xs" color="gray.500">
                  +{workbook.tags.length - 3} more
                </Text>
              )}
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Updated {new Date(workbook.updated_at).toLocaleDateString()}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(workbook.webpage_url, '_blank')}>
                  View Workbook
                </MenuItem>
                <MenuItem icon={<EmbedIcon />} onClick={() => onCopy(workbook.embed_code)}>
                  Copy Embed Code
                </MenuItem>
                {workbook.refreshable && (
                  <MenuItem icon={<RefreshIcon />} onClick={() => {
                    setRefreshForm({
                      item_id: workbook.id,
                      item_type: 'workbook',
                      refresh_type: 'full'
                    });
                    setRefreshModalOpen(true);
                  }}>
                    Refresh Extracts
                  </MenuItem>
                )}
                <MenuItem icon={<DownloadIcon />} onClick={() => window.open(workbook.download_url, '_blank')}>
                  Download
                </MenuItem>
                <MenuDivider />
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderDatasourceCard = (datasource: TableauDatasource) => (
    <Card key={datasource.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={DatabaseIcon} color="green.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  <Link href={datasource.webpage_url} target="_blank" color="blue.600">
                    {datasource.name}
                  </Link>
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {datasource.project_name} by {datasource.owner_name}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={datasource.connection_type === 'live' ? 'green' : 'blue'}>
                {datasource.connection_type}
              </Badge>
              {datasource.extracts_enabled && <Badge colorScheme="purple">Extracts</Badge>}
              <Badge colorScheme={datasource.status === 'active' ? 'green' : 'orange'}>
                {datasource.status}
              </Badge>
            </HStack>
          </HStack>
          
          {datasource.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {datasource.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>🔧 {datasource.type}</Text>
            <Text>⚡ {datasource.query_time}s</Text>
            <Text>🌐 {datasource.connection_speed}</Text>
            <Text>📅 {datasource.data_freshness}</Text>
          </HStack>
          
          <HStack spacing={4} fontSize="xs" color="gray.500">
            <Text>Size: {(datasource.size / 1000000).toFixed(1)} MB</Text>
            {datasource.last_refresh && (
              <Text>Last: {new Date(datasource.last_refresh).toLocaleDateString()}</Text>
            )}
            {datasource.extract_refresh_schedule && (
              <Text>Refresh: {datasource.extract_refresh_schedule.frequency}</Text>
            )}
          </HStack>
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Updated {new Date(datasource.updated_at).toLocaleDateString()}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(datasource.webpage_url, '_blank')}>
                  View Datasource
                </MenuItem>
                {datasource.user_permissions.refresh && (
                  <MenuItem icon={<RefreshIcon />} onClick={() => {
                    setRefreshForm({
                      item_id: datasource.id,
                      item_type: 'datasource',
                      refresh_type: 'full'
                    });
                    setRefreshModalOpen(true);
                  }}>
                    Refresh Extracts
                  </MenuItem>
                )}
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderViewCard = (view: TableauView) => (
    <Card key={view.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={BarChartIcon} color="purple.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  <Link href={view.view_url} target="_blank" color="blue.600">
                    {view.name}
                  </Link>
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {view.workbook_name} by {view.owner_name}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={view.sheet_type === 'story' ? 'blue' : 'purple'}>
                {view.sheet_type}
              </Badge>
              {view.total_views > 0 && (
                <Badge colorScheme="green">{view.total_views} views</Badge>
              )}
            </HStack>
          </HStack>
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>📊 Sheet #{view.sheet_number}</Text>
            <Text>💾 {(view.sheet_size / 1000).toFixed(0)} KB</Text>
            <Text>🔗 {view.data_source_count} datasources</Text>
          </HStack>
          
          {view.tags && view.tags.length > 0 && (
            <HStack spacing={2} flexWrap="wrap">
              {view.tags.slice(0, 3).map((tag) => (
                <Tag key={tag} size="sm" colorScheme="gray">
                  <TagLabel>{tag}</TagLabel>
                </Tag>
              ))}
              {view.tags.length > 3 && (
                <Text fontSize="xs" color="gray.500">
                  +{view.tags.length - 3} more
                </Text>
              )}
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <HStack spacing={4} fontSize="xs" color="gray.500">
              {view.total_views > 0 && <Text>👁 {view.total_views}</Text>}
              {view.favorite_count > 0 && <Text>⭐ {view.favorite_count}</Text>}
              {view.comment_count > 0 && <Text>💬 {view.comment_count}</Text>}
            </HStack>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(view.view_url, '_blank')}>
                  View Dashboard
                </MenuItem>
                <MenuItem icon={<EmbedIcon />} onClick={() => {
                  setEmbedForm({
                    view_id: view.id,
                    width: '1200',
                    height: '800',
                    toolbar: 'yes',
                    show_share_options: 'true'
                  });
                  setEmbedViewModalOpen(true);
                }}>
                  Get Embed Code
                </MenuItem>
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderProjectCard = (project: TableauProject) => (
    <Card key={project.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={FolderIcon} color="orange.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  <Link href={project.webpage_url} target="_blank" color="blue.600">
                    {project.name}
                  </Link>
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  by {project.owner_name}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              {project.is_default && <Badge colorScheme="blue">Default</Badge>}
              <Badge colorScheme="green">{project.workbook_count} workbooks</Badge>
              <Badge colorScheme="purple">{project.datasource_count} datasources</Badge>
            </HStack>
          </HStack>
          
          {project.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {project.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="xs" color="gray.500">
            <Text>Created {new Date(project.created_at).toLocaleDateString()}</Text>
            <Text>Updated {new Date(project.updated_at).toLocaleDateString()}</Text>
          </HStack>
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Permission: {project.project_permission}
            </Text>
            
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ViewIcon />}
                onClick={() => window.open(project.webpage_url, '_blank')}
              >
                View Project
              </Button>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  if (!health?.connected) {
    return (
      <Box p={6}>
        <Alert status="warning">
          <AlertIcon />
          <Box>
            <AlertTitle>Tableau Not Connected</AlertTitle>
            <AlertDescription>
              Please connect your Tableau account to access workbooks, datasources, and views.
            </AlertDescription>
          </Box>
        </Alert>
        <Button
          mt={4}
          colorScheme="orange"
          onClick={startTableauOAuth}
        >
          Connect Tableau Account
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Tableau Integration</Heading>
          <Text color="gray.600">Manage workbooks, datasources, and dashboards</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search workbooks, datasources, views, projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchTableau()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="orange"
            onClick={searchTableau}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<PlusIcon />}
            colorScheme="blue"
            onClick={() => setCreateWorkbookModalOpen(true)}
          >
            New Workbook
          </Button>
          
          <Button
            leftIcon={<DatabaseIcon />}
            colorScheme="green"
            onClick={() => setCreateDatasourceModalOpen(true)}
          >
            New Datasource
          </Button>
        </HStack>

        {/* Stats Overview */}
        {currentUser && (
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>Workbooks</StatLabel>
              <StatNumber>{currentUser.workbook_count}</StatNumber>
              <StatHelpText>Published dashboards</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Datasources</StatLabel>
              <StatNumber>{currentUser.datasource_count}</StatNumber>
              <StatHelpText>Data connections</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Views</StatLabel>
              <StatNumber>{currentUser.view_count}</StatNumber>
              <StatHelpText>Total dashboard views</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Favorites</StatLabel>
              <StatNumber>{currentUser.favorite_count}</StatNumber>
              <StatHelpText>Saved content</StatHelpText>
            </Stat>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <DashboardIcon />
                <Text>Workbooks ({workbooks.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <DatabaseIcon />
                <Text>Datasources ({datasources.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <BarChartIcon />
                <Text>Views ({views.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <FolderIcon />
                <Text>Projects ({projects.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <UserIcon />
                <Text>Profile</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Workbooks Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : workbooks.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <DashboardIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No workbooks found</Text>
                  <Button
                    mt={4}
                    colorScheme="blue"
                    onClick={() => setCreateWorkbookModalOpen(true)}
                  >
                    Create Your First Workbook
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {workbooks.map(renderWorkbookCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Datasources Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : datasources.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <DatabaseIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No datasources found</Text>
                  <Button
                    mt={4}
                    colorScheme="green"
                    onClick={() => setCreateDatasourceModalOpen(true)}
                  >
                    Create Your First Datasource
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {datasources.map(renderDatasourceCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Views Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : views.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <BarChartIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No views found</Text>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {views.map(renderViewCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Projects Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : projects.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <FolderIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No projects found</Text>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {projects.map(renderProjectCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Profile Tab */}
            <TabPanel>
              {currentUser && (
                <Card>
                  <CardBody p={6}>
                    <VStack spacing={4} align="center">
                      <Avatar
                        name={currentUser.name}
                        size="2xl"
                        bg="orange.500"
                        color="white"
                      />
                      <VStack align="center" spacing={2}>
                        <Heading size="lg">{currentUser.name}</Heading>
                        <Text color="gray.600">{currentUser.email}</Text>
                        <Text fontSize="sm" color="gray.500">
                          Role: {currentUser.role} | Site Role: {currentUser.site_role}
                        </Text>
                        {currentUser.last_login && (
                          <Text fontSize="xs" color="gray.400">
                            Last login: {new Date(currentUser.last_login).toLocaleDateString()}
                          </Text>
                        )}
                      </VStack>
                      
                      <Divider />
                      
                      <VStack align="start" spacing={2} w="full">
                        <HStack justify="space-between" w="full">
                          <Text>Services</Text>
                          <HStack>
                            <Badge colorScheme="blue">Workbooks</Badge>
                            <Badge colorScheme="green">Datasources</Badge>
                            <Badge colorScheme="purple">Views</Badge>
                            <Badge colorScheme="orange">Projects</Badge>
                            <Badge colorScheme="red">Search</Badge>
                            <Badge colorScheme="teal">Embed</Badge>
                          </HStack>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Auth Method</Text>
                          <Text>{currentUser.auth_setting}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Total Content</Text>
                          <Text>{currentUser.workbook_count + currentUser.datasource_count + currentUser.view_count} items</Text>
                        </HStack>
                        
                        <Button
                          colorScheme="orange"
                          onClick={() => window.open('https://tableau.cloud', '_blank')}
                        >
                          Open Tableau Cloud
                        </Button>
                      </VStack>
                    </VStack>
                  </CardBody>
                </Card>
              )}
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Workbook Modal */}
        <Modal isOpen={createWorkbookModalOpen} onClose={() => setCreateWorkbookModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Workbook</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Workbook Name</FormLabel>
                  <Input
                    value={workbookForm.name}
                    onChange={(e) => setWorkbookForm({...workbookForm, name: e.target.value})}
                    placeholder="Enter workbook name"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={workbookForm.description}
                    onChange={(e) => setWorkbookForm({...workbookForm, description: e.target.value})}
                    placeholder="Enter workbook description"
                    rows={4}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Project</FormLabel>
                  <Select
                    value={workbookForm.project_id}
                    onChange={(e) => setWorkbookForm({...workbookForm, project_id: e.target.value, project_name: e.target.value === '' ? 'Default Project' : e.target.value})}
                  >
                    <option value="">Default Project</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Show Tabs</FormLabel>
                    <Switch
                      isChecked={workbookForm.show_tabs}
                      onChange={(e) => setWorkbookForm({...workbookForm, show_tabs: e.target.checked})}
                    >
                      Enable tab navigation
                    </Switch>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Publish</FormLabel>
                    <Switch
                      isChecked={workbookForm.publish}
                      onChange={(e) => setWorkbookForm({...workbookForm, publish: e.target.checked})}
                    >
                      Publish workbook
                    </Switch>
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateWorkbookModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={createWorkbook}
                isLoading={loading}
              >
                Create Workbook
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Datasource Modal */}
        <Modal isOpen={createDatasourceModalOpen} onClose={() => setCreateDatasourceModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Datasource</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Datasource Name</FormLabel>
                  <Input
                    value={datasourceForm.name}
                    onChange={(e) => setDatasourceForm({...datasourceForm, name: e.target.value})}
                    placeholder="Enter datasource name"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={datasourceForm.description}
                    onChange={(e) => setDatasourceForm({...datasourceForm, description: e.target.value})}
                    placeholder="Enter datasource description"
                    rows={4}
                  />
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Type</FormLabel>
                    <Select
                      value={datasourceForm.type}
                      onChange={(e) => setDatasourceForm({...datasourceForm, type: e.target.value})}
                    >
                      <option value="sqlserver">SQL Server</option>
                      <option value="postgresql">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="oracle">Oracle</option>
                      <option value="excel">Excel</option>
                      <option value="csv">CSV</option>
                      <option value="json">JSON</option>
                      <option value="snowflake">Snowflake</option>
                      <option value="bigquery">Google BigQuery</option>
                      <option value="redshift">Amazon Redshift</option>
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Connection Type</FormLabel>
                    <Select
                      value={datasourceForm.connection_type}
                      onChange={(e) => setDatasourceForm({...datasourceForm, connection_type: e.target.value as 'live' | 'extract'})}
                    >
                      <option value="live">Live Connection</option>
                      <option value="extract">Data Extract</option>
                    </Select>
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Project</FormLabel>
                  <Select
                    value={datasourceForm.project_id}
                    onChange={(e) => setDatasourceForm({...datasourceForm, project_id: e.target.value, project_name: e.target.value === '' ? 'Default Project' : e.target.value})}
                  >
                    <option value="">Default Project</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateDatasourceModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="green"
                onClick={() => {/* Create datasource logic */}}
                isLoading={loading}
              >
                Create Datasource
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Embed View Modal */}
        <Modal isOpen={embedViewModalOpen} onClose={() => setEmbedViewModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Get Embed Code</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>View ID</FormLabel>
                  <Input
                    value={embedForm.view_id}
                    onChange={(e) => setEmbedForm({...embedForm, view_id: e.target.value})}
                    placeholder="Enter view ID"
                  />
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Width</FormLabel>
                    <Input
                      value={embedForm.width}
                      onChange={(e) => setEmbedForm({...embedForm, width: e.target.value})}
                      placeholder="1200"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Height</FormLabel>
                    <Input
                      value={embedForm.height}
                      onChange={(e) => setEmbedForm({...embedForm, height: e.target.value})}
                      placeholder="800"
                    />
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Toolbar</FormLabel>
                    <Select
                      value={embedForm.toolbar}
                      onChange={(e) => setEmbedForm({...embedForm, toolbar: e.target.value})}
                    >
                      <option value="yes">Show</option>
                      <option value="no">Hide</option>
                      <option value="top">Top</option>
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Share Options</FormLabel>
                    <Switch
                      isChecked={embedForm.show_share_options === 'true'}
                      onChange={(e) => setEmbedForm({...embedForm, show_share_options: e.target.checked ? 'true' : 'false'})}
                    >
                      Show share options
                    </Switch>
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setEmbedViewModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={embedView}
                isLoading={loading}
              >
                Generate & Copy Embed Code
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Refresh Item Modal */}
        <Modal isOpen={refreshModalOpen} onClose={() => setRefreshModalOpen(false)} size="md">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Refresh Extracts</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Item Type</FormLabel>
                  <Select
                    value={refreshForm.item_type}
                    onChange={(e) => setRefreshForm({...refreshForm, item_type: e.target.value as 'workbook' | 'datasource'})}
                  >
                    <option value="workbook">Workbook</option>
                    <option value="datasource">Datasource</option>
                  </Select>
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Item ID</FormLabel>
                  <Input
                    value={refreshForm.item_id}
                    onChange={(e) => setRefreshForm({...refreshForm, item_id: e.target.value})}
                    placeholder="Enter item ID"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Refresh Type</FormLabel>
                  <Select
                    value={refreshForm.refresh_type}
                    onChange={(e) => setRefreshForm({...refreshForm, refresh_type: e.target.value as 'full' | 'incremental'})}
                  >
                    <option value="full">Full Refresh</option>
                    <option value="incremental">Incremental Refresh</option>
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setRefreshModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={refreshItem}
                isLoading={loading}
              >
                Start Refresh
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default TableauIntegrationManager;