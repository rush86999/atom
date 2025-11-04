/**
 * ATOM Universal Search Component
 * Advanced search interface for all ATOM integrations
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  DrawerFooter
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
  HamburgerIcon
} from '@chakra-ui/icons';

interface AtomSearchResult {
  id: string;
  type: 'file' | 'issue' | 'commit' | 'message' | 'task' | 'document' | 'project' | 'user';
  title: string;
  description?: string;
  source: string; // integration name (gitlab, github, slack, etc.)
  sourceIcon: React.ElementType;
  sourceColor: string;
  url?: string;
  createdAt: string;
  updatedAt: string;
  author?: {
    name: string;
    avatar?: string;
    email?: string;
  };
  metadata: Record<string, any>;
  highlights?: string[];
  score?: number;
}

interface AtomSearchFilters {
  sources: string[];
  types: string[];
  dateRange: {
    from: string;
    to: string;
  };
  authors: string[];
  projects: string[];
  tags: string[];
  status: string[];
  priority: string[];
  includeArchived: boolean;
  includeDeleted: boolean;
}

interface AtomSearchSort {
  field: string;
  direction: 'asc' | 'desc';
}

interface AtomSearchProps {
  integrations: string[];
  onSearch: (query: string, filters: AtomSearchFilters, sort: AtomSearchSort) => void;
  onResultClick: (result: AtomSearchResult) => void;
  loading?: boolean;
  recentSearches?: string[];
  savedSearches?: Array<{
    id: string;
    name: string;
    query: string;
    filters: AtomSearchFilters;
    sort: AtomSearchSort;
    createdAt: string;
  }>;
}

const integrationIcons = {
  gitlab: GitlabIcon,
  github: GitHubIcon,
  slack: SlackIcon,
  gmail: EmailIcon,
  notion: NotionIcon,
  jira: JiraIcon,
  box: BoxIcon,
  dropbox: DropBoxIcon,
  gdrive: GoogleDriveIcon,
  nextjs: CodeIcon
};

const integrationColors = {
  gitlab: 'orange.500',
  github: 'gray.700',
  slack: 'purple.500',
  gmail: 'red.500',
  notion: 'gray.600',
  jira: 'blue.600',
  box: 'blue.500',
  dropbox: 'blue.400',
  gdrive: 'green.500',
  nextjs: 'gray.800'
};

const typeIcons = {
  file: DocumentIcon,
  issue: BugIcon,
  commit: CodeIcon,
  message: ChatIcon,
  task: EditIcon,
  document: DocumentIcon,
  project: FolderIcon,
  user: UserIcon
};

const typeColors = {
  file: 'gray.500',
  issue: 'red.500',
  commit: 'green.500',
  message: 'blue.500',
  task: 'purple.500',
  document: 'gray.600',
  project: 'orange.500',
  user: 'teal.500'
};

const AtomSearch: React.FC<AtomSearchProps> = ({
  integrations,
  onSearch,
  onResultClick,
  loading = false,
  recentSearches = [],
  savedSearches = []
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<AtomSearchFilters>({
    sources: [],
    types: [],
    dateRange: {
      from: '',
      to: ''
    },
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

  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showSavedSearchModal, setShowSavedSearchModal] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [searchResults, setSearchResults] = useState<AtomSearchResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<AtomSearchResult | null>(null);
  const [searchStats, setSearchStats] = useState({
    total: 0,
    sources: 0,
    types: 0,
    time: 0
  });

  const [isSearching, setIsSearching] = useState(false);
  const [searchSuggestions, setSearchSuggestions] = useState<string[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [isMobile, setIsMobile] = useState(false);
  
  const toast = useToast();
  const {
    isOpen: isFilterDrawerOpen,
    onOpen: onFilterDrawerOpen,
    onClose: onFilterDrawerClose
  } = useDisclosure();

  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBgColor = useColorModeValue('gray.50', 'gray.700');

  // Check if mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Auto-search with debounce
  const performSearch = useCallback(async () => {
    if (!searchTerm.trim()) {
      setSearchResults([]);
      setSearchStats({ total: 0, sources: 0, types: 0, time: 0 });
      return;
    }

    setIsSearching(true);
    const startTime = Date.now();

    try {
      // Simulate search results (in real implementation, this would call your search API)
      const mockResults = generateMockResults(searchTerm, filters, sort);
      
      const endTime = Date.now();
      
      setSearchResults(mockResults);
      setSearchStats({
        total: mockResults.length,
        sources: new Set(mockResults.map(r => r.source)).size,
        types: new Set(mockResults.map(r => r.type)).size,
        time: endTime - startTime
      });

      onSearch(searchTerm, filters, sort);
    } catch (error) {
      toast({
        title: 'Search Error',
        description: 'Failed to perform search. Please try again.',
        status: 'error',
        duration: 3000
      });
    } finally {
      setIsSearching(false);
    }
  }, [searchTerm, filters, sort, onSearch, toast]);

  // Generate mock results for demonstration
  const generateMockResults = (query: string, filters: AtomSearchFilters, sort: AtomSearchSort): AtomSearchResult[] => {
    const results: AtomSearchResult[] = [];
    const availableSources = filters.sources.length > 0 ? filters.sources : integrations;
    const availableTypes = filters.types.length > 0 ? filters.types : ['file', 'issue', 'commit', 'message', 'task'];

    // Generate mock results for each integration
    availableSources.forEach((source, index) => {
      const SourceIcon = integrationIcons[source as keyof typeof integrationIcons];
      const sourceColor = integrationColors[source as keyof typeof integrationColors];

      availableTypes.forEach((type, typeIndex) => {
        const TypeIcon = typeIcons[type as keyof typeof typeIcons];
        const typeColor = typeColors[type as keyof typeof typeColors];

        for (let i = 0; i < 3; i++) {
          results.push({
            id: `${source}-${type}-${index}-${typeIndex}-${i}`,
            type: type as any,
            title: `${query} - ${type} from ${source}`,
            description: `This is a ${type} from ${source} that matches your search query "${query}".`,
            source,
            sourceIcon: SourceIcon,
            sourceColor,
            url: `https://${source}.example.com/item/${index}-${typeIndex}-${i}`,
            createdAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
            updatedAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
            author: {
              name: `User ${i}`,
              avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${i}`,
              email: `user${i}@example.com`
            },
            metadata: {
              projectId: `project-${index}`,
              size: Math.floor(Math.random() * 1000),
              language: ['JavaScript', 'Python', 'TypeScript', 'Go', 'Rust'][Math.floor(Math.random() * 5)],
              status: ['active', 'pending', 'completed', 'archived'][Math.floor(Math.random() * 4)]
            },
            highlights: [query, type, source],
            score: Math.random() * 100
          });
        }
      });
    });

    // Sort results
    return results.sort((a, b) => {
      let aValue: any = a[sort.field];
      let bValue: any = b[sort.field];

      if (sort.field === 'relevance') {
        aValue = a.score || 0;
        bValue = b.score || 0;
      } else if (sort.field.includes('At')) {
        aValue = new Date(a[sort.field] || 0).getTime();
        bValue = new Date(b[sort.field] || 0).getTime();
      }

      if (aValue < bValue) {
        return sort.direction === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sort.direction === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
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
    performSearch();
  }, [searchTerm, filters, sort, performSearch]);

  // Update filters
  const updateFilters = useCallback((newFilters: Partial<AtomSearchFilters>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
  }, [filters]);

  // Update sort
  const updateSort = useCallback((field: string, direction?: 'asc' | 'desc') => {
    const newDirection = direction || (sort.field === field && sort.direction === 'desc' ? 'asc' : 'desc');
    const newSort = { field, direction: newDirection };
    setSort(newSort);
  }, [sort]);

  // Clear filters
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
  }, []);

  // Handle result click
  const handleResultClick = useCallback((result: AtomSearchResult) => {
    setSelectedResult(result);
    onResultClick(result);
    
    // Open URL if available
    if (result.url) {
      window.open(result.url, '_blank');
    }
  }, [onResultClick]);

  // Save search
  const saveSearch = useCallback(() => {
    const searchName = prompt('Enter a name for this search:');
    if (searchName && searchTerm.trim()) {
      // In real implementation, save to backend
      toast({
        title: 'Search Saved',
        description: `Search "${searchName}" has been saved`,
        status: 'success',
        duration: 2000
      });
    }
  }, [searchTerm, toast]);

  // Get active filters count
  const getActiveFiltersCount = useCallback(() => {
    return Object.values(filters).reduce((count, value) => {
      if (Array.isArray(value)) {
        return count + value.length;
      } else if (typeof value === 'boolean') {
        return count + (value ? 1 : 0);
      } else if (typeof value === 'object' && value !== null) {
        return count + Object.values(value).filter(v => v && v.toString().trim()).length;
      }
      return count;
    }, 0);
  }, [filters]);

  const activeFiltersCount = getActiveFiltersCount();

  // Render search result item
  const renderSearchResult = (result: AtomSearchResult) => {
    const TypeIcon = typeIcons[result.type];
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
                color={typeColors[result.type]}
              />
              <VStack align="start" spacing={1">
                <Text fontWeight="bold" noOfLines={1}>
                  {result.title}
                </Text>
                {result.description && (
                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                    {result.description}
                  </Text>
                )}
              </VStack>
            </HStack>
            
            <VStack align="end" spacing={1">
              <Badge
                display="flex"
                alignItems="center"
                gap={1}
                colorScheme={result.source.replace('gitlab', 'orange').replace('github', 'gray') as any}
                size="sm"
              >
                <Icon as={SourceIcon} w={3} h={3} />
                {result.source}
              </Badge>
              <Text fontSize="xs" color="gray.500">
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
                <Text fontSize="sm" color="gray.600">
                  {result.author.name}
                </Text>
              </HStack>
              
              <HStack spacing={2}>
                {result.highlights?.map((highlight, index) => (
                  <Tag key={index} size="sm" colorScheme="blue" variant="subtle">
                    {highlight}
                  </Tag>
                ))}
                {result.score && (
                  <Tag size="sm" colorScheme="green" variant="subtle">
                    {Math.round(result.score)}%
                  </Tag>
                )}
              </HStack>
            </HStack>
          )}
          
          <HStack spacing={2}>
            {Object.entries(result.metadata).map(([key, value]) => {
              if (!value || value === '') return null;
              return (
                <Tag key={key} size="sm" variant="subtle">
                  <Text textTransform="capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}:
                  </Text>
                  {value}
                </Tag>
              );
            })}
          </HStack>
        </VStack>
      </Box>
    );
  };

  return (
    <Box minH="100vh" bg={bgColor}>
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
          {/* Search Bar */}
          <HStack spacing={4} align="center">
            <InputGroup size="lg" flex={1}>
              <InputLeftElement>
                <Icon as={SearchIcon} color="gray.400" />
              </InputLeftElement>
              <Input
                ref={searchInputRef}
                placeholder="Search across all integrations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    performSearch();
                  }
                  if (e.key === 'ArrowDown') {
                    setSelectedSuggestionIndex(prev => 
                      Math.min(prev + 1, searchSuggestions.length - 1)
                    );
                  }
                  if (e.key === 'ArrowUp') {
                    setSelectedSuggestionIndex(prev => Math.max(prev - 1, -1));
                  }
                }}
                onFocus={() => {
                  if (recentSearches.length > 0) {
                    setShowSearchHistory(true);
                  }
                }}
              />
              <InputRightElement width="auto">
                <HStack spacing={2} mr={2}>
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
                  <Menu>
                    <MenuButton
                      as={Button}
                      size="sm"
                      variant="ghost"
                      rightIcon={<ChevronDownIcon />}
                    >
                      Recent
                    </MenuButton>
                    <MenuList>
                      {recentSearches.length > 0 ? (
                        recentSearches.map((search, index) => (
                          <MenuItem
                            key={index}
                            onClick={() => setSearchQuery(search)}
                          >
                            <HStack>
                              <Icon as={HistoryIcon} />
                              <Text>{search}</Text>
                            </HStack>
                          </MenuItem>
                        ))
                      ) : (
                        <MenuItem isDisabled>
                          <Text color="gray.500">No recent searches</Text>
                        </MenuItem>
                      )}
                    </MenuList>
                  </Menu>
                </HStack>
              </InputRightElement>
            </InputGroup>

            {isMobile && (
              <IconButton
                variant="outline"
                aria-label="Filters"
                icon={<FilterIcon />}
                onClick={onFilterDrawerOpen}
              />
            )}
          </HStack>

          {/* Filter Bar */}
          {!isMobile && (
            <HStack spacing={4} wrap="wrap" justify="space-between">
              <HStack spacing={4} wrap="wrap">
                {/* Source Filter */}
                <Select
                  placeholder="All Sources"
                  w="150px"
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
                </Select>

                {/* Type Filter */}
                <Select
                  placeholder="All Types"
                  w="150px"
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
                  <option value="document">Documents</option>
                  <option value="project">Projects</option>
                </Select>

                {/* Sort Options */}
                <Select
                  placeholder="Sort by..."
                  w="150px"
                  value={sort.field}
                  onChange={(e) => updateSort(e.target.value)}
                >
                  <option value="relevance">Relevance</option>
                  <option value="updatedAt">Last Updated</option>
                  <option value="createdAt">Created</option>
                  <option value="title">Title</option>
                </Select>

                <Button
                  variant="outline"
                  leftIcon={sort.direction === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />}
                  onClick={() => updateSort(sort.field)}
                >
                  {sort.direction === 'asc' ? 'Ascending' : 'Descending'}
                </Button>
              </HStack>

              <HStack spacing={4}>
                <Button
                  variant="outline"
                  leftIcon={<FilterIcon />}
                  rightIcon={<ChevronDownIcon />}
                  onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                >
                  Filters
                  {activeFiltersCount > 0 && (
                    <Badge ml={2} colorScheme="blue" size="sm">
                      {activeFiltersCount}
                    </Badge>
                  )}
                </Button>

                <Button
                  variant="outline"
                  leftIcon={<SaveIcon />}
                  onClick={saveSearch}
                >
                  Save
                </Button>

                <Button
                  variant="outline"
                  leftIcon={<CloseIcon />}
                  onClick={clearFilters}
                >
                  Clear
                </Button>
              </HStack>
            </HStack>
          )}
        </VStack>
      </Box>

      {/* Advanced Filters */}
      {showAdvancedFilters && !isMobile && (
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
                  {integrations.map(integration => {
                    const Icon = integrationIcons[integration as keyof typeof integrationIcons];
                    const color = integrationColors[integration as keyof typeof integrationColors];
                    
                    return (
                      <Checkbox
                        key={integration}
                        isChecked={filters.sources.includes(integration)}
                        onChange={(e) => {
                          const newSources = e.target.checked
                            ? [...filters.sources, integration]
                            : filters.sources.filter(s => s !== integration);
                          updateFilters({ sources: newSources });
                        }}
                      >
                        <HStack>
                          <Icon as={Icon} w={4} h={4} color={color} />
                          <Text>{integration.charAt(0).toUpperCase() + integration.slice(1)}</Text>
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
                  {Object.entries(typeIcons).map(([type, Icon]) => {
                    const color = typeColors[type as keyof typeof typeColors];
                    
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
      )}

      {/* Search Stats */}
      {searchResults.length > 0 && (
        <Box p={4} bg="gray.50" borderBottom="1px" borderColor={borderColor}>
          <HStack justify="space-between" align="center">
            <HStack>
              <Text fontWeight="bold">
                {searchStats.total} results
              </Text>
              <Text fontSize="sm" color="gray.600">
                Found in {searchStats.time}ms across {searchStats.sources} sources
              </Text>
            </HStack>
            <HStack>
              <Text fontSize="sm" color="gray.600">
                Filters: {activeFiltersCount} active
              </Text>
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
            <Text fontSize="lg" color="gray.600" textAlign="center">
              No results found for "{searchTerm}"
            </Text>
            <Text fontSize="sm" color="gray.500" textAlign="center">
              Try adjusting your filters or search terms
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
            <Text fontSize="lg" color="gray.600" textAlign="center">
              Search across all your integrations
            </Text>
            <Text fontSize="sm" color="gray.500" textAlign="center">
              Enter a query to find files, issues, commits, messages, and more
            </Text>
          </VStack>
        )}
      </Box>

      {/* Mobile Filter Drawer */}
      {isMobile && (
        <Drawer
          isOpen={isFilterDrawerOpen}
          placement="right"
          onClose={onFilterDrawerClose}
          size="md"
        >
          <DrawerOverlay />
          <DrawerContent>
            <DrawerCloseButton />
            <DrawerHeader>
              <HStack>
                <Icon as={FilterIcon} />
                <Text>Search Filters</Text>
              </HStack>
            </DrawerHeader>
            <DrawerBody>
              <VStack spacing={6} align="stretch">
                <Text fontWeight="bold">Sources</Text>
                <VStack align="start" spacing={2}>
                  {integrations.map(integration => {
                    const Icon = integrationIcons[integration as keyof typeof integrationIcons];
                    const color = integrationColors[integration as keyof typeof integrationColors];
                    
                    return (
                      <Checkbox
                        key={integration}
                        isChecked={filters.sources.includes(integration)}
                        onChange={(e) => {
                          const newSources = e.target.checked
                            ? [...filters.sources, integration]
                            : filters.sources.filter(s => s !== integration);
                          updateFilters({ sources: newSources });
                        }}
                      >
                        <HStack>
                          <Icon as={Icon} w={4} h={4} color={color} />
                          <Text>{integration.charAt(0).toUpperCase() + integration.slice(1)}</Text>
                        </HStack>
                      </Checkbox>
                    );
                  })}
                </VStack>

                <Text fontWeight="bold">Types</Text>
                <VStack align="start" spacing={2}>
                  {Object.entries(typeIcons).map(([type, Icon]) => {
                    const color = typeColors[type as keyof typeof typeColors];
                    
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
                </VStack>

                <Text fontWeight="bold">Date Range</Text>
                <VStack spacing={2}>
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
                </VStack>
              </VStack>
            </DrawerBody>
            <DrawerFooter>
              <Button
                variant="outline"
                onClick={clearFilters}
                mr={3}
              >
                Clear All
              </Button>
              <Button
                colorScheme="blue"
                onClick={onFilterDrawerClose}
              >
                Apply Filters
              </Button>
            </DrawerFooter>
          </DrawerContent>
        </Drawer>
      )}
    </Box>
  );
};

export default AtomSearch;