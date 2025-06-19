// Main types for Atom agent

export interface AtomMessage {
  id: string;
  text: string;
  // Potentially add a timestamp, sender, etc.
}

// --- Generic OAuth2 Token Type ---
// This type is compatible with googleapis and can be used for other OAuth2 providers.
export interface OAuth2Token {
  access_token: string;
  refresh_token?: string | null; // Refresh tokens are not always present
  scope?: string;
  token_type?: string; // e.g., "Bearer"
  expiry_date?: number | null; // Timestamp (milliseconds since epoch) when the access token expires
  id_token?: string | null; // Present in OpenID Connect flows
  // Allow any other properties that might come from the provider
  [key: string]: any;
}

// --- Generic Skill Error and Response Types ---
export interface SkillError {
  code: string; // e.g., 'AUTH_TOKEN_INVALID', 'API_ERROR', 'VALIDATION_ERROR', 'NOT_FOUND', 'CONFIG_ERROR'
  message: string;
  details?: any; // Additional details, like the original error object or validation specifics
}

// Generic response structure for Calendar skills.
export interface CalendarSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for HubSpot skills.
export interface HubSpotSkillResponse<T> {
  ok: boolean;
  data?: T; // Data will be null if ok:true but contact not found for getHubSpotContactByEmail
  error?: SkillError;
}

// Generic response structure for Slack skills.
export interface SlackSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for Zoom skills.
export interface ZoomSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for Microsoft Graph skills.
export interface GraphSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for Stripe skills.
export interface StripeSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for QuickBooks Online skills.
export interface QBSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// Generic response structure for Web Research skills.
export interface WebResearchSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// --- Python Service API Call Types ---

/**
 * Represents the structure of an error payload from the Python Flask services.
 */
export interface PythonErrorPayload {
  code: string; // e.g., "PYTHON_ERROR_CONFIG_ERROR", "PYTHON_ERROR_NOTION_API_ERROR"
  message: string;
  details?: any;
}

/**
 * Generic type for responses from the Python Flask services.
 * These services should return a JSON object with an "ok" boolean field,
 * and either "data" on success or "error" on failure.
 */
export interface PythonApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: PythonErrorPayload;
}

// Specific data types for Python API responses (matching Python's return dicts)

// For initiateResearch (data field of PythonApiResponse)
export interface InitiateResearchData {
  project_page_id: string;
  task_page_ids: string[];
}

// For processResearchQueue (data field of PythonApiResponse)
export interface ProcessResearchQueueData {
  message: string;
  processed_tasks: number;
  failed_tasks: number;
  synthesis_outcome?: any;
}

// For createNotionNote and createAudioNoteFromUrl (data field of PythonApiResponse)
export interface CreateNoteData {
  page_id: string;
  url?: string;
  summary?: string;
  key_points?: string;
}

// For searchNotionNotes (data field of PythonApiResponse)
export interface NotionSearchResultData { // This is an item in the array returned by searchNotionNotes
  id: string;
  title?: string; // Title property from Notion
  url?: string;
  content?: string; // Main content snippet or ContentText property
  // other properties from Notion page summary (e.g., Source, Linked Task ID)
  [key: string]: any;
}


// --- Calendar Types ---
export interface CalendarEvent {
  id: string;
  summary: string;
  description?: string;
  startTime: string; // ISO 8601 date-time string
  endTime: string;   // ISO 8601 date-time string
  location?: string;
  htmlLink?: string; // Link to the event in Google Calendar
  conferenceData?: ConferenceData; // Added for Google Meet details
  // Potential future additions: attendees, recurrence rules etc.
}

// --- Google Meet / Calendar Conference Types ---
export interface ConferenceSolution {
  key?: { type?: string; [key: string]: any; }; // e.g., { type: "hangoutsMeet" }
  name?: string; // e.g., "Google Meet"
  iconUri?: string;
  [key: string]: any;
}

export interface ConferenceEntryPoint {
  entryPointType?: 'video' | 'phone' | 'sip' | 'more';
  uri?: string; // e.g., "https://meet.google.com/abc-def-ghi" or "tel:+1234567890,,,12345#"
  label?: string;
  pin?: string; // PIN for phone entry point
  accessCode?: string;
  meetingCode?: string; // e.g., "abc-def-ghi"
  passcode?: string;
  password?: string;
  [key: string]: any;
}

export interface ConferenceData {
  createRequest?: {
    requestId?: string;
    conferenceSolutionKey?: { type?: string; };
    status?: { statusCode?: 'success' | 'failure' | 'pending'; };
    [key: string]: any;
  };
  entryPoints?: ConferenceEntryPoint[];
  conferenceSolution?: ConferenceSolution;
  conferenceId?: string; // e.g., "abc-def-ghi"
  signature?: string;
  notes?: string;
  [key: string]: any;
}

export interface CreateEventResponse {
  success: boolean;
  eventId?: string;
  message: string;
  htmlLink?: string;
}

export interface SkillResponse {
  success: boolean;
  message: string;
  data?: any;
}

// --- Email Types ---
export interface Email {
  id: string;
  sender: string;
  recipient: string;
  subject: string;
  body: string;
  timestamp: string;
  read: boolean;
}

export interface SendEmailResponse {
  success: boolean;
  emailId?: string;
  message: string;
}

export interface ReadEmailResponse {
  success: boolean;
  email?: Email;
  message?: string;
}

// --- Web Research Types ---
export interface SearchResult {
  title: string;
  link: string;
  snippet: string;
}

// --- Zapier Types ---
export interface ZapTriggerResponse {
  success: boolean;
  zapName?: string;
  runId?: string;
  message: string;
}

// --- HubSpot Types ---
export interface HubSpotContactProperties {
  email: string;
  firstname?: string;
  lastname?: string;
  company?: string;
}

export interface HubSpotContact {
  id: string;
  properties: {
    hs_object_id: string;
    createdate: string;
    lastmodifieddate: string;
    email?: string;
    firstname?: string;
    lastname?: string;
    company?: string;
    [key: string]: any;
  };
  createdAt: string;
  updatedAt: string;
  archived: boolean;
}

export interface CreateHubSpotContactResponse {
  success: boolean;
  contactId?: string;
  message?: string;
  hubSpotContact?: HubSpotContact;
}

export interface HubSpotEmailEngagementProperties {
  activityTimestamp: number;
  subject: string;
  htmlBody: string;
  direction?: 'INCOMING' | 'OUTGOING';
}

export interface HubSpotEngagementAssociation {
  to: { id: string };
  types: { associationCategory: string; associationTypeId: number }[];
}

export interface HubSpotEngagement {
  id: string;
  properties: {
    hs_object_id: string;
    hs_engagement_type: 'EMAIL' | 'MEETING' | 'CALL' | 'NOTE' | 'TASK';
    hs_timestamp?: string;
    hs_body_preview?: string;
    hs_email_subject?: string;
    hs_email_direction?: 'INCOMING' | 'OUTGOING';
    createdate?: string;
    lastmodifieddate?: string;
    [key: string]: any;
  };
  associations?: {
    contacts?: { results: { id: string, type: string }[] };
    companies?: { results: { id: string, type: string }[] };
  };
  createdAt: string;
  updatedAt: string;
  archived: boolean;
}

export interface LogEngagementResponse {
  success: boolean;
  engagementId?: string;
  message: string;
  hubSpotEngagement?: HubSpotEngagement;
}

export interface GetContactActivitiesResponse {
  success: boolean;
  activities: HubSpotEngagement[];
  message?: string;
  nextPage?: string;
}

// --- Slack Types ---
export interface SlackChannel {
  id: string;
  name?: string;
  is_channel?: boolean;
  is_group?: boolean;
  is_im?: boolean;
  is_mpim?: boolean;
  is_private?: boolean;
  is_archived?: boolean;
  is_general?: boolean;
  num_members?: number;
  topic?: { value: string; creator: string; last_set: number; };
  purpose?: { value: string; creator: string; last_set: number; };
  created?: number;
  creator?: string;
}

export interface SlackMessageData {
  ts?: string;
  channel?: string;
  message?: {
    text?: string;
    user?: string;
    bot_id?: string;
    ts?: string;
    type?: string;
    subtype?: string;
    [key: string]: any;
  };
}

export interface ListSlackChannelsData {
  channels?: SlackChannel[];
  nextPageCursor?: string;
}

// --- Calendly Types ---
export interface CalendlyUser {
  uri: string;
  name: string;
  slug: string;
  email: string;
  scheduling_url: string;
  timezone: string;
  avatar_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendlyEventType {
  uri: string;
  name: string;
  active: boolean;
  slug: string;
  scheduling_url: string;
  duration: number;
  kind: 'solo' | 'group';
  pooling_type?: 'round_robin' | 'collective' | null;
  type: string;
  color: string;
  created_at: string;
  updated_at: string;
}

export interface CalendlyScheduledEventLocation {
  type: 'physical' | 'inbound_call' | 'outbound_call' | 'custom' | 'google_conference' | 'gotomeeting_conference' | 'microsoft_teams_conference' | 'zoom_conference' | string;
  location?: string | null;
}

export interface CalendlyInvitee {
  uri: string;
  email: string;
  name: string;
  first_name?: string | null;
  last_name?: string | null;
  status: 'active' | 'canceled';
  questions_and_answers: { question: string; answer: string; position: number }[];
  timezone: string;
  event_uri: string;
  cancel_url: string;
  reschedule_url: string;
  created_at: string;
  updated_at: string;
}

export interface CalendlyScheduledEvent {
  uri: string;
  name: string;
  status: 'active' | 'canceled';
  start_time: string;
  end_time: string;
  event_type: string;
  location: CalendlyScheduledEventLocation;
  created_at: string;
  updated_at: string;
}

export interface CalendlyPagination {
  count: number;
  next_page?: string | null;
  previous_page?: string | null;
  next_page_token?: string | null;
  previous_page_token?: string | null;
}

// --- NLU Service Types ---
export interface NLUResponseData {
  intent: string | null;
  entities: Record<string, any>;
  confidence?: number;
  recognized_phrase?: string;
  clarification_question?: string;
  partially_understood_intent?: string;
  sub_tasks?: Array<{intent: string; entities: Record<string, any>; summary_for_sub_task?: string;}>;
  original_query?: string;
}

export interface ProcessedNLUResponse extends NLUResponseData {
  originalMessage: string;
  error?: string;
  requires_clarification?: boolean;
  clarification_question?: string;
  conversation_context?: any;
  sub_tasks?: Array<{intent: string | null; entities: Record<string, any>; summary_for_sub_task?: string;}>;
}

// --- QuickBooks Online (QBO) Types ---
export interface QuickBooksAuthTokens {
  accessToken: string;
  refreshToken: string;
  realmId: string;
  accessTokenExpiresAt: number;
  refreshTokenExpiresAt: number;
  createdAt: number;
}

export interface ListQBInvoicesData {
  invoices: QuickBooksInvoice[];
  queryResponse?: any;
}

export interface QuickBooksInvoice {
  Id: string;
  DocNumber?: string;
  TxnDate?: string;
  DueDate?: string;
  CustomerRef?: { value: string; name?: string; };
  BillEmail?: { Address: string; };
  TotalAmt?: number;
  Balance?: number;
  CurrencyRef?: { value: string; name?: string; };
  Line?: any[];
  PrivateNote?: string;
  CustomerMemo?: string;
  EmailStatus?: 'EmailSent' | 'NotSet' | string;
  [key: string]: any;
}

// --- Stripe Types ---
export interface ListStripePaymentsData {
  payments: StripePaymentIntent[];
  has_more: boolean;
}

export interface StripeCharge {
  id: string;
  amount: number;
  currency: string;
  status: 'succeeded' | 'pending' | 'failed';
  created: number;
  receipt_url?: string | null;
  description?: string | null;
}

export interface StripePaymentIntent {
  id: string;
  amount: number;
  currency: string;
  status: 'succeeded' | 'requires_payment_method' | 'requires_confirmation' | 'requires_action' | 'processing' | 'canceled';
  created: number;
  customer?: string | null;
  description?: string | null;
  latest_charge?: StripeCharge | null;
}

// --- Microsoft Graph / Teams Types ---
export interface ListMSGraphEventsData {
  events: MSGraphEvent[];
  nextLink?: string;
}

export interface MSGraphDateTimeTimeZone {
  dateTime: string;
  timeZone: string;
}

export interface MSGraphOnlineMeetingInfo {
  joinUrl?: string | null;
  conferenceId?: string | null;
  tollNumber?: string | null;
  [key: string]: any;
}

export interface MSGraphEvent {
  id: string;
  subject?: string | null;
  bodyPreview?: string | null;
  body?: { contentType?: 'html' | 'text'; content?: string | null; } | null;
  start?: MSGraphDateTimeTimeZone | null;
  end?: MSGraphDateTimeTimeZone | null;
  isOnlineMeeting?: boolean | null;
  onlineMeetingProvider?: 'teamsForBusiness' | 'skypeForBusiness' | 'skypeForConsumer' | string | null;
  onlineMeeting?: MSGraphOnlineMeetingInfo | null;
  webLink?: string | null;
  attendees?: { emailAddress?: { address?: string | null; name?: string | null; }; type?: 'required' | 'optional' | 'resource'; status?: { response?: string; time?: string; }; }[];
  location?: { displayName?: string | null; locationType?: 'default' | 'conferenceRoom' | 'homeAddress' | 'businessAddress' | string; uniqueId?: string | null; address?: any; coordinates?: any; } | null;
  locations?: any[];
  organizer?: { emailAddress?: { name?: string | null; address?: string | null; }; } | null;
  [key: string]: any;
}

export interface MSGraphTokenResponse {
  token_type: string;
  expires_in: number;
  ext_expires_in?: number;
  access_token: string;
}

// --- Zoom Types ---
export interface ZoomTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  scope: string;
}

export interface ListZoomMeetingsData {
  meetings: ZoomMeeting[];
  page_count?: number;
  page_number?: number;
  page_size?: number;
  total_records?: number;
  next_page_token?: string;
}

export interface ZoomMeeting {
  uuid: string;
  id: string;
  host_id?: string;
  topic: string;
  type: number;
  start_time?: string;
  duration?: number;
  timezone?: string;
  agenda?: string;
  created_at: string;
  join_url: string;
  [key: string]: any;
}

[end of atomic-docker/project/functions/atom-agent/types.ts]
