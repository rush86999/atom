/**
 * ATOM Search Types
 * Type definitions for universal search
 */

export interface AtomSearchResult {
  id: string;
  type: 'file' | 'issue' | 'commit' | 'message' | 'task' | 'document' | 'project' | 'user';
  title: string;
  description?: string;
  content?: string;
  source: string; // integration name
  sourceIcon: any; // React component
  sourceColor: string;
  url?: string;
  createdAt: string;
  updatedAt: string;
  author?: {
    id: string;
    name: string;
    username: string;
    avatar?: string;
    email?: string;
  };
  metadata: Record<string, any>;
  highlights?: string[];
  score?: number; // relevance score 0-100
  permissions?: {
    canView: boolean;
    canEdit: boolean;
    canDelete: boolean;
    canShare: boolean;
  };
  tags?: string[];
  category?: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  status?: 'active' | 'pending' | 'completed' | 'archived' | 'deleted';
  size?: number; // bytes
  mimeType?: string;
}

export interface AtomSearchFilters {
  // Source filtering
  sources: string[];
  
  // Type filtering
  types: string[];
  
  // Date range filtering
  dateRange: {
    from: string;
    to: string;
  };
  
  // Author filtering
  authors: string[];
  
  // Project filtering
  projects: string[];
  
  // Tag filtering
  tags: string[];
  
  // Status filtering
  status: string[];
  
  // Priority filtering
  priority: string[];
  
  // Content filtering
  contentType: string[];
  mimeType: string[];
  
  // Size filtering
  sizeRange?: {
    min: number;
    max: number;
  };
  
  // Special filters
  includeArchived: boolean;
  includeDeleted: boolean;
  includePrivate: boolean;
  includeShared: boolean;
  includePublic: boolean;
  
  // Location filtering
  locations: string[];
  paths: string[];
  
  // Integration-specific filters
  integrationFilters?: {
    [integration: string]: Record<string, any>;
  };
}

export interface AtomSearchSort {
  field: string;
  direction: 'asc' | 'desc';
}

export interface AtomSearchStats {
  total: number;
  sources: number;
  types: number;
  time: number;
  aggregated?: {
    [source: string]: {
      count: number;
      time: number;
      types: string[];
    };
  };
}

export interface AtomSavedSearch {
  id: string;
  name: string;
  description?: string;
  query: string;
  filters: AtomSearchFilters;
  sort: AtomSearchSort;
  createdAt: string;
  lastUsed?: string;
  usageCount: number;
  isPublic?: boolean;
  createdBy?: string;
  tags?: string[];
}

export interface AtomSearchHistory {
  query: string;
  timestamp: string;
  resultCount: number;
  sources: string[];
  types: string[];
}

export interface AtomSearchSuggestion {
  text: string;
  type: 'query' | 'filter' | 'source' | 'type';
  count: number;
  lastUsed?: string;
  metadata?: Record<string, any>;
}

export interface AtomSearchConfig {
  // Search behavior
  maxResults: number;
  defaultSort: AtomSearchSort;
  enableFuzzySearch: boolean;
  enablePhoneticSearch: boolean;
  enableSemanticSearch: boolean;
  searchTimeout: number;
  
  // UI behavior
  showHighlights: boolean;
  showMetadata: boolean;
  showPreview: boolean;
  groupResults: boolean;
  groupBy: string;
  
  // Performance
  enableCaching: boolean;
  cacheTimeout: number;
  enablePrefetch: boolean;
  batchSize: number;
  
  // Privacy
  trackSearches: boolean;
  retainHistory: number; // days
  anonymizeHistory: boolean;
  
  // Integrations
  enabledSources: string[];
  sourcePriorities: { [source: string]: number };
  sourceWeights: { [source: string]: number };
}

export interface AtomSearchContext {
  query: string;
  filters: AtomSearchFilters;
  sort: AtomSearchSort;
  results: AtomSearchResult[];
  stats: AtomSearchStats;
  loading: boolean;
  error?: string;
  suggestions: AtomSearchSuggestion[];
  history: AtomSearchHistory[];
  savedSearches: AtomSavedSearch[];
  config: AtomSearchConfig;
  
  // Actions
  search: (query: string) => Promise<void>;
  updateFilters: (filters: Partial<AtomSearchFilters>) => void;
  updateSort: (sort: Partial<AtomSearchSort>) => void;
  clearResults: () => void;
  saveSearch: (name: string) => Promise<void>;
  deleteSavedSearch: (id: string) => Promise<void>;
  loadSavedSearch: (id: string) => Promise<void>;
  exportResults: (format: 'json' | 'csv' | 'xml') => Promise<void>;
  shareSearch: (searchId: string) => Promise<void>;
}

// Integration-specific result types
export interface GitLabSearchResult extends AtomSearchResult {
  source: 'gitlab';
  metadata: {
    projectId: number;
    projectName: string;
    visibility: string;
    archived: boolean;
    starCount?: number;
    forksCount?: number;
    openIssuesCount?: number;
    iid?: number; // issue/merge request number
    ref?: string; // branch/ref name
    status?: string; // pipeline status
    labels?: Array<{
      id: number;
      title: string;
      color: string;
    }>;
    milestone?: {
      id: number;
      title: string;
    };
    assignees?: Array<{
      id: number;
      name: string;
      username: string;
      avatar_url: string;
    }>;
    reviewers?: Array<{
      id: number;
      name: string;
      username: string;
      avatar_url: string;
    }>;
    web_url?: string;
  };
}

export interface GitHubSearchResult extends AtomSearchResult {
  source: 'github';
  metadata: {
    repoId: number;
    repoName: string;
    fullName: string;
    private: boolean;
    stargazersCount?: number;
    forksCount?: number;
    openIssuesCount?: number;
    language?: string;
    topics?: string[];
    number?: number; // issue/PR number
    state?: string;
    labels?: Array<{
      name: string;
      color: string;
    }>;
    assignees?: Array<{
      login: string;
      avatar_url: string;
    }>;
    reviewers?: Array<{
      login: string;
      avatar_url: string;
    }>;
    html_url?: string;
  };
}

export interface SlackSearchResult extends AtomSearchResult {
  source: 'slack';
  metadata: {
    channelId: string;
    channelName: string;
    teamId: string;
    teamName: string;
    threadTs?: string;
    reactions?: Array<{
      name: string;
      count: number;
      users: string[];
    }>;
    attachments?: Array<{
      id: string;
      title: string;
      title_link?: string;
      text: string;
      service_name: string;
    }>;
    blocks?: Array<any>;
  };
}

export interface NotionSearchResult extends AtomSearchResult {
  source: 'notion';
  metadata: {
    pageId: string;
    databaseId?: string;
    properties: Record<string, any>;
    icon?: string;
    cover?: string;
    archived: boolean;
    created_time?: string;
    last_edited_time?: string;
    parent?: {
      type: string;
      [key: string]: any;
    };
  };
}

export interface GmailSearchResult extends AtomSearchResult {
  source: 'gmail';
  metadata: {
    messageId: string;
    threadId: string;
    subject: string;
    from: string;
    to: string[];
    cc: string[];
    bcc: string[];
    snippet: string;
    attachments?: Array<{
      filename: string;
      size: number;
      mimeType: string;
      attachmentId: string;
    }>;
    labels: string[];
    starred: boolean;
    unread: boolean;
    important: boolean;
    spam: boolean;
    trash: boolean;
  };
}

export interface JiraSearchResult extends AtomSearchResult {
  source: 'jira';
  metadata: {
    issueId: string;
    key: string;
    projectKey: string;
    projectName: string;
    issueType: {
      id: string;
      name: string;
      iconUrl: string;
    };
    status: {
      id: string;
      name: string;
      statusCategory: {
        id: string;
        key: string;
        colorName: string;
      };
    };
    priority?: {
      id: string;
      name: string;
      iconUrl: string;
    };
    assignee?: {
      id: string;
      name: string;
      emailAddress: string;
      avatarUrl: string;
    };
    reporter: {
      id: string;
      name: string;
      emailAddress: string;
      avatarUrl: string;
    };
    labels: string[];
    components: Array<{
      id: string;
      name: string;
    }>;
    fixVersions: Array<{
      id: string;
      name: string;
    }>;
    dueDate?: string;
    created: string;
    updated: string;
  };
}

// Search aggregation types
export interface AtomSearchAggregation {
  field: string;
  name: string;
  buckets: Array<{
    key: string;
    doc_count: number;
    selected: boolean;
  }>;
}

export interface AtomSearchFacets {
  sources: AtomSearchAggregation;
  types: AtomSearchAggregation;
  authors: AtomSearchAggregation;
  projects: AtomSearchAggregation;
  tags: AtomSearchAggregation;
  status: AtomSearchAggregation;
  priority: AtomSearchAggregation;
  dates: AtomSearchAggregation;
}

// Search query types
export interface AtomSearchQuery {
  text: string;
  filters: AtomSearchFilters;
  sort: AtomSearchSort;
  offset?: number;
  limit?: number;
  highlight?: boolean;
  aggregate?: boolean;
  facets?: string[];
  explain?: boolean;
}

// Search response types
export interface AtomSearchResponse {
  results: AtomSearchResult[];
  total: number;
  took: number;
  aggregations?: {
    facets: AtomSearchFacets;
  };
  suggestions?: AtomSearchSuggestion[];
  scroll?: string; // for pagination
  explain?: any; // for debugging
}

// Search index types
export interface AtomSearchIndex {
  name: string;
  source: string;
  type: string;
  fields: string[];
  config: Record<string, any>;
  status: 'building' | 'ready' | 'error';
  size: number; // bytes
  docCount: number;
  lastUpdated: string;
  version: string;
}

// Search analytics types
export interface AtomSearchAnalytics {
  query: string;
  timestamp: string;
  userId?: string;
  sessionId: string;
  resultsCount: number;
  clickCount: number;
  timeSpent: number; // ms
  filters: string[];
  sources: string[];
  types: string[];
  resultIds?: string[];
  clickedResultIds?: string[];
  bounced: boolean; // no clicks
  converted: boolean; // found what needed
}

// Search alert types
export interface AtomSearchAlert {
  id: string;
  name: string;
  description?: string;
  query: string;
  filters: AtomSearchFilters;
  frequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
  enabled: boolean;
  lastTriggered?: string;
  triggerCount: number;
  notifications: {
    email?: boolean;
    push?: boolean;
    webhook?: string;
  };
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export default AtomSearchResult;