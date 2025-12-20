/**
 * Microsoft 365 Integration Types
 * Type definitions for Microsoft 365 API and integration components
 */

// Core Microsoft 365 Types
export interface Microsoft365User {
  id: string;
  displayName: string;
  mail: string | null;
  userPrincipalName: string;
  jobTitle: string | null;
  department: string | null;
  officeLocation: string | null;
  companyName: string | null;
  lastSignInDateTime: string | null;
  usageLocation: string | null;
  accountEnabled: boolean;
  userType: string;
}

export interface Microsoft365Team {
  id: string;
  displayName: string;
  description: string | null;
  visibility: 'public' | 'private';
  mailNickname: string | null;
  createdDateTime: string;
  teamType: string;
  isArchived: boolean;
  memberCount: number;
  channelCount: number;
  owners: Microsoft365User[];
  members: Microsoft365User[];
  settings?: Microsoft365TeamSettings;
}

export interface Microsoft365Channel {
  id: string;
  displayName: string;
  description: string | null;
  teamId: string;
  teamName: string;
  type: 'standard' | 'private' | 'shared';
  membershipType: 'standard' | 'private' | 'shared';
  isFavoriteByDefault: boolean;
  email: string | null;
  webUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  tenantId: string;
}

export interface Microsoft365Message {
  id: string;
  messageType: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  subject: string;
  summary: string;
  importance: 'low' | 'normal' | 'high';
  locale: string;
  body: {
    content: string;
    contentType: 'text' | 'html';
  };
  attachments: Microsoft365Attachment[];
  from: Microsoft365User;
  toRecipients: Microsoft365User[];
  ccRecipients: Microsoft365User[];
  bccRecipients: Microsoft365User[];
  conversationId: string;
  threadId: string;
}

export interface Microsoft365Document {
  id: string;
  name: string;
  webUrl: string;
  size: number;
  createdDateTime: string;
  lastModifiedDateTime: string;
  contentType: string;
  parentReference?: {
    driveId: string;
    driveType: string;
    id: string;
    name: string;
    path: string;
  };
  file?: {
    mimeType: string;
    hashes: {
      sha1Hash: string;
      quickXorHash: string;
    };
  };
  folder?: {
    childCount: number;
    view: {
      viewType: string;
      sortBy: string;
      sortOrder: string;
    };
  };
  package?: {
    type: string;
  };
  sharing: Microsoft365SharingInfo;
}

export interface Microsoft365Event {
  id: string;
  subject: string;
  body: {
    contentType: string;
    content: string;
  };
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location?: {
    displayName: string;
    address: {
      street: string;
      city: string;
      state: string;
      countryOrRegion: string;
      postalCode: string;
    };
    coordinates?: {
      latitude: number;
      longitude: number;
    };
  };
  attendees: Microsoft365Attendee[];
  organizer: Microsoft365User;
  isAllDay: boolean;
  sensitivity: 'normal' | 'personal' | 'private' | 'confidential';
  showAs: 'busy' | 'tentative' | 'away' | 'workingElsewhere';
  recurrence?: Microsoft365Recurrence;
  seriesMasterId?: string;
  occurrenceId?: string;
  canceledOccurrences?: string[];
  transactionId?: string;
}

export interface Microsoft365Flow {
  id: string;
  name: string;
  displayName: string;
  description: string;
  status: 'running' | 'stopped' | 'suspended' | 'failed';
  createdTime: string;
  modifiedTime: string;
  lastExecutionTime: string;
  nextExecutionTime: string;
  executionMode: 'automated' | 'triggered' | 'scheduled';
  isEnabled: boolean;
  flowDefinition: {
    triggers: Microsoft365Trigger[];
    actions: Microsoft365Action[];
    description: string;
  };
  environment: 'production' | 'preview';
  version: string;
  apiId: string;
}

export interface ExcelWorksheet {
  id: string;
  name: string;
  position: number;
  visibility: 'visible' | 'hidden' | 'veryHidden';
}

export interface ExcelTable {
  id: string;
  name: string;
  showHeaders: boolean;
  showTotals: boolean;
  style: string;
}

export interface ExcelRange {
  address: string;
  values: any[][];
  formulas: any[][];
  numberFormat: string[][];
  columnCount: number;
  rowCount: number;
}

export interface PowerBIReport {
  id: string;
  name: string;
  webUrl: string;
  embedUrl: string;
  datasetId: string;
}

export interface PowerBIDataset {
  id: string;
  name: string;
  addRowsAPIEnabled: boolean;
  configuredBy: string;
  isRefreshable: boolean;
}

export interface PlannerTask {
  id: string;
  title: string;
  percentComplete: number;
  startDateTime?: string;
  dueDateTime?: string;
  assigneePriority?: string;
  bucketId: string;
  planId: string;
}

export interface PlannerBucket {
  id: string;
  name: string;
  orderHint: string;
  planId: string;
}

export interface Microsoft365Site {
  id: string;
  name: string;
  displayName: string;
  description: string;
  webUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  siteCollection: {
    hostname: string;
    dataLocationCode: string;
    root: {
      serverRelativeUrl: string;
      siteId: string;
    };
  };
  siteGroup?: {
    id: string;
    displayName: string;
    isTeam: boolean;
  };
  sharePointIds?: {
    webId: string;
    siteId: string;
    listId: string;
  };
  permissions: Microsoft365Permission[];
  drive?: {
    id: string;
    name: string;
    webUrl: string;
    driveType: string;
    quota: {
      deleted: number;
      remaining: number;
      state: string;
      storagePlanInformation: {
        planName: string;
        used?: number;
        available?: number;
      };
      total: number;
    };
  };
}

export interface Microsoft365Analytics {
  totalUsers: number;
  activeUsers: number;
  totalFiles: number;
  totalSites: number;
  totalMessages: number;
  totalEvents: number;
  totalFlows: number;
  storageUsed: number;
  storageQuota: number;
  licenseUsage: {
    totalLicenses: number;
    usedLicenses: number;
    availableLicenses: number;
    byLicenseType: Array<{
      licenseType: string;
      total: number;
      used: number;
      available: number;
    }>;
  };
  serviceHealth: {
    status: 'healthy' | 'degraded' | 'unavailable';
    incidents: Array<{
      id: string;
      title: string;
      description: string;
      status: string;
      impact: string;
      startTime: string;
      endTime?: string;
      affectedServices: string[];
    }>;
    advisories: Array<{
      id: string;
      title: string;
      description: string;
      category: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      startTime: string;
      endTime?: string;
      affectedServices: string[];
    }>;
  };
  usageMetrics: {
    teams: {
      totalMessages: number;
      totalMeetings: number;
      totalFiles: number;
      averageMeetingDuration: number;
    };
    outlook: {
      totalEmails: number;
      totalEvents: number;
      averageEmailsPerUser: number;
    };
    onedrive: {
      totalFiles: number;
      totalStorage: number;
      averageFilesPerUser: number;
      fileSyncStatus: {
        synced: number;
        pending: number;
        failed: number;
      };
    };
    sharepoint: {
      totalSites: number;
      totalFiles: number;
      totalPages: number;
      averageFilesPerSite: number;
    };
    powerPlatform: {
      totalFlows: number;
      successfulRuns: number;
      failedRuns: number;
      averageRunTime: number;
    };
  };
}

// Supporting Types
export interface Microsoft365Attachment {
  id: string;
  contentType: string;
  name: string;
  size: number;
  isInline: boolean;
  lastModifiedDateTime: string;
  url?: string;
}

export interface Microsoft365SharingInfo {
  shared: boolean;
  sharedWith?: Array<{
    displayName: string;
    email: string;
    siteId: string;
    permission: string;
  }>;
  owner?: {
    displayName: string;
    email: string;
    siteId: string;
  };
}

export interface Microsoft365Attendee {
  type: 'required' | 'optional' | 'resource';
  status: 'accepted' | 'declined' | 'tentativelyAccepted' | 'notResponded';
  emailAddress: {
    name: string;
    address: string;
  };
  responseTime?: string;
  responseComment?: string;
}

export interface Microsoft365Recurrence {
  pattern: {
    type: 'daily' | 'weekly' | 'absoluteMonthly' | 'relativeMonthly' | 'yearly';
    interval: number;
    month?: number;
    dayOfMonth?: number;
    daysOfWeek?: string[];
    firstDayOfWeek?: string;
    dayIndex?: string;
  };
  range: {
    type: 'noEnd' | 'endDate' | 'numbered';
    startDate: string;
    endDate?: string;
    numberOfOccurrences?: number;
    recurrenceTimeZone?: string;
  };
}

export interface Microsoft365Trigger {
  type: string;
  id: string;
  displayName: string;
  description: string;
  configuration: Record<string, any>;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
}

export interface Microsoft365Action {
  type: string;
  id: string;
  displayName: string;
  description: string;
  configuration: Record<string, any>;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
}

export interface Microsoft365Permission {
  id: string;
  roles: string[];
  grantedToIdentities: Array<{
    application: {
      displayName: string;
      id: string;
      appId: string;
    };
    user?: {
      displayName: string;
      id: string;
      email: string;
    };
  }>;
  grantedToIdentitiesV2?: Array<{
    type: string;
    id: string;
    displayName: string;
  }>;
  invitation?: {
    signInRequired: boolean;
    invitedBy: {
      application: {
        displayName: string;
        id: string;
      };
      user: {
        displayName: string;
        id: string;
        email: string;
      };
    };
  };
}

export interface Microsoft365TeamSettings {
  memberAddRestriction: 'everyone' | 'teamAndOrg' | 'team';
  guestCreateUpdateRestriction: 'none' | 'team' | 'teamAndOrg';
  channelDeleteRestriction: 'everyone' | 'team';
  channelRenameRestriction: 'everyone' | 'team';
  allowChannelCreation: boolean;
  allowTeamCreation: boolean;
  allowAddRemoveApps: boolean;
  allowCreateUpdateChannels: boolean;
  allowCreateUpdateRemoveConnectors: boolean;
  allowDeleteChannels: boolean;
  allowTeamMentions: boolean;
}

export interface Microsoft365TeamMember {
  id: string;
  displayName: string;
  roles: string[];
  userId: string;
  email: string;
  tenantId: string;
}

export interface Microsoft365ChannelMessage {
  id: string;
  replyToId?: string;
  messageType: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  subject?: string;
  summary?: string;
  importance: 'normal' | 'high' | 'urgent';
  locale: string;
  from: Microsoft365User;
  body: {
    content: string;
    contentType: 'text' | 'html';
  };
  attachments: Microsoft365Attachment[];
  mentions: Microsoft365Mention[];
  reactions: Microsoft365Reaction[];
  channelIdentity: {
    channelId: string;
    teamId: string;
  };
  etag: string;
}

export interface Microsoft365Mention {
  id: number;
  mentionText: string;
  mentioned: {
    user: {
      displayName: string;
      id: string;
      userIdentityType: string;
    };
    application: {
      displayName: string;
      id: string;
    };
    conversation: {
      id: string;
      conversationIdentityType: string;
    };
    team: {
      id: string;
      displayName: string;
      teamIdentityType: string;
    };
  };
  chatMessage: {
    id: string;
    replyToId?: string;
    messageType: string;
    createdDateTime: string;
    lastModifiedDateTime: string;
    subject?: string;
    summary?: string;
    importance: string;
    locale: string;
  };
};

export interface Microsoft365Reaction {
  reactionType: string;
  createdDateTime: string;
  user: {
    displayName: string;
    id: string;
    userIdentityType: string;
  };
}

// Configuration Types
export interface Microsoft365Config {
  tenantId: string;
  clientId: string;
  clientSecret: string;
  domain?: string;
  apiVersion?: string;
  scopes?: string[];
  features?: {
    teams?: boolean;
    outlook?: boolean;
    onedrive?: boolean;
    sharepoint?: boolean;
    calendar?: boolean;
    powerAutomate?: boolean;
    powerBI?: boolean;
    powerApps?: boolean;
    yammer?: boolean;
    planner?: boolean;
    toDo?: boolean;
    forms?: boolean;
    stream?: boolean;
    loop?: boolean;
    whiteboard?: boolean;
    bookings?: boolean;
    shift?: boolean;
    lists?: boolean;
    project?: boolean;
    visio?: boolean;
  };
  preferences?: {
    defaultTimeZone: string;
    defaultLanguage: string;
    dateFormat: string;
    timeFormat: string;
    theme: 'light' | 'dark' | 'auto';
    notifications: {
      email: boolean;
      push: boolean;
      desktop: boolean;
      teams: boolean;
      outlook: boolean;
    };
    privacy: {
      presence: boolean;
      lastSeen: boolean;
      profileInfo: boolean;
      activityStatus: boolean;
    };
  };
  security?: {
    multiFactorAuth: boolean;
    conditionalAccess: boolean;
    auditLogging: boolean;
    dataLossPrevention: boolean;
    encryption: boolean;
    sessionManagement: boolean;
    deviceManagement: boolean;
    appProtection: boolean;
  };
  governance?: {
    dataRetention: boolean;
    legalHold: boolean;
    compliance: boolean;
    usagePolicies: boolean;
    accessControl: boolean;
    monitoring: boolean;
    reporting: boolean;
  };
  integration?: {
    externalServices: boolean;
    customConnectors: boolean;
    apiManagement: boolean;
    webhooks: boolean;
    powerAutomateFlows: boolean;
    customApplications: boolean;
    thirdPartyIntegrations: boolean;
  };
}

// UI State Types
export interface Microsoft365IntegrationState {
  isAuthenticated: boolean;
  config: Microsoft365Config | null;
  user: Microsoft365User | null;
  accessToken: string | null;
  refreshToken: string | null;
  tokenExpiry: string | null;
  teams: Microsoft365Team[];
  channels: Microsoft365Channel[];
  messages: Microsoft365Message[];
  documents: Microsoft365Document[];
  events: Microsoft365Event[];
  flows: Microsoft365Flow[];
  sites: Microsoft365Site[];
  analytics: Microsoft365Analytics | null;
  loading: boolean;
  error: string | null;
  selectedTeam?: Microsoft365Team;
  selectedChannel?: Microsoft365Channel;
  selectedDocument?: Microsoft365Document;
  selectedEvent?: Microsoft365Event;
  searchQuery?: string;
  filters: Microsoft365Filters;
  permissions: Microsoft365Permission[];
  serviceHealth: {
    status: 'healthy' | 'degraded' | 'unavailable';
    lastUpdated: string;
    incidents: any[];
    advisories: any[];
  };
}

export interface Microsoft365Filters {
  teamIds?: string[];
  channelIds?: string[];
  userIds?: string[];
  dateRange?: {
    startDate: string;
    endDate: string;
  };
  messageTypes?: string[];
  documentTypes?: string[];
  eventCategories?: string[];
  flowStatuses?: string[];
  siteTypes?: string[];
  contentTypes?: string[];
  tags?: string[];
  customFields?: Record<string, any>;
}

// Event Types
export interface Microsoft365Event {
  type: string;
  team?: Microsoft365Team;
  channel?: Microsoft365Channel;
  message?: Microsoft365Message;
  document?: Microsoft365Document;
  event?: Microsoft365Event;
  flow?: Microsoft365Flow;
  site?: Microsoft365Site;
  user?: Microsoft365User;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface Microsoft365WebhookEvent {
  type: string;
  tenantId: string;
  clientState?: string;
  resource: string;
  subscriptionId: string;
  expirationDateTime: string;
  organizationId: string;
  payload?: any;
  changeType: string;
  resourceData?: {
    id: string;
    '@odata.type': string;
    '@odata.id': string;
    '@odata.etag': string;
  };
  encryptedContent?: string;
  signature?: string;
}

// Skill Types
export interface Microsoft365Skill {
  name: string;
  description: string;
  parameters: Record<string, any>;
  result: any;
  executionTime: number;
  timestamp: string;
}

export interface Microsoft365SkillContext {
  config: Microsoft365Config;
  state: Microsoft365IntegrationState;
  user: Microsoft365User;
  team?: Microsoft365Team;
  channel?: Microsoft365Channel;
  document?: Microsoft365Document;
  event?: Microsoft365Event;
}

// Error Types
export interface Microsoft365Error {
  code: string;
  message: string;
  description?: string;
  field?: string;
  help_url?: string;
  suggestions?: string[];
}

export interface Microsoft365APIError extends Microsoft365Error {
  status_code: number;
  response?: any;
  request?: {
    method: string;
    url: string;
    headers: Record<string, string>;
    body?: any;
  };
}

// Constants
export const MICROSOFT365_SERVICE_ENDPOINTS = {
  graph: 'https://graph.microsoft.com',
  teams: 'https://graph.microsoft.com/beta/teams',
  outlook: 'https://outlook.office.com/api',
  onedrive: 'https://graph.microsoft.com/v1.0/drive',
  sharepoint: 'https://{tenant}.sharepoint.com',
  powerAutomate: 'https://make.powerautomate.com',
  powerBI: 'https://api.powerbi.com',
  powerApps: 'https://api.powerapps.com',
  yammer: 'https://www.yammer.com/api/v1'
} as const;

export const MICROSOFT365_OAUTH_SCOPES = {
  teams: [
    'Team.ReadBasic.All',
    'TeamSettings.Read.All',
    'TeamSettings.ReadWrite.All',
    'Team.Create',
    'Team.Delete',
    'TeamMember.Read.All',
    'TeamMember.ReadWrite.All',
    'Channel.ReadBasic.All',
    'Channel.Read.All',
    'Channel.Create',
    'Channel.Delete',
    'ChannelMessage.Read.All',
    'ChannelMessage.Send',
    'Chat.ReadWrite',
    'Chat.Create',
    'User.Read.All',
    'Presence.Read.All',
    'OnlineMeetings.Read.All',
    'OnlineMeetings.ReadWrite'
  ],
  outlook: [
    'Mail.Read',
    'Mail.ReadWrite',
    'Mail.Send',
    'Calendars.Read',
    'Calendars.ReadWrite',
    'Contacts.Read',
    'Contacts.ReadWrite',
    'User.Read.All'
  ],
  onedrive: [
    'Files.Read.All',
    'Files.ReadWrite.All',
    'Sites.Read.All',
    'Sites.ReadWrite.All',
    'Sites.Manage.All',
    'Sites.FullControl.All'
  ],
  sharepoint: [
    'Sites.Read.All',
    'Sites.ReadWrite.All',
    'Sites.Manage.All',
    'Sites.FullControl.All'
  ],
  powerAutomate: [
    'Flow.Read.All',
    'Flow.ReadWrite.All',
    'Flow.Create',
    'Flow.Delete',
    'Flow.Manage.All'
  ],
  powerBI: [
    'Dashboard.Read.All',
    'Report.Read.All',
    'Dataset.Read.All',
    'Workspace.Read.All',
    'Workspace.Create'
  ],
  powerApps: [
    'App.Read.All',
    'App.ReadWrite.All',
    'App.Create',
    'App.Delete',
    'Environment.Read.All',
    'Environment.Create'
  ]
} as const;

export const MICROSOFT365_API_VERSIONS = {
  v1: 'v1.0',
  v2: 'v2.0',
  beta: 'beta'
} as const;

export const MICROSOFT365_PERMISSIONS = {
  user: [
    'User.Read.All',
    'User.ReadWrite.All',
    'User.Export.All',
    'User.Import.All',
    'User.ManageIdentities.All',
    'User.Read.All',
    'User.RevokeSessions.All'
  ],
  group: [
    'Group.Read.All',
    'Group.ReadWrite.All',
    'Group.Create',
    'Group.Delete',
    'GroupMember.Read.All',
    'GroupMember.ReadWrite.All'
  ],
  directory: [
    'Directory.Read.All',
    'Directory.ReadWrite.All',
    'Directory.AccessAsUser.All',
    'Directory.ReadWrite.All',
    'Directory.ReadWrite.All'
  ],
  application: [
    'Application.Read.All',
    'Application.ReadWrite.All',
    'Application.Create',
    'Application.Delete',
    'Application.ReadWrite.All',
    'Application.ReadWrite.All'
  ],
  policy: [
    'Policy.Read.All',
    'Policy.ReadWrite.All',
    'Policy.Create',
    'Policy.Delete'
  ],
  device: [
    'Device.Read.All',
    'Device.ReadWrite.All',
    'Device.Create',
    'Device.Delete',
    'DeviceManagementConfiguration.Read.All',
    'DeviceManagementConfiguration.ReadWrite.All'
  ]
} as const;

export const MICROSOFT365_FEATURES = {
  teams: 'Microsoft Teams',
  outlook: 'Microsoft Outlook',
  onedrive: 'Microsoft OneDrive',
  sharepoint: 'Microsoft SharePoint',
  powerAutomate: 'Microsoft Power Automate',
  powerBI: 'Microsoft Power BI',
  powerApps: 'Microsoft Power Apps',
  yammer: 'Microsoft Yammer',
  planner: 'Microsoft Planner',
  toDo: 'Microsoft To Do',
  forms: 'Microsoft Forms',
  stream: 'Microsoft Stream',
  loop: 'Microsoft Loop',
  whiteboard: 'Microsoft Whiteboard',
  bookings: 'Microsoft Bookings',
  shift: 'Microsoft Shift',
  lists: 'Microsoft Lists',
  project: 'Microsoft Project',
  visio: 'Microsoft Visio'
} as const;

export const MICROSOFT365_RATE_LIMITS = {
  graph: {
    requestsPerMinute: 12000,
    requestsPerHour: 720000,
    requestsPerDay: 17280000,
    concurrentRequests: 20,
    largePayloadRequests: 500
  },
  teams: {
    requestsPerMinute: 5000,
    requestsPerHour: 300000,
    requestsPerDay: 7200000,
    concurrentConnections: 100,
    messageSizeLimit: 28000
  },
  powerAutomate: {
    requestsPerMinute: 1000,
    requestsPerHour: 60000,
    requestsPerDay: 1440000,
    flowRunsPerMinute: 1000,
    flowRunsPerHour: 60000
  },
  powerBI: {
    requestsPerMinute: 200,
    requestsPerHour: 12000,
    requestsPerDay: 288000,
    concurrentRequests: 10,
    datasetRefreshes: 48
  },
  onedrive: {
    requestsPerMinute: 6000,
    requestsPerHour: 360000,
    requestsPerDay: 8640000,
    uploadSizeLimit: 250 * 1024 * 1024 * 1024, // 250GB
    downloadSizeLimit: 250 * 1024 * 1024 * 1024
  }
} as const;