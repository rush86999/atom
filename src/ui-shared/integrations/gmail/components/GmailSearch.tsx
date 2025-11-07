import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  Button,
  Select,
  Checkbox,
  CheckboxGroup,
  Text,
  Badge,
  IconButton,
  Tooltip,
  useColorModeValue,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Switch,
  Divider,
  SimpleGrid,
  Progress,
  Tag,
  TagLabel,
  TagCloseButton,
  Flex,
  Spacer,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  RangeSlider,
  RangeSliderTrack,
  RangeSliderFilledTrack,
  RangeSliderThumb,
} from '@chakra-ui/react';
import {
  SearchIcon,
  FilterIcon,
  CalendarIcon,
  TimeIcon,
  StarIcon,
  AttachmentIcon,
  DownloadIcon,
  SettingsIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  AddIcon,
  DeleteIcon,
  RepeatIcon,
} from '@chakra-ui/icons';

// Interfaces for Gmail data types
interface GmailMessage {
  id: string;
  threadId: string;
  labelIds: string[];
  snippet: string;
  payload: {
    headers: Array<{
      name: string;
      value: string;
    }>;
    parts?: Array<{
      mimeType: string;
      body: {
        data?: string;
        size?: number;
      };
    }>;
  };
  sizeEstimate: number;
  internalDate: string;
}

interface GmailThread {
  id: string;
  messages: GmailMessage[];
  historyId: string;
  snippet: string;
}

interface GmailLabel {
  id: string;
  name: string;
  type: string;
  messageListVisibility?: string;
  labelListVisibility?: string;
  color?: {
    textColor: string;
    backgroundColor: string;
  };
}

interface GmailContact {
  resourceName: string;
  emailAddresses: Array<{
    value: string;
    type?: string;
    formattedType?: string;
  }>;
  names: Array<{
    displayName: string;
    familyName?: string;
    givenName?: string;
    middleName?: string;
  }>;
  phoneNumbers: Array<{
    value: string;
    type?: string;
    formattedType?: string;
  }>;
  organizations: Array<{
    name?: string;
    title?: string;
    department?: string;
  }>;
}

// Search filters interface
interface GmailSearchFilters {
  searchTerm: string;
  labels: string[];
  from: string;
  to: string;
  subject: string;
  hasAttachment: boolean;
  isStarred: boolean;
  isUnread: boolean;
  isImportant: boolean;
  dateRange: {
    from: string;
    to: string;
  };
  sizeRange: {
    min: number;
    max: number;
  };
  semanticSearch: boolean;
  includeSpam: boolean;
  includeTrash: boolean;
  importance: 'all' | 'high' | 'normal' | 'low';
  readStatus: 'all' | 'read' | 'unread';
  starredStatus: 'all' | 'starred' | 'not-starred';
}

// Search sort interface
interface GmailSearchSort {
  field: string;
  direction: 'asc' | 'desc';
}

// Component props
interface GmailSearchProps {
  data: GmailMessage[] | GmailThread[] | GmailContact[];
  dataType: 'messages' | 'threads' | 'contacts';
  onSearch: (results: any[], filters: GmailSearchFilters, sort: GmailSearchSort) => void;
  onFiltersChange?: (filters: GmailSearchFilters) => void;
  onSortChange?: (sort: GmailSearchSort) => void;
  loading?: boolean;
  totalCount?: number;
  availableLabels?: GmailLabel[];
  availableContacts?: GmailContact[];
}

const GmailSearch: React.FC<GmailSearchProps> = ({
  data,
  dataType,
  onSearch,
  onFiltersChange,
  onSortChange,
  loading = false,
  totalCount = 0,
  availableLabels = [],
  availableContacts = []
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<GmailSearchFilters>({
    searchTerm: '',
    labels: [],
    from: '',
    to: '',
    subject: '',
    hasAttachment: false,
    isStarred: false,
    isUnread: false,
    isImportant: false,
    dateRange: {
      from: '',
      to: ''
    },
    sizeRange: {
      min: 0,
      max: 50000000 // 50MB
    },
    semanticSearch: false,
    includeSpam: false,
    includeTrash: false,
    importance: 'all',
    readStatus: 'all',
    starredStatus: 'all'
  });

  const [sort, setSort] = useState<GmailSearchSort>({
    field: getDefaultSortField(dataType),
    direction: 'desc'
  });

  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [savedSearches, setSavedSearches] = useState<any[]>([]);
  const [showSavedSearchModal, setShowSavedSearchModal] = useState(false);
  const [searchHistory, setSearchHistory] = useState<any[]>([]);
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Get default sort field based on data type
  function getDefaultSortField(type: string): string {
    switch (type) {
      case 'messages':
        return 'internalDate';
      case 'threads':
        return 'internalDate';
      case 'contacts':
        return 'displayName';
      default:
        return 'internalDate';
    }
  }

  // Get available options from data
  const getAvailableOptions = useCallback(() => {
    const senders = new Set<string>();
    const recipients = new Set<string>();
    const subjects = new Set<string>();

    data.forEach(item => {
      if ('payload' in item) {
        const message = item as GmailMessage;
        const headers = message.payload.headers || [];

        // Extract senders
        const fromHeader = headers.find(h => h.name.toLowerCase() === 'from');
        if (fromHeader) {
          senders.add(fromHeader.value);
        }

        // Extract recipients
        const toHeader = headers.find(h => h.name.toLowerCase() === 'to');
        if (toHeader) {
          toHeader.value.split(',').forEach(email => {
            recipients.add(email.trim());
          });
        }

        // Extract subjects
        const subjectHeader = headers.find(h => h.name.toLowerCase() === 'subject');
        if (subjectHeader) {
          subjects.add(subjectHeader.value);
        }
      }
    });

    return {
      senders: Array.from(senders).slice(0, 50), // Limit to 50
      recipients: Array.from(recipients).slice(0, 50),
      subjects: Array.from(subjects).slice(0, 50)
    };
  }, [data]);

  // Perform search with filters
  const performSearch = useCallback(() => {
    let results = [...data];

    // Apply search term
    if (searchTerm.trim()) {
      results = results.filter(item => {
        const searchText = searchTerm.toLowerCase();

        if ('payload' in item) {
          const message = item as GmailMessage;
          const headers = message.payload.headers || [];

          // Search in from, to, subject, and snippet
          const from = headers.find(h => h.name.toLowerCase() === 'from')?.value || '';
          const to = headers.find(h => h.name.toLowerCase() === 'to')?.value || '';
          const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || '';

          return from.toLowerCase().includes(searchText) ||
                 to.toLowerCase().includes(searchText) ||
                 subject.toLowerCase().includes(searchText) ||
                 message.snippet.toLowerCase().includes(searchText);
        }

        if ('names' in item) {
          const contact = item as GmailContact;
          return contact.names.some(name =>
            name.displayName.toLowerCase().includes(searchText)
          ) || contact.emailAddresses.some(email =>
            email.value.toLowerCase().includes(searchText)
          );
        }

        return false;
      });
    }

    // Apply filters based on data type
    if (dataType === 'messages') {
      results = filterMessages(results as GmailMessage[], filters);
    } else if (dataType === 'threads') {
      results = filterThreads(results as GmailThread[], filters);
    } else if (dataType === 'contacts') {
      results = filterContacts(results as GmailContact[], filters);
    }

    // Apply sorting
    results = sortResults(results, sort.field, sort.direction);

    // Add to recent searches
    if (searchTerm.trim() && !recentSearches.includes(searchTerm)) {
      const newRecentSearches = [searchTerm, ...recentSearches.slice(0, 9)];
      setRecentSearches(newRecentSearches);
      localStorage.setItem('gmail-recent-searches', JSON.stringify(newRecentSearches));
    }

    onSearch(results, filters, sort);
  }, [data, searchTerm, filters, sort, dataType, recentSearches, onSearch]);

  // Filter messages
  const filterMessages = (messages: GmailMessage[], filters: GmailSearchFilters) => {
    return messages.filter(message => {
      const headers = message.payload.headers || [];

      // From filter
      if (filters.from) {
        const fromHeader = headers.find(h => h.name.toLowerCase() === 'from');
        if (!fromHeader || !fromHeader.value.toLowerCase().includes(filters.from.toLowerCase())) {
          return false;
        }
      }

      // To filter
      if (filters.to) {
        const toHeader = headers.find(h => h.name.toLowerCase() === 'to');
        if (!toHeader || !toHeader.value.toLowerCase().includes(filters.to.toLowerCase())) {
          return false;
        }
      }

      // Subject filter
      if (filters.subject) {
        const subjectHeader = headers.find(h => h.name.toLowerCase() === 'subject');
        if (!subjectHeader || !subjectHeader.value.toLowerCase().includes(filters.subject.toLowerCase())) {
          return false;
        }
      }

      // Labels filter
      if (filters.labels.length > 0) {
        const hasAllLabels = filters.labels.every(label =>
          message.labelIds.includes(label)
        );
        if (!hasAllLabels) {
          return false;
        }
      }

      // Attachment filter
      if (filters.hasAttachment) {
        const hasAttachment = message.payload.parts?.some(part =>
          part.mimeType !== 'text/plain' && part.mimeType !== 'text/html'
        ) || false;
        if (!hasAttachment) {
          return false;
        }
      }

      // Size range filter
      if (message.sizeEstimate < filters.sizeRange.min || message.sizeEstimate > filters.sizeRange.max) {
        return false;
      }

      // Date range filter
      if (filters.dateRange.from && new Date(parseInt(message.internalDate)) < new Date(filters.dateRange.from)) {
        return false;
      }
      if (filters.dateRange.to && new Date(parseInt(message.internalDate)) > new Date(filters.dateRange.to)) {
        return false;
      }

      // Read status filter
      if (filters.readStatus !== 'all') {
        const isUnread = message.labelIds.includes('UNREAD');
        if (filters.readStatus === 'read' && isUnread) return false;
        if (filters.readStatus === 'unread' && !isUnread) return false;
      }

      // Starred status filter
      if (filters.starredStatus !== 'all') {
        const isStarred = message.labelIds.includes('STARRED');
        if (filters.starredStatus === 'starred' && !isStarred) return false;
        if (filters.starredStatus === 'not-starred' && isStarred) return false;
      }

      return true;
    });
  };

  // Filter threads
  const filterThreads = (threads: GmailThread[], filters: GmailSearchFilters) => {
    return threads.filter(thread => {
      // For threads, we check if any message in the thread matches the filters
      const matchingMessages = filterMessages(thread.messages, filters);
      return matchingMessages.length > 0;
    });
  };

  // Filter contacts
  const filterContacts = (contacts: GmailContact[], filters: GmailSearchFilters) => {
    return contacts.filter(contact => {
      // Search in contact names and emails
      const matchesName = contact.names.some(name =>
        name.displayName.toLowerCase().includes(filters.searchTerm.toLowerCase())
      );
      const matchesEmail = contact.emailAddresses.some(email =>
        email.value.toLowerCase().includes(filters.searchTerm.toLowerCase())
      );

      return matchesName || matchesEmail;
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

      // Handle date comparison
      if (field === 'internalDate') {
        aValue = new Date(parseInt(aValue)).getTime();
        bValue = new Date(parseInt(bValue)).getTime();
      }

      // Handle string comparison
      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (aValue < bValue) {
        return direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  };

  // Handle filter changes
  const handleFilterChange = (newFilters: Partial<GmailSearchFilters>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    onFiltersChange?.(updatedFilters);
  };

  // Handle sort changes
  const handleSortChange = (newSort: Partial<GmailSearchSort>) => {
    const updatedSort = { ...sort, ...newSort };
    setSort(updatedSort);
    onSortChange?.(updatedSort);
  };

  // Clear all filters
  const clearAllFilters = () => {
    const defaultFilters: GmailSearchFilters = {
      searchTerm: '',
      labels: [],
      from: '',
      to: '',
      subject: '',
      hasAttachment: false,
      isStarred: false,
      isUnread: false,
      isImportant: false,
      dateRange: {
        from: '',
        to: ''
      },
      sizeRange: {
        min: 0,
        max: 50000000
      },
      semanticSearch: false,
      includeSpam: false,
      includeTrash: false,
      importance: 'all',
      readStatus: 'all',
      starredStatus: 'all'
    };
    setFilters(defaultFilters);
    setSearchTerm('');
    onFiltersChange?.(defaultFilters);
  };

  // Save current search
  const saveCurrentSearch = () => {
    const searchToSave = {
      id: Date.now().toString(),
      name: `Search ${new Date().toLocaleString()}`,
      filters: { ...filters },
      sort: { ...sort },
      searchTerm,
      timestamp: new Date().toISOString()
    };

    const updatedSavedSearches = [searchToSave, ...savedSearches.slice(0, 9)];
    setSavedSearches(updatedSavedSearches);
    localStorage.setItem('gmail-saved-searches', JSON.stringify(updatedSavedSearches));

    toast({
      title: 'Search saved',
      status: 'success',
      duration: 2000,
    });
  };

  // Load saved search
  const loadSavedSearch = (savedSearch: any) => {
    setFilters(savedSearch.filters);
    setSort(savedSearch.sort);
    setSearchTerm(savedSearch.searchTerm);
    onFiltersChange?.(savedSearch.filters);
    onSortChange?.(savedSearch.sort);
    setShowSavedSearchModal(false);
  };

  // Available options from data
  const availableOptions = useMemo(() => getAvailableOptions(), [getAvailableOptions]);

  // Effect to load recent and saved searches
  useEffect(() => {
    const storedRecent = localStorage.getItem('gmail-recent-searches');
    const storedSaved = localStorage.getItem('gmail-saved-searches');

    if (storedRecent) {
      setRecentSearches(JSON.parse(storedRecent));
    }
    if (storedSaved) {
      setSavedSearches(JSON.parse(storedSaved));
    }
  }, []);

  // Effect to perform search when filters or search term changes
  useEffect(() => {
    performSearch();
  }, [performSearch]);

  return (
    <Box bg={bgColor} border="1px" borderColor={borderColor} borderRadius="lg" p={4}>
      {/* Main Search Bar */}
      <VStack spacing={4} align="stretch">
        <HStack spacing={3}>
          <InputGroup flex={1}>
            <InputLeftElement pointerEvents="none">
              <SearchIcon color="gray.400" />
            </InputLeftElement>
            <Input
              placeholder={`Search ${dataType}...`}
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                handleFilterChange({ searchTerm: e.target.value });
              }}
              onKeyPress={(e) => {
