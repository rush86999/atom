/**
 * ATOM Jira Integration - TypeScript Types
 * Project Management → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Jira API Types
export interface JiraProject {
  id: string;
  key: string;
  name: string;
  projectTypeKey: string;
  simplified: boolean;
  avatarUrls: JiraAvatarUrls;
  projectCategory: {
    id: string;
    name: string;
    description: string;
  };
  lead: JiraUser;
  url: string;
  assigneeType: 'PROJECT_LEAD' | 'UNASSIGNED';
  style: string;
  issueTypes: JiraIssueType[];
  components: JiraComponent[];
  versions: JiraVersion[];
  releaseCenter?: {
    id: string;
    name: string;
    url: string;
  };
}

export interface JiraIssueType {
  id: string;
  name: string;
  description: string;
  iconUrl: string;
  avatarId: number;
  subtask: boolean;
  fieldId: string;
  scope: JiraScope;
}

export interface JiraScope {
  type: 'PROJECT' | 'GLOBAL';
  project?: JiraProject;
}

export interface JiraComponent {
  id: string;
  name: string;
  description: string;
  lead?: JiraUser;
  assigneeType: 'PROJECT_DEFAULT' | 'COMPONENT_LEAD' | 'UNASSIGNED';
  realAssigneeType: 'PROJECT_DEFAULT' | 'COMPONENT_LEAD' | 'UNASSIGNED';
  realAssignee?: JiraUser;
  isAssigneeTypeValid: boolean;
  project: string;
  projectId: number;
}

export interface JiraVersion {
  id: string;
  description: string;
  name: string;
  archived: boolean;
  released: boolean;
  releaseDate?: string;
  userReleaseDate?: string;
  overdue: boolean;
}

export interface JiraAvatarUrls {
  '16x16': string;
  '24x24': string;
  '32x32': string;
  '48x48': string;
}

export interface JiraIssue {
  id: string;
  key: string;
  fields: JiraIssueFields;
  self: string;
  renderedFields?: JiraRenderedFields;
  transitions?: JiraTransition[];
}

export interface JiraIssueFields {
  summary: string;
  description?: string;
  status: JiraStatus;
  priority?: JiraPriority;
  issueType: JiraIssueType;
  created: string;
  updated: string;
  resolution?: JiraResolution;
  resolutiondate?: string;
  reporter: JiraUser;
  assignee?: JiraUser;
  project: JiraProject;
  components: JiraComponent[];
  fixVersions: JiraVersion[];
  labels: string[];
  environment?: string;
  duedate?: string;
  watches: {
    watchCount: number;
    isWatching: boolean;
  };
  timeoriginalestimate?: number;
  timeestimate?: number;
  timespent?: number;
  aggregateprogress?: {
    progress: number;
    total: number;
  };
  workratio?: number;
  subtasks?: JiraIssue[];
  issuelinks?: JiraIssueLink[];
  attachments?: JiraAttachment[];
  comment?: {
    comments: JiraComment[];
    maxResults: number;
    startAt: number;
    total: number;
  };
  history?: JiraHistoryItem[];
}

export interface JiraStatus {
  id: string;
  name: string;
  description: string;
  iconUrl: string;
  statusCategory: JiraStatusCategory;
}

export interface JiraStatusCategory {
  id: number;
  key: 'new' | 'indeterminate' | 'done';
  colorName: string;
  name: string;
}

export interface JiraPriority {
  id: string;
  name: string;
  description: string;
  iconUrl: string;
  statusColor: string;
}

export interface JiraResolution {
  id: string;
  name: string;
  description: string;
}

export interface JiraUser {
  self: string;
  key: string;
  accountId: string;
  name: string;
  emailAddress?: string;
  displayName: string;
  active: boolean;
  timeZone: string;
  avatarUrls: JiraAvatarUrls;
  applicationRoles?: JiraApplicationRoles;
}

export interface JiraApplicationRoles {
  items: JiraApplicationRole[];
  maxResults: number;
  startAt: number;
  total: number;
}

export interface JiraApplicationRole {
  key: string;
  name: string;
  default: boolean;
  defined: boolean;
  numberOfActors: number;
}

export interface JiraTransition {
  id: string;
  name: string;
  to: {
    id: string;
    name: string;
    statusCategory: JiraStatusCategory;
  };
  fields?: JiraField[];
  screen?: {
    id: string;
    name: string;
  };
  conditions?: JiraCondition[];
  looped: boolean;
  hasScreen: boolean;
  isGlobal: boolean;
  isInitial: boolean;
  isAvailable: boolean;
  isHidden: boolean;
}

export interface JiraField {
  id: string;
  key: string;
  name: string;
  required: boolean;
  defaultValue?: any;
  type: string;
  operations?: string[];
  allowedValues?: any[];
  autoCompleteUrl?: string;
  schema?: JiraSchema;
}

export interface JiraSchema {
  type: string;
  items?: string;
  system?: string;
  custom?: string;
  customId?: number;
  configuration?: Record<string, any>;
}

export interface JiraCondition {
  type: string;
  condition: string;
}

export interface JiraRenderedFields {
  summary: string;
  description?: string;
  environment?: string;
  comment?: {
    comments: JiraComment[];
  };
}

export interface JiraIssueLink {
  id: string;
  type: JiraIssueLinkType;
  inwardIssue?: JiraIssue;
  outwardIssue?: JiraIssue;
}

export interface JiraIssueLinkType {
  id: string;
  name: string;
  inward: string;
  outward: string;
  self: string;
}

export interface JiraAttachment {
  id: string;
  self: string;
  filename: string;
  author: JiraUser;
  created: string;
  size: number;
  mimeType: string;
  content: string;
  thumbnail?: string;
}

export interface JiraComment {
  id: string;
  self: string;
  author: JiraUser;
  body: string;
  updateAuthor?: JiraUser;
  created: string;
  updated?: string;
  jsdPublic?: boolean;
  jsdAuthorCanSeeComment?: boolean;
  visibility?: JiraVisibility;
}

export interface JiraVisibility {
  type: 'group' | 'role';
  value: string;
  identifier: string;
}

export interface JiraHistoryItem {
  id: string;
  author: JiraUser;
  created: string;
  items: JiraHistoryItemChange[];
}

export interface JiraHistoryItemChange {
  field: string;
  fieldtype: string;
  from?: string;
  fromString?: string;
  to?: string;
  toString?: string;
}

export interface JiraBoard {
  id: number;
  name: string;
  type: string;
  self: string;
  location?: JiraBoardLocation;
  filter?: JiraFilter;
  columnConfig?: JiraColumnConfig;
  rapidListConfig?: JiraRapidListConfig;
  swimlaneConfig?: JiraSwimlaneConfig;
  sprint?: JiraSprint;
}

export interface JiraBoardLocation {
  type: 'project' | 'user';
  projectKeyOrId?: string;
  projectName?: string;
  projectId?: string;
  displayName?: string;
  projectAvatarUrl?: string;
  projectTypeKey?: string;
}

export interface JiraFilter {
  id: string;
  name: string;
  description: string;
  owner?: JiraUser;
  jql: string;
  viewUrl: string;
  searchUrl: string;
  favourite?: boolean;
  sharePermissions?: JiraSharePermission[];
  subscriptions?: JiraSubscription[];
}

export interface JiraSharePermission {
  id: number;
  type: 'project' | 'group' | 'authenticated' | 'global';
  project?: JiraProject;
  group?: JiraGroup;
}

export interface JiraGroup {
  name: string;
  self: string;
  users?: JiraUser[];
}

export interface JiraSubscription {
  id: number;
  user: JiraUser;
  group?: JiraGroup;
}

export interface JiraColumnConfig {
  columns: JiraColumn[];
  constraintType: 'none' | 'issueCount' | 'issueCountExclusive';
  columnsCount: number;
}

export interface JiraColumn {
  id: string;
  name: string;
  statuses: JiraStatus[];
  max: number;
  min: number;
}

export interface JiraRapidListConfig {
  showAcceptedIssue: boolean;
  showSprintName: boolean;
  key: string;
  viewMapping: Record<string, JiraViewMapping>;
}

export interface JiraViewMapping {
  viewType: string;
  query: string;
  name: string;
}

export interface JiraSwimlaneConfig {
  swimlaneBasedField?: JiraField;
  ignoreIssuesWithEmptySwimlaneFields: boolean;
  useCustomField?: boolean;
  customFieldId?: string;
}

export interface JiraSprint {
  id: number;
  name: string;
  state: 'future' | 'active' | 'closed';
  startDate?: string;
  endDate?: string;
  completeDate?: string;
  originBoardId: number;
  goal?: string;
  self?: string;
}

export interface JiraSearchResponse {
  startAt: number;
  maxResults: number;
  total: number;
  issues: JiraIssue[];
  warningMessages?: string[];
  names?: Record<string, any>;
  schema?: JiraSearchSchema;
}

export interface JiraSearchSchema {
  id: string;
  type: string;
  items?: string;
  custom?: string;
  customId?: number;
  system?: string;
  properties: JiraSchemaProperties;
}

export interface JiraSchemaProperties {
  [key: string]: JiraSchemaProperty;
}

export interface JiraSchemaProperty {
  key: string;
  system?: string;
  type: string;
  custom?: string;
  name?: string;
  customId?: number;
  priority?: number;
  searchable: boolean;
  sortable: boolean;
}

// Jira Configuration Types
export interface JiraConfig {
  // API Configuration
  apiBaseUrl: string;
  jqlApiUrl: string;
  
  // Authentication
  serverUrl: string;
  username?: string;
  apiToken?: string;
  oauthToken?: string;
  
  // Jira-specific settings
  defaultProject?: string;
  defaultAssignee?: string;
  defaultPriority?: string;
  defaultIssueType?: string;
  
  // Issue Discovery
  includeSubtasks: boolean;
  includeArchived: boolean;
  maxIssuesPerProject: number;
  issueDateRange?: {
    start: Date;
    end: Date;
  };
  
  // Project Filtering
  includedProjects: string[];
  excludedProjects: string[];
  projectTypes: string[];
  
  // Search Settings
  jqlQuery?: string;
  searchFields: string[];
  maxSearchResults: number;
  
  // Issue Processing
  includeComments: boolean;
  includeAttachments: boolean;
  includeHistory: boolean;
  includeLinkedIssues: boolean;
  maxAttachmentSize: number;
  
  // Real-time Settings
  useWebhooks: boolean;
  webhookEvents: string[];
  webhookSecret?: string;
  
  // Rate Limiting
  apiCallsPerSecond: number;
  useBatchRequests: boolean;
  
  // Platform-specific
  tauriCommands?: {
    createIssue: string;
    updateIssue: string;
    downloadAttachment: string;
  };
}

// Enhanced Types
export interface JiraIssueEnhanced extends JiraIssue {
  source: 'jira';
  discoveredAt: string;
  processedAt?: string;
  commentsProcessed?: boolean;
  attachmentsProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  linkInfo?: JiraLinkInfo;
  attachmentInfo?: JiraAttachmentInfo;
  commentInfo?: JiraCommentInfo;
  historyInfo?: JiraHistoryInfo;
  markdownContent?: string;
  plainTextContent?: string;
}

export interface JiraLinkInfo {
  linkedIssues: JiraIssue[];
  blockedBy: JiraIssue[];
  blocks: JiraIssue[];
  duplicates: JiraIssue[];
  isDuplicatedBy: JiraIssue[];
}

export interface JiraAttachmentInfo {
  totalAttachments: number;
  totalSize: number;
  processedAttachments: JiraAttachment[];
  fileTypes: string[];
  hasImages: boolean;
  hasDocuments: boolean;
}

export interface JiraCommentInfo {
  totalComments: number;
  processedComments: JiraComment[];
  totalAuthors: string[];
  lastCommentDate?: string;
  resolutionComments?: number;
}

export interface JiraHistoryInfo {
  totalChanges: number;
  processedChanges: JiraHistoryItemChange[];
  statusChanges: number;
  assigneeChanges: number;
  priorityChanges: number;
  resolutionChanges: number;
}

// Component Props
export interface AtomJiraManagerProps extends AtomIntegrationProps<JiraConfig> {
  // Jira-specific events
  onIssueCreated?: (issue: JiraIssue) => void;
  onIssueUpdated?: (issue: JiraIssue) => void;
  onIssueDeleted?: (issueId: string) => void;
  onIssueAssigned?: (issue: JiraIssue, assignee: JiraUser) => void;
  onIssueStatusChanged?: (issue: JiraIssue, status: JiraStatus) => void;
  onCommentAdded?: (comment: JiraComment, issueId: string) => void;
  onAttachmentAdded?: (attachment: JiraAttachment, issueId: string) => void;
  onProjectCreated?: (project: JiraProject) => void;
  onBoardUpdated?: (board: JiraBoard) => void;
}

export interface AtomJiraDataSourceProps extends AtomIntegrationProps<JiraConfig, AtomJiraIngestionConfig> {
  // Ingestion-specific events
  onIssueDiscovered?: (issue: JiraIssueEnhanced) => void;
  onProjectDiscovered?: (project: JiraProject) => void;
  onBoardDiscovered?: (board: JiraBoard) => void;
  onCommentDiscovered?: (comment: JiraComment) => void;
  onAttachmentDiscovered?: (attachment: JiraAttachment) => void;
}

// State Types
export interface AtomJiraState extends AtomIntegrationState {
  projects: JiraProject[];
  issues: JiraIssue[];
  boards: JiraBoard[];
  sprints: JiraSprint[];
  users: JiraUser[];
  filters: JiraFilter[];
  currentProject?: JiraProject;
  currentBoard?: JiraBoard;
  selectedItems: (JiraIssue | JiraProject | JiraBoard)[];
  searchResults: JiraSearchResponse;
  sortBy: JiraSortField;
  sortOrder: JiraSortOrder;
  viewMode: 'grid' | 'list' | 'kanban';
  filters: JiraFilters;
}

export interface AtomJiraDataSourceState extends AtomIntegrationState {
  discoveredIssues: JiraIssueEnhanced[];
  discoveredProjects: JiraProject[];
  discoveredBoards: JiraBoard[];
  discoveredComments: JiraComment[];
  discoveredAttachments: JiraAttachment[];
  ingestionQueue: JiraIssueEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalIssues: number;
    totalProjects: number;
    totalBoards: number;
    totalComments: number;
    totalAttachments: number;
    ingestedIssues: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomJiraIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'jira';
  
  // API Configuration
  apiBaseUrl: string;
  jqlApiUrl: string;
  serverUrl: string;
  username?: string;
  apiToken?: string;
  oauthToken?: string;
  
  // Project Discovery
  includedProjects: string[];
  excludedProjects: string[];
  projectTypes: string[];
  
  // Issue Discovery
  jqlQuery?: string;
  includeSubtasks: boolean;
  includeArchived: boolean;
  maxIssuesPerProject: number;
  issueDateRange?: {
    start: Date;
    end: Date;
  };
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Processing
  includeComments: boolean;
  includeAttachments: boolean;
  includeHistory: boolean;
  includeLinkedIssues: boolean;
  maxAttachmentSize: number;
  extractMarkdown: boolean;
  
  // Sync Settings
  useWebhooks: boolean;
  webhookEvents: string[];
  webhookSecret?: string;
  syncInterval: number;
  incrementalSync: boolean;
  
  // Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

// API Types
export interface AtomJiraAPI extends AtomIntegrationAPI<JiraIssue, JiraConfig> {
  // Authentication
  authenticate: (authCode?: string) => Promise<JiraAuthResponse>;
  
  // Project Operations
  getProjects: (startAt?: number, maxResults?: number) => Promise<JiraProject[]>;
  getProject: (projectId: string) => Promise<JiraProject>;
  createProject: (project: Partial<JiraProject>) => Promise<JiraProject>;
  
  // Issue Operations
  getIssues: (jql: string, startAt?: number, maxResults?: number, fields?: string[]) => Promise<JiraSearchResponse>;
  getIssue: (issueId: string) => Promise<JiraIssue>;
  createIssue: (issue: Partial<JiraIssue>) => Promise<JiraIssue>;
  updateIssue: (issueId: string, issue: Partial<JiraIssue>) => Promise<JiraIssue>;
  deleteIssue: (issueId: string) => Promise<void>;
  assignIssue: (issueId: string, assignee?: string) => Promise<JiraIssue>;
  transitionIssue: (issueId: string, transition: { id: string; name: string; }) => Promise<JiraIssue>;
  
  // Comment Operations
  getComments: (issueId: string) => Promise<JiraComment[]>;
  addComment: (issueId: string, comment: string) => Promise<JiraComment>;
  updateComment: (commentId: string, comment: string) => Promise<JiraComment>;
  deleteComment: (commentId: string) => Promise<void>;
  
  // Attachment Operations
  getAttachment: (attachmentId: string) => Promise<JiraAttachment>;
  downloadAttachment: (attachmentId: string) => Promise<JiraAttachment>;
  addAttachment: (issueId: string, file: File) => Promise<JiraAttachment>;
  deleteAttachment: (attachmentId: string) => Promise<void>;
  
  // Board Operations
  getBoards: (startAt?: number, maxResults?: number) => Promise<JiraBoard[]>;
  getBoard: (boardId: string) => Promise<JiraBoard>;
  getBoardIssues: (boardId: string, startAt?: number, maxResults?: number) => Promise<JiraIssue[]>;
  
  // User Operations
  getUsers: (startAt?: number, maxResults?: number) => Promise<JiraUser[]>;
  getUser: (username: string) => Promise<JiraUser>;
  searchUsers: (query: string, maxResults?: number) => Promise<JiraUser[]>;
  
  // Search Operations
  searchIssues: (jql: string, fields?: string[]) => Promise<JiraSearchResponse>;
  searchProjects: (query: string) => Promise<JiraProject[]>;
  searchBoards: (query: string) => Promise<JiraBoard[]>;
}

export interface JiraAuthResponse {
  accessToken?: string;
  refreshToken?: string;
  expiresIn?: number;
  tokenType?: string;
  scope?: string;
}

// Hook Types
export interface AtomJiraHookReturn extends AtomIntegrationHookReturn<JiraIssue> {
  state: AtomJiraState;
  api: AtomJiraAPI;
  actions: AtomJiraActions;
  config: JiraConfig;
}

export interface AtomJiraDataSourceHookReturn extends AtomIntegrationHookReturn<JiraIssueEnhanced> {
  state: AtomJiraDataSourceState;
  api: AtomJiraAPI;
  actions: AtomJiraDataSourceActions;
  config: AtomJiraIngestionConfig;
}

// Actions Types
export interface AtomJiraActions {
  // Issue Actions
  createIssue: (issue: Partial<JiraIssue>) => Promise<JiraIssue>;
  updateIssue: (issueId: string, issue: Partial<JiraIssue>) => Promise<JiraIssue>;
  deleteIssues: (issueIds: string[]) => Promise<void>;
  assignIssues: (issueIds: string[], assignee?: string) => Promise<void>;
  transitionIssues: (issueIds: string[], transitionId: string) => Promise<void>;
  
  // Comment Actions
  addComment: (issueId: string, comment: string) => Promise<JiraComment>;
  updateComment: (commentId: string, comment: string) => Promise<JiraComment>;
  deleteComments: (commentIds: string[]) => Promise<void>;
  
  // Navigation Actions
  navigateToProject: (project: JiraProject) => void;
  navigateToBoard: (board: JiraBoard) => void;
  navigateToIssue: (issue: JiraIssue) => void;
  
  // Search Actions
  searchIssues: (jql: string, fields?: string[]) => Promise<JiraSearchResponse>;
  searchProjects: (query: string) => Promise<JiraProject[]>;
  searchBoards: (query: string) => Promise<JiraBoard[]>;
  
  // UI Actions
  selectItems: (items: (JiraIssue | JiraProject | JiraBoard)[]) => void;
  sortBy: (field: JiraSortField, order: JiraSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'kanban') => void;
  setFilters: (filters: JiraFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomJiraDataSourceActions {
  // Discovery Actions
  discoverIssues: (projectIds?: string[], jql?: string) => Promise<JiraIssueEnhanced[]>;
  discoverProjects: () => Promise<JiraProject[]>;
  discoverBoards: () => Promise<JiraBoard[]>;
  discoverComments: (issueIds: string[]) => Promise<JiraComment[]>;
  discoverAttachments: (issueIds: string[]) => Promise<JiraAttachment[]>;
  
  // Ingestion Actions
  ingestIssues: (issues: JiraIssueEnhanced[]) => Promise<void>;
  ingestProject: (projectId: string) => Promise<void>;
  ingestBoard: (boardId: string) => Promise<void>;
  
  // Sync Actions
  syncIssues: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface JiraFilters {
  projects: string[];
  issueTypes: string[];
  statuses: string[];
  priorities: string[];
  assignees: string[];
  labels: string[];
  components: string[];
  dateRange?: {
    start: Date;
    end: Date;
  };
  jqlQuery?: string;
}

// Sort Types
export type JiraSortField = 'key' | 'summary' | 'status' | 'priority' | 'assignee' | 'created' | 'updated' | 'dueDate';
export type JiraSortOrder = 'asc' | 'desc';

// Error Types
export class AtomJiraError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomJiraError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const jiraConfigDefaults: Partial<JiraConfig> = {
  apiBaseUrl: '/rest/api/3',
  jqlApiUrl: '/rest/api/3/search',
  includeSubtasks: true,
  includeArchived: false,
  maxIssuesPerProject: 1000,
  includedProjects: [],
  excludedProjects: [],
  projectTypes: ['software', 'service_desk', 'business'],
  searchFields: ['summary', 'description', 'comment', 'status', 'priority', 'assignee'],
  maxSearchResults: 100,
  includeComments: true,
  includeAttachments: true,
  includeHistory: true,
  includeLinkedIssues: true,
  maxAttachmentSize: 50 * 1024 * 1024, // 50MB
  useWebhooks: true,
  webhookEvents: ['jira:issue_created', 'jira:issue_updated', 'jira:comment_added', 'jira:attachment_added'],
  apiCallsPerSecond: 60, // Jira rate limit
  useBatchRequests: true
};

export const jiraIngestionConfigDefaults: Partial<AtomJiraIngestionConfig> = {
  sourceId: 'jira-integration',
  sourceName: 'Jira',
  sourceType: 'jira',
  apiBaseUrl: '/rest/api/3',
  jqlApiUrl: '/rest/api/3/search',
  includedProjects: [],
  excludedProjects: [],
  projectTypes: ['software', 'service_desk', 'business'],
  jqlQuery: 'status != "Done" ORDER BY created DESC',
  includeSubtasks: true,
  includeArchived: false,
  maxIssuesPerProject: 1000,
  autoIngest: true,
  ingestInterval: 1800000, // 30 minutes
  realTimeIngest: true,
  batchSize: 50,
  maxConcurrentIngestions: 2,
  includeComments: true,
  includeAttachments: true,
  includeHistory: true,
  includeLinkedIssues: true,
  maxAttachmentSize: 50 * 1024 * 1024, // 50MB
  extractMarkdown: true,
  useWebhooks: true,
  webhookEvents: ['jira:issue_created', 'jira:issue_updated', 'jira:comment_added', 'jira:attachment_added'],
  syncInterval: 600000, // 10 minutes
  incrementalSync: true,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const jiraSearchDefaults = {
  fields: ['summary', 'description', 'status', 'priority', 'assignee', 'project', 'created', 'updated'],
  maxResults: 50,
  startAt: 0
};

export const jiraSortFields: JiraSortField[] = ['key', 'summary', 'status', 'priority', 'assignee', 'created', 'updated', 'dueDate'];
export const jiraSortOrders: JiraSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';