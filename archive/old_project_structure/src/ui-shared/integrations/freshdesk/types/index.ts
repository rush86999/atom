/**
 * Freshdesk Integration Types
 * Type definitions for Freshdesk API and integration components
 */

// Core Freshdesk Types
export interface FreshdeskTicket {
  id: number;
  subject: string;
  description: string;
  description_text: string;
  status: number;
  priority: number;
  source: number;
  requester_id: number;
  responder_id?: number;
  group_id?: number;
  company_id?: number;
  type?: string;
  product_id?: number;
  category?: string;
  sub_category?: string;
  item?: string;
  due_by?: string;
  fr_due_by?: string;
  is_escalated: boolean;
  spam: boolean;
  email_config_id?: number;
  custom_fields?: Record<string, any>;
  created_at: string;
  updated_at: string;
  tags?: string[];
  attachments?: FreshdeskAttachment[];
  cc_emails?: string[];
  to_emails?: string[];
  fwd_emails?: string[];
  reply_cc_emails?: string[];
  ticket_cc_emails?: string[];
  nr_due_by?: string;
  fr_escalated?: boolean;
  is_trashed?: boolean;
  urgent?: boolean;
}

export interface FreshdeskContact {
  id: number;
  name: string;
  email: string;
  phone?: string;
  mobile?: string;
  address?: string;
  twitter_id?: string;
  facebook_id?: string;
  linkedin_id?: string;
  company_id?: number;
  avatar?: {
    url: string;
    'content-type': string;
    name: string;
  };
  custom_fields?: Record<string, any>;
  tags?: string[];
  language?: string;
  time_zone?: string;
  created_at: string;
  updated_at: string;
  active?: boolean;
  job_title?: string;
  description?: string;
  unique_external_id?: string;
  view_all_tickets?: boolean;
  other_companies?: Array<{
    id: number;
    name: string;
  }>;
}

export interface FreshdeskCompany {
  id: number;
  name: string;
  description?: string;
  note?: string;
  domains?: string[];
  health_score?: string;
  account_tier?: string;
  industry?: string;
  renewal_date?: string;
  custom_fields?: Record<string, any>;
  tags?: string[];
  created_at: string;
  updated_at: string;
  active?: boolean;
  sla_policy_id?: number;
  freshtwo?: boolean;
}

export interface FreshdeskAgent {
  id: number;
  name: string;
  email: string;
  phone?: string;
  mobile?: string;
  active: boolean;
  available: boolean;
  occasional: boolean;
  signature?: string;
  last_seen_at?: string;
  roles?: Array<{
    id: number;
    name: string;
  }>;
  groups?: Array<{
    id: number;
    name: string;
  }>;
  contact?: FreshdeskContact;
  skill_names?: string[];
  background_info?: string;
  time_zone?: string;
  created_at: string;
  updated_at: string;
  auto_ticket_assign?: boolean;
  type?: string;
  department_ids?: number[];
}

export interface FreshdeskGroup {
  id: number;
  name: string;
  description?: string;
  escalate_to?: number;
  unassigned_for?: number;
  agent_ids?: number[];
  business_hour_id?: number;
  auto_ticket_assign?: boolean;
  round_robin_enabled?: boolean;
  created_at: string;
  updated_at: string;
  type?: string;
  restrict_tickets?: boolean;
  include_members?: boolean;
}

export interface FreshdeskConversation {
  id: number;
  body: string;
  body_text?: string;
  private?: boolean;
  user_id?: number;
  support_email?: string;
  source?: number;
  incoming?: boolean;
  ticket_id: number;
  attachments?: FreshdeskAttachment[];
  to_emails?: string[];
  from_email?: string;
  cc_emails?: string[];
  bcc_emails?: string[];
  created_at: string;
  updated_at: string;
  user?: FreshdeskAgent;
}

export interface FreshdeskAttachment {
  id: number;
  name: string;
  content_type: string;
  size: number;
  attachment_url?: string;
  created_at: string;
  updated_at: string;
}

export interface FreshdeskSatisfactionRating {
  id: number;
  ticket_id: number;
  rating: number;
  feedback?: string;
  created_at: string;
  updated_at: string;
}

export interface FreshdeskSLAPolicy {
  id: number;
  name: string;
  description?: string;
  is_default: boolean;
  applicable_to?: string;
  sla_details: Array<{
    responder_id?: number;
    group_id?: number;
    product_id?: number;
    bhrs_id?: number;
    sla_target: {
      response_in_hrs: number;
      resolution_in_hrs: number;
    };
  }>;
  created_at: string;
  updated_at: string;
}

// API Request/Response Types
export interface FreshdeskAPIResponse<T> {
  data: T;
  success: boolean;
  errors?: string[];
  message?: string;
}

export interface FreshdeskPaginatedResponse<T> {
  results: T[];
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface FreshdeskSearchResult {
  results: Array<{
    id: number;
    title: string;
    description?: string;
    type: string;
    url: string;
    created_at: string;
    updated_at: string;
  }>;
  total: number;
  query: string;
}

// Configuration Types
export interface FreshdeskConfig {
  domain: string;
  apiKey?: string;
  accessToken?: string;
  apiVersion?: string;
  webhookSecret?: string;
  rateLimit?: {
    requestsPerMinute: number;
    requestsPerHour: number;
    requestsPerDay: number;
  };
  features?: {
    ticketManagement: boolean;
    contactManagement: boolean;
    companyManagement: boolean;
    agentManagement: boolean;
    groupManagement: boolean;
    satisfactionTracking: boolean;
    slaManagement: boolean;
    knowledgeBase: boolean;
    forums: boolean;
    analytics: boolean;
    automation: boolean;
    customFields: boolean;
    timeTracking: boolean;
    phoneSupport: boolean;
    chatSupport: boolean;
    socialSupport: boolean;
  };
  preferences?: {
    defaultPriority: number;
    defaultStatus: number;
    autoAssign: boolean;
    escalateUnassigned: boolean;
    notifyOnUpdate: boolean;
    includeSignature: boolean;
    enableSpellCheck: boolean;
    timeFormat: string;
    dateFormat: string;
    timezone: string;
    language: string;
  };
  security?: {
    enforceStrongPasswords: boolean;
    requireTwoFactor: boolean;
    ipWhitelist: string[];
    encryptAttachments: boolean;
    auditLogging: boolean;
    dataRetentionDays: number;
    gdprCompliant: boolean;
    roleBasedAccess: boolean;
  };
  integrations?: {
    email: {
      enabled: boolean;
      providers: string[];
      customEmail: boolean;
      emailRouting: boolean;
      emailTemplates: boolean;
      cannedResponses: boolean;
    };
    phone: {
      enabled: boolean;
      provider: string;
      callRecording: boolean;
      voicemail: boolean;
      ivr: boolean;
      callRouting: boolean;
    };
    chat: {
      enabled: boolean;
      provider: string;
      chatHistory: boolean;
      fileSharing: boolean;
      screenSharing: boolean;
      coBrowsing: boolean;
    };
    social: {
      enabled: boolean;
      platforms: string[];
      directMessages: boolean;
      publicPosts: boolean;
      mentions: boolean;
      hashtags: boolean;
    };
    crm: {
      enabled: boolean;
      provider: string;
      syncContacts: boolean;
      syncCompanies: boolean;
      syncTickets: boolean;
      syncDeals: boolean;
    };
  };
}

// UI State Types
export interface FreshdeskIntegrationState {
  isAuthenticated: boolean;
  config: FreshdeskConfig | null;
  user: FreshdeskAgent | null;
  tickets: FreshdeskTicket[];
  contacts: FreshdeskContact[];
  companies: FreshdeskCompany[];
  agents: FreshdeskAgent[];
  groups: FreshdeskGroup[];
  conversations: FreshdeskConversation[];
  satisfactionRatings: FreshdeskSatisfactionRating[];
  slaPolicies: FreshdeskSLAPolicy[];
  loading: boolean;
  error: string | null;
  selectedTicket?: FreshdeskTicket;
  selectedContact?: FreshdeskContact;
  selectedCompany?: FreshdeskCompany;
  searchQuery?: string;
  filters: FreshdeskFilters;
  pagination: {
    tickets: { page: number; hasMore: boolean; total: number };
    contacts: { page: number; hasMore: boolean; total: number };
    companies: { page: number; hasMore: boolean; total: number };
  };
  statistics: FreshdeskStatistics;
}

export interface FreshdeskFilters {
  status?: number[];
  priority?: number[];
  source?: number[];
  group?: number[];
  agent?: number[];
  company?: number[];
  dateRange?: {
    startDate: string;
    endDate: string;
  };
  tags?: string[];
  category?: string;
  subCategory?: string;
  item?: string;
  type?: string;
}

export interface FreshdeskStatistics {
  totalTickets: number;
  openTickets: number;
  pendingTickets: number;
  resolvedTickets: number;
  closedTickets: number;
  overdueTickets: number;
  dueToday: number;
  satisfactionRating: number;
  averageResponseTime: number;
  averageResolutionTime: number;
  ticketsByPriority: Record<string, number>;
  ticketsByStatus: Record<string, number>;
  ticketsByAgent: Record<string, number>;
  ticketsByGroup: Record<string, number>;
  ticketsBySource: Record<string, number>;
  topContacts: Array<{ name: string; email: string; ticketCount: number }>;
  topCompanies: Array<{ name: string; ticketCount: number }>;
  agentPerformance: Array<{
    agent: string;
    ticketsHandled: number;
    averageResponseTime: number;
    averageResolutionTime: number;
    satisfactionRating: number;
  }>;
}

// Event Types
export interface FreshdeskEvent {
  type: string;
  ticket?: FreshdeskTicket;
  contact?: FreshdeskContact;
  company?: FreshdeskCompany;
  agent?: FreshdeskAgent;
  group?: FreshdeskGroup;
  conversation?: FreshdeskConversation;
  rating?: FreshdeskSatisfactionRating;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface FreshdeskWebhookEvent {
  event_type: string;
  domain: string;
  payload: {
    ticket?: FreshdeskTicket;
    user?: FreshdeskAgent;
    group?: FreshdeskGroup;
    conversation?: FreshdeskConversation;
    contact?: FreshdeskContact;
    company?: FreshdeskCompany;
  };
  timestamp: string;
  signature?: string;
}

// Skill Types
export interface FreshdeskSkill {
  name: string;
  description: string;
  parameters: Record<string, any>;
  result: any;
  executionTime: number;
  timestamp: string;
}

export interface FreshdeskSkillContext {
  config: FreshdeskConfig;
  state: FreshdeskIntegrationState;
  user: FreshdeskAgent;
  ticket?: FreshdeskTicket;
  contact?: FreshdeskContact;
  company?: FreshdeskCompany;
}

// Error Types
export interface FreshdeskError {
  code: string;
  message: string;
  description?: string;
  field?: string;
  help_url?: string;
  suggestions?: string[];
}

export interface FreshdeskAPIError extends FreshdeskError {
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
export const FRESHDESK_TICKET_STATUS = {
  OPEN: 2,
  PENDING: 3,
  RESOLVED: 4,
  CLOSED: 5
} as const;

export const FRESHDESK_TICKET_PRIORITY = {
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  URGENT: 4
} as const;

export const FRESHDESK_TICKET_SOURCE = {
  EMAIL: 1,
  PORTAL: 2,
  PHONE: 3,
  FORUM: 4,
  TWITTER: 5,
  FACEBOOK: 6,
  CHAT: 7,
  MOBIHELP: 8,
  FeedbackWidget: 9,
  OutboundEmail: 10,
  ECOMMERCE: 11,
  BGGAME: 12,
  SMS: 13,
  API: 7
} as const;

export const FRESHDESK_AGENT_TYPE = {
  ALL: 'all',
  AGENT: 'agent',
  SUPERVISOR: 'supervisor',
  ADMIN: 'admin'
} as const;

export const FRESHDESK_GROUP_TYPE = {
  TEAM: 'team',
  TASK_BASED: 'task_based'
} as const;

export const FRESHDESK_SATISFACTION_RATING = {
  VERY_POOR: 1,
  POOR: 2,
  NEUTRAL: 3,
  GOOD: 4,
  VERY_GOOD: 5
} as const;