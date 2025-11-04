/**
 * GitLab Search & Filter Component
 * Advanced search and filtering for GitLab integration
 */

import React, { useState, useEffect, useCallback } from 'react';
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
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  NumberInput,
  NumberInputField,
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
  useColorModeValue
} from '@chakra-ui/react';
import {
  SearchIcon,
  FilterIcon,
  CloseIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  TimeIcon,
  StarIcon,
  GitlabIcon,
  CodeIcon,
  BugIcon,
  MergeIcon,
  HistoryIcon,
  UserIcon,
  CalendarIcon,
  SettingsIcon,
  RepeatIcon,
  DownloadIcon,
  AddIcon,
  ArrowUpIcon,
  ArrowDownIcon
} from '@chakra-ui/icons';
import {
  GitLabProject,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest,
  GitLabUser,
  GitLabBranch
} from '../types';
import { GitLabUtils } from '../utils';

interface GitLabSearchFilters {
  searchTerm: string;
  visibility: string[];
  archived: boolean;
  status: string[];
  state: string[];
  labels: string[];
  assignee: string;
  author: string;
  milestone: string;
  dateRange: {
    from: string;
    to: string;
  };
  starRange: {
    min: number;
    max: number;
  };
  forkRange: {
    min: number;
    max: number;
  };
  issueRange: {
    min: number;
    max: number;
  };
  languages: string[];
  projectTypes: string[];
  includeArchived: boolean;
  excludeEmpty: boolean;
}

interface GitLabSearchSort {
  field: string;
  direction: 'asc' | 'desc';
}

interface GitLabSearchProps {
  data: GitLabProject[] | GitLabPipeline[] | GitLabIssue[] | GitLabMergeRequest[];
  dataType: 'projects' | 'pipelines' | 'issues' | 'merge-requests' | 'commits' | 'branches';
  onSearch: (results: any[], filters: GitLabSearchFilters, sort: GitLabSearchSort) => void;
  onFiltersChange?: (filters: GitLabSearchFilters) => void;
  onSortChange?: (sort: GitLabSearchSort) => void;
  loading?: boolean;
  totalCount?: number;
}

const GitLabSearch: React.FC<GitLabSearchProps> = ({
  data,
  dataType,
  onSearch,
  onFiltersChange,
  onSortChange,
  loading = false,
  totalCount
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<GitLabSearchFilters>({
    searchTerm: '',
    visibility: [],
    archived: false,
    status: [],
    state: [],
    labels: [],
    assignee: '',
    author: '',
    milestone: '',
    dateRange: {
      from: '',
      to: ''
    },
    starRange: {
      min: 0,
      max: 1000
    },
    forkRange: {
      min: 0,
      max: 500
    },
    issueRange: {
      min: 0,
      max: 100
    },
    languages: [],
    projectTypes: [],
    includeArchived: false,
    excludeEmpty: false
  });

  const [sort, setSort] = useState<GitLabSearchSort>({
    field: getDefaultSortField(dataType),
    direction: 'desc'
  });

  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [savedSearches, setSavedSearches] = useState<any[]>([]);
  const [showSavedSearchModal, setShowSavedSearchModal] = useState(false);
  const [searchHistory, setSearchHistory] = useState<any[]>([]);
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Get default sort field based on data type
  function getDefaultSortField(type: string): string {
    switch (type) {
      case 'projects':
        return 'updated_at';
      case 'pipelines':
        return 'created_at';
      case 'issues':
        return 'updated_at';
      case 'merge-requests':
        return 'updated_at';
      case 'commits':
        return 'created_at';
      case 'branches':
        return 'name';
      default:
        return 'updated_at';
    }
  }

  // Get available options based on data
  const getAvailableOptions = useCallback(() => {
    const labels = new Set<string>();
    const users = new Set<string>();
    const milestones = new Set<string>();
    const languages = new Set<string>();

    data.forEach(item => {
      // Extract labels
      if ('labels' in item && Array.isArray(item.labels)) {
        item.labels.forEach((label: any) => {
          if (typeof label === 'string') {
            labels.add(label);
          } else if (label.title) {
            labels.add(label.title);
          }
        });
      }

      // Extract users
      if ('author' in item && item.author) {
        users.add(item.author.username);
      }
      if ('assignees' in item && Array.isArray(item.assignees)) {
        item.assignees.forEach((assignee: any) => {
          users.add(assignee.username);
        });
      }
      if ('assignee' in item && item.assignee) {
        users.add(item.assignee.username);
      }

      // Extract milestones
      if ('milestone' in item && item.milestone) {
        milestones.add(item.milestone.title);
      }

      // Extract languages (for projects)
      if ('languages' in item && item.languages) {
        Object.keys(item.languages).forEach(lang => {
          languages.add(lang);
        });
      }
    });

    return {
      labels: Array.from(labels),
      users: Array.from(users),
      milestones: Array.from(milestones),
      languages: Array.from(languages)
    };
  }, [data]);

  // Search and filter data
  const performSearch = useCallback(() => {
    let results = [...data];
    
    // Apply search term
    if (searchTerm.trim()) {
      results = results.filter(item => {
        const searchText = searchTerm.toLowerCase();
        
        if ('name' in item) {
          return item.name.toLowerCase().includes(searchText) ||
                 (item as any).description?.toLowerCase().includes(searchText) ||
                 (item as any).path?.toLowerCase().includes(searchText);
        }
        if ('title' in item) {
          return item.title.toLowerCase().includes(searchText) ||
                 (item as any).description?.toLowerCase().includes(searchText);
        }
        if ('id' in item) {
          return (item as any).iid?.toString().includes(searchText) ||
                 (item as any).ref?.toLowerCase().includes(searchText);
        }
        if ('message' in item) {
          return item.message.toLowerCase().includes(searchText) ||
                 (item as any).title?.toLowerCase().includes(searchText);
        }
        if ('name' in item) {
          return item.name.toLowerCase().includes(searchText);
        }
        
        return false;
      });
    }

    // Apply filters based on data type
    if (dataType === 'projects') {
      results = filterProjects(results as GitLabProject[], filters);
    } else if (dataType === 'pipelines') {
      results = filterPipelines(results as GitLabPipeline[], filters);
    } else if (dataType === 'issues') {
      results = filterIssues(results as GitLabIssue[], filters);
    } else if (dataType === 'merge-requests') {
      results = filterMergeRequests(results as GitLabMergeRequest[], filters);
    }

    // Apply sorting
    results = sortResults(results, sort.field, sort.direction);

    // Add to recent searches
    if (searchTerm.trim() && !recentSearches.includes(searchTerm)) {
      const newRecentSearches = [searchTerm, ...recentSearches.slice(0, 9)];
      setRecentSearches(newRecentSearches);
      localStorage.setItem('gitlab-recent-searches', JSON.stringify(newRecentSearches));
    }

    onSearch(results, filters, sort);
  }, [data, searchTerm, filters, sort, dataType, recentSearches, onSearch]);

  // Filter projects
  const filterProjects = (projects: GitLabProject[], filters: GitLabSearchFilters) => {
    return projects.filter(project => {
      // Visibility filter
      if (filters.visibility.length > 0 && !filters.visibility.includes(project.visibility)) {
        return false;
      }

      // Archived filter
      if (!filters.includeArchived && project.archived) {
        return false;
      }

      // Star range filter
      if (project.star_count < filters.starRange.min || project.star_count > filters.starRange.max) {
        return false;
      }

      // Fork range filter
      if (project.forks_count < filters.forkRange.min || project.forks_count > filters.forkRange.max) {
        return false;
      }

      // Issue range filter
      if (project.open_issues_count < filters.issueRange.min || project.open_issues_count > filters.issueRange.max) {
        return false;
      }

      // Exclude empty filter
      if (filters.excludeEmpty && project.star_count === 0 && project.forks_count === 0) {
        return false;
      }

      return true;
    });
  };

  // Filter pipelines
  const filterPipelines = (pipelines: GitLabPipeline[], filters: GitLabSearchFilters) => {
    return pipelines.filter(pipeline => {
      // Status filter
      if (filters.status.length > 0 && !filters.status.includes(pipeline.status)) {
        return false;
      }

      // Date range filter
      if (filters.dateRange.from && new Date(pipeline.created_at) < new Date(filters.dateRange.from)) {
        return false;
      }
      if (filters.dateRange.to && new Date(pipeline.created_at) > new Date(filters.dateRange.to)) {
        return false;
      }

      return true;
    });
  };

  // Filter issues
  const filterIssues = (issues: GitLabIssue[], filters: GitLabSearchFilters) => {
    return issues.filter(issue => {
      // State filter
      if (filters.state.length > 0 && !filters.state.includes(issue.state)) {
        return false;
      }

      // Labels filter
      if (filters.labels.length > 0) {
        const issueLabels = issue.labels.map(l => l.title);
        const hasAllLabels = filters.labels.every(label => issueLabels.includes(label));
        if (!hasAllLabels) {
          return false;
        }
      }

      // Assignee filter
      if (filters.assignee && issue.assignees.length > 0) {
        const hasAssignee = issue.assignees.some(a => a.username === filters.assignee);
        if (!hasAssignee) {
          return false;
        }
      }

      // Author filter
      if (filters.author && issue.author.username !== filters.author) {
        return false;
      }

      // Milestone filter
      if (filters.milestone && (!issue.milestone || issue.milestone.title !== filters.milestone)) {
        return false;
      }

      // Date range filter
      if (filters.dateRange.from && new Date(issue.created_at) < new Date(filters.dateRange.from)) {
        return false;
      }
      if (filters.dateRange.to && new Date(issue.created_at) > new Date(filters.dateRange.to)) {
        return false;
      }

      return true;
    });
  };

  // Filter merge requests
  const filterMergeRequests = (mergeRequests: GitLabMergeRequest[], filters: GitLabSearchFilters) => {
    return mergeRequests.filter(mr => {
      // State filter
      if (filters.state.length > 0 && !filters.state.includes(mr.state)) {
        return false;
      }

      // Labels filter
      if (filters.labels.length > 0) {
        const mrLabels = mr.labels.map(l => l.title);
        const hasAllLabels = filters.labels.every(label => mrLabels.includes(label));
        if (!hasAllLabels) {
          return false;
        }
      }

      // Assignee filter
      if (filters.assignee && mr.assignees.length > 0) {
        const hasAssignee = mr.assignees.some(a => a.username === filters.assignee);
        if (!hasAssignee) {
          return false;
        }
      }

      // Author filter
      if (filters.author && mr.author.username !== filters.author) {
        return false;
      }

      // Milestone filter
      if (filters.milestone && (!mr.milestone || mr.milestone.title !== filters.milestone)) {
        return false;
      }

      // Date range filter
      if (filters.dateRange.from && new Date(mr.created_at) < new Date(filters.dateRange.from)) {
        return false;
      }
      if (filters.dateRange.to && new Date(mr.created_at) > new Date(filters.dateRange.to)) {
        return false;
      }

      return true;
    });
  };

  // Sort results
  const sortResults = (results: any[], field: string, direction: 'asc' | 'desc') => {
    return [...results].sort((a, b) => {
      let aValue: any = a[field];
      let bValue: any = b[field];

      // Handle nested fields
      if (field.includes('.')) {
        const nestedFields = field.split('.');
        aValue = nestedFields.reduce((obj, key) => obj?.[key], a);
        bValue = nestedFields.reduce((obj, key) => obj?.[key], b);
      }

      // Handle string comparison
      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      // Handle date comparison
      if (field.includes('_at')) {
        aValue = new Date(aValue).getTime();
        bValue = new Date(bValue).getTime();
      }

      if (aValue < bValue) {
        return direction === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return direction === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  };

  // Update filters
  const updateFilters = useCallback((newFilters: Partial<GitLabSearchFilters>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    onFiltersChange?.(updatedFilters);
  }, [filters, onFiltersChange]);

  // Update sort
  const updateSort = useCallback((field: string, direction?: 'asc' | 'desc') => {
    const newDirection = direction || (sort.field === field && sort.direction === 'desc' ? 'asc' : 'desc');
    const newSort = { field, direction: newDirection };
    setSort(newSort);
    onSortChange?.(newSort);
  }, [sort, onSortChange]);

  // Clear filters
  const clearFilters = useCallback(() => {
    const defaultFilters: GitLabSearchFilters = {
      searchTerm: '',
      visibility: [],
      archived: false,
      status: [],
      state: [],
      labels: [],
      assignee: '',
      author: '',
      milestone: '',
      dateRange: {
        from: '',
        to: ''
      },
      starRange: {
        min: 0,
        max: 1000
      },
      forkRange: {
        min: 0,
        max: 500
      },
      issueRange: {
        min: 0,
        max: 100
      },
      languages: [],
      projectTypes: [],
      includeArchived: false,
      excludeEmpty: false
    };
    
    setFilters(defaultFilters);
    setSearchTerm('');
    onFiltersChange?.(defaultFilters);
  }, [onFiltersChange]);

  // Save search
  const saveSearch = useCallback(() => {
    const searchName = prompt('Enter a name for this search:');
    if (searchName) {
      const newSavedSearch = {
        id: Date.now(),
        name: searchName,
        filters: { ...filters },
        sort: { ...sort },
        searchTerm,
        dataType,
        createdAt: new Date().toISOString()
      };
      
      const newSavedSearches = [...savedSearches, newSavedSearch];
      setSavedSearches(newSavedSearches);
      localStorage.setItem('gitlab-saved-searches', JSON.stringify(newSavedSearches));
      
      toast({
        title: 'Search Saved',
        description: `Search "${searchName}" has been saved`,
        status: 'success',
        duration: 2000
      });
    }
  }, [filters, sort, searchTerm, dataType, savedSearches, toast]);

  // Load saved searches
  useEffect(() => {
    const saved = localStorage.getItem('gitlab-saved-searches');
    if (saved) {
      setSavedSearches(JSON.parse(saved));
    }

    const recent = localStorage.getItem('gitlab-recent-searches');
    if (recent) {
      setRecentSearches(JSON.parse(recent));
    }
  }, []);

  // Perform search when dependencies change
  useEffect(() => {
    performSearch();
  }, [performSearch]);

  const options = getAvailableOptions();
  const resultCount = data.length;

  return (
    <Box bg={bgColor} border="1px" borderColor={borderColor} borderRadius="lg" p={4}>
      <VStack spacing={4} align="stretch">
        {/* Search Header */}
        <HStack justify="space-between" align="center">
          <Heading size="md">Search & Filter</Heading>
          <HStack>
            <Text fontSize="sm" color="gray.600">
              {resultCount} of {totalCount || data.length} results
            </Text>
            {loading && <Icon as={RepeatIcon} className="animate-spin" />}
          </HStack>
        </HStack>

        {/* Main Search Bar */}
        <InputGroup size="lg">
          <InputLeftElement>
            <Icon as={SearchIcon} color="gray.400" />
          </InputLeftElement>
          <Input
            placeholder={`Search ${dataType}...`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && performSearch()}
          />
          <InputRightElement width="auto">
            <HStack spacing={2} mr={2}>
              {searchTerm && (
                <IconButton
                  size="sm"
                  variant="ghost"
                  aria-label="Clear search"
                  icon={<CloseIcon />}
                  onClick={() => setSearchTerm('')}
                />
              )}
              <Menu>
                <MenuButton as={Button} size="sm" variant="ghost" rightIcon={<ChevronDownIcon />}>
                  Recent
                </MenuButton>
                <MenuList>
                  {recentSearches.length > 0 ? (
                    recentSearches.map((search, index) => (
                      <MenuItem
                        key={index}
                        onClick={() => setSearchTerm(search)}
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

        {/* Quick Filters */}
        <HStack spacing={4} wrap="wrap">
          <Select
            placeholder="Sort by..."
            w="200px"
            value={sort.field}
            onChange={(e) => updateSort(e.target.value)}
          >
            {dataType === 'projects' && (
              <>
                <option value="name">Name</option>
                <option value="updated_at">Last Updated</option>
                <option value="created_at">Created</option>
                <option value="star_count">Stars</option>
                <option value="forks_count">Forks</option>
                <option value="open_issues_count">Open Issues</option>
              </>
            )}
            {dataType === 'pipelines' && (
              <>
                <option value="created_at">Created</option>
                <option value="updated_at">Updated</option>
                <option value="status">Status</option>
                <option value="duration">Duration</option>
              </>
            )}
            {dataType === 'issues' && (
              <>
                <option value="created_at">Created</option>
                <option value="updated_at">Updated</option>
                <option value="state">State</option>
                <option value="weight">Weight</option>
              </>
            )}
            {dataType === 'merge-requests' && (
              <>
                <option value="created_at">Created</option>
                <option value="updated_at">Updated</option>
                <option value="state">State</option>
                <option value="iid">Number</option>
              </>
            )}
          </Select>

          <Button
            variant="outline"
            leftIcon={sort.direction === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />}
            onClick={() => updateSort(sort.field)}
          >
            {sort.direction === 'asc' ? 'Ascending' : 'Descending'}
          </Button>

          <Button
            variant="outline"
            leftIcon={<FilterIcon />}
            rightIcon={showAdvancedFilters ? <ChevronUpIcon /> : <ChevronDownIcon />}
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          >
            Advanced Filters
            {Object.values(filters).filter(v => 
              (Array.isArray(v) && v.length > 0) || 
              (typeof v === 'boolean' && v) ||
              (typeof v === 'string' && v.trim() !== '')
            ).length > 0 && (
              <Badge ml={2} colorScheme="blue" size="sm">
                {Object.values(filters).filter(v => 
                  (Array.isArray(v) && v.length > 0) || 
                  (typeof v === 'boolean' && v) ||
                  (typeof v === 'string' && v.trim() !== '')
                ).length}
              </Badge>
            )}
          </Button>

          <Button
            variant="outline"
            leftIcon={<SaveIcon />}
            onClick={saveSearch}
          >
            Save Search
          </Button>

          <Button
            variant="outline"
            leftIcon={<CloseIcon />}
            onClick={clearFilters}
          >
            Clear All
          </Button>
        </HStack>

        {/* Advanced Filters */}
        <Collapse in={showAdvancedFilters} animateOpacity>
          <Box bg="gray.50" p={4} borderRadius="md" border="1px" borderColor="gray.200">
            <Accordion allowMultiple>
              {/* Projects Filters */}
              {dataType === 'projects' && (
                <AccordionItem>
                  <h2>
                    <AccordionButton>
                      <Box flex="1" textAlign="left">
                        <Text fontWeight="bold">Project Filters</Text>
                      </Box>
                      <AccordionIcon />
                    </AccordionButton>
                  </h2>
                  <AccordionPanel>
                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                      {/* Visibility Filter */}
                      <FormControl>
                        <FormLabel>Visibility</FormLabel>
                        <Stack>
                          {['public', 'private', 'internal'].map(visibility => (
                            <Checkbox
                              key={visibility}
                              isChecked={filters.visibility.includes(visibility)}
                              onChange={(e) => {
                                const newVisibility = e.target.checked
                                  ? [...filters.visibility, visibility]
                                  : filters.visibility.filter(v => v !== visibility);
                                updateFilters({ visibility: newVisibility });
                              }}
                            >
                              {visibility.charAt(0).toUpperCase() + visibility.slice(1)}
                            </Checkbox>
                          ))}
                        </Stack>
                      </FormControl>

                      {/* Star Range Filter */}
                      <FormControl>
                        <FormLabel>Stars: {filters.starRange.min} - {filters.starRange.max}</FormLabel>
                        <Slider
                          aria-label="star-range"
                          min={0}
                          max={1000}
                          value={[filters.starRange.min, filters.starRange.max]}
                          onChange={(values) => updateFilters({
                            starRange: { min: values[0], max: values[1] }
                          })}
                        >
                          <SliderTrack>
                            <SliderFilledTrack />
                          </SliderTrack>
                          <SliderThumb index={0} />
                          <SliderThumb index={1} />
                        </Slider>
                      </FormControl>

                      {/* Fork Range Filter */}
                      <FormControl>
                        <FormLabel>Forks: {filters.forkRange.min} - {filters.forkRange.max}</FormLabel>
                        <Slider
                          aria-label="fork-range"
                          min={0}
                          max={500}
                          value={[filters.forkRange.min, filters.forkRange.max]}
                          onChange={(values) => updateFilters({
                            forkRange: { min: values[0], max: values[1] }
                          })}
                        >
                          <SliderTrack>
                            <SliderFilledTrack />
                          </SliderTrack>
                          <SliderThumb index={0} />
                          <SliderThumb index={1} />
                        </Slider>
                      </FormControl>

                      {/* Options */}
                      <Stack>
                        <Checkbox
                          isChecked={filters.includeArchived}
                          onChange={(e) => updateFilters({ includeArchived: e.target.checked })}
                        >
                          Include Archived Projects
                        </Checkbox>
                        <Checkbox
                          isChecked={filters.excludeEmpty}
                          onChange={(e) => updateFilters({ excludeEmpty: e.target.checked })}
                        >
                          Exclude Empty Projects
                        </Checkbox>
                      </Stack>
                    </SimpleGrid>
                  </AccordionPanel>
                </AccordionItem>
              )}

              {/* Pipelines Filters */}
              {dataType === 'pipelines' && (
                <AccordionItem>
                  <h2>
                    <AccordionButton>
                      <Box flex="1" textAlign="left">
                        <Text fontWeight="bold">Pipeline Filters</Text>
                      </Box>
                      <AccordionIcon />
                    </AccordionButton>
                  </h2>
                  <AccordionPanel>
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                      {/* Status Filter */}
                      <FormControl>
                        <FormLabel>Status</FormLabel>
                        <Stack>
                          {['success', 'failed', 'running', 'pending', 'created', 'canceled', 'skipped', 'manual'].map(status => (
                            <Checkbox
                              key={status}
                              isChecked={filters.status.includes(status)}
                              onChange={(e) => {
                                const newStatus = e.target.checked
                                  ? [...filters.status, status]
                                  : filters.status.filter(s => s !== status);
                                updateFilters({ status: newStatus });
                              }}
                            >
                              {status.charAt(0).toUpperCase() + status.slice(1)}
                            </Checkbox>
                          ))}
                        </Stack>
                      </FormControl>

                      {/* Date Range Filter */}
                      <FormControl>
                        <FormLabel>Date Range</FormLabel>
                        <Stack>
                          <Input
                            type="date"
                            placeholder="From"
                            value={filters.dateRange.from}
                            onChange={(e) => updateFilters({
                              dateRange: { ...filters.dateRange, from: e.target.value }
                            })}
                          />
                          <Input
                            type="date"
                            placeholder="To"
                            value={filters.dateRange.to}
                            onChange={(e) => updateFilters({
                              dateRange: { ...filters.dateRange, to: e.target.value }
                            })}
                          />
                        </Stack>
                      </FormControl>
                    </SimpleGrid>
                  </AccordionPanel>
                </AccordionItem>
              )}

              {/* Issues Filters */}
              {(dataType === 'issues' || dataType === 'merge-requests') && (
                <AccordionItem>
                  <h2>
                    <AccordionButton>
                      <Box flex="1" textAlign="left">
                        <Text fontWeight="bold">
                          {dataType === 'issues' ? 'Issue' : 'Merge Request'} Filters
                        </Text>
                      </Box>
                      <AccordionIcon />
                    </AccordionButton>
                  </h2>
                  <AccordionPanel>
                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                      {/* State Filter */}
                      <FormControl>
                        <FormLabel>State</FormLabel>
                        <Stack>
                          {['opened', 'closed'].map(state => (
                            <Checkbox
                              key={state}
                              isChecked={filters.state.includes(state)}
                              onChange={(e) => {
                                const newState = e.target.checked
                                  ? [...filters.state, state]
                                  : filters.state.filter(s => s !== state);
                                updateFilters({ state: newState });
                              }}
                            >
                              {state.charAt(0).toUpperCase() + state.slice(1)}
                            </Checkbox>
                          ))}
                        </Stack>
                      </FormControl>

                      {/* Labels Filter */}
                      <FormControl>
                        <FormLabel>Labels</FormLabel>
                        <Stack maxH="200px" overflowY="auto">
                          {options.labels.map(label => (
                            <Checkbox
                              key={label}
                              isChecked={filters.labels.includes(label)}
                              onChange={(e) => {
                                const newLabels = e.target.checked
                                  ? [...filters.labels, label]
                                  : filters.labels.filter(l => l !== label);
                                updateFilters({ labels: newLabels });
                              }}
                            >
                              {label}
                            </Checkbox>
                          ))}
                        </Stack>
                      </FormControl>

                      {/* Assignee Filter */}
                      <FormControl>
                        <FormLabel>Assignee</FormLabel>
                        <Select
                          placeholder="Any assignee"
                          value={filters.assignee}
                          onChange={(e) => updateFilters({ assignee: e.target.value })}
                        >
                          {options.users.map(user => (
                            <option key={user} value={user}>
                              {user}
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      {/* Author Filter */}
                      <FormControl>
                        <FormLabel>Author</FormLabel>
                        <Select
                          placeholder="Any author"
                          value={filters.author}
                          onChange={(e) => updateFilters({ author: e.target.value })}
                        >
                          {options.users.map(user => (
                            <option key={user} value={user}>
                              {user}
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      {/* Milestone Filter */}
                      <FormControl>
                        <FormLabel>Milestone</FormLabel>
                        <Select
                          placeholder="Any milestone"
                          value={filters.milestone}
                          onChange={(e) => updateFilters({ milestone: e.target.value })}
                        >
                          {options.milestones.map(milestone => (
                            <option key={milestone} value={milestone}>
                              {milestone}
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      {/* Date Range Filter */}
                      <FormControl>
                        <FormLabel>Date Range</FormLabel>
                        <Stack>
                          <Input
                            type="date"
                            placeholder="From"
                            value={filters.dateRange.from}
                            onChange={(e) => updateFilters({
                              dateRange: { ...filters.dateRange, from: e.target.value }
                            })}
                          />
                          <Input
                            type="date"
                            placeholder="To"
                            value={filters.dateRange.to}
                            onChange={(e) => updateFilters({
                              dateRange: { ...filters.dateRange, to: e.target.value }
                            })}
                          />
                        </Stack>
                      </FormControl>
                    </SimpleGrid>
                  </AccordionPanel>
                </AccordionItem>
              )}
            </Accordion>
          </Box>
        </Collapse>

        {/* Saved Searches Modal */}
        <Modal
          isOpen={showSavedSearchModal}
          onClose={() => setShowSavedSearchModal(false)}
          size="lg"
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Saved Searches</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="stretch">
                {savedSearches.length > 0 ? (
                  savedSearches.map((savedSearch, index) => (
                    <Box
                      key={index}
                      p={4}
                      border="1px"
                      borderColor="gray.200"
                      borderRadius="md"
                      cursor="pointer"
                      _hover={{ bg: 'gray.50' }}
                      onClick={() => {
                        setFilters(savedSearch.filters);
                        setSort(savedSearch.sort);
                        setSearchTerm(savedSearch.searchTerm);
                        setShowSavedSearchModal(false);
                      }}
                    >
                      <HStack justify="space-between">
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">{savedSearch.name}</Text>
                          <Text fontSize="sm" color="gray.600">
                            {savedSearch.searchTerm || 'No search term'}
                          </Text>
                          <Text fontSize="xs" color="gray.500">
                            {new Date(savedSearch.createdAt).toLocaleString()}
                          </Text>
                        </VStack>
                        <HStack>
                          <Badge colorScheme="blue">
                            {savedSearch.dataType}
                          </Badge>
                          <IconButton
                            size="sm"
                            variant="ghost"
                            aria-label="Delete saved search"
                            icon={<CloseIcon />}
                            onClick={(e) => {
                              e.stopPropagation();
                              const newSavedSearches = savedSearches.filter(
                                (s, i) => i !== index
                              );
                              setSavedSearches(newSavedSearches);
                              localStorage.setItem(
                                'gitlab-saved-searches',
                                JSON.stringify(newSavedSearches)
                              );
                            }}
                          />
                        </HStack>
                      </HStack>
                    </Box>
                  ))
                ) : (
                  <Box textAlign="center" py={8}>
                    <Text color="gray.500">No saved searches found</Text>
                  </Box>
                )}
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                onClick={() => setShowSavedSearchModal(false)}
              >
                Close
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default GitLabSearch;