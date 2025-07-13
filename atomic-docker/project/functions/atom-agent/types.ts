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

// For searchSimilarNotionNotes skill (based on Python's NoteSearchResult)
export interface NotionSimilarNoteResult {
  note_id: string;
  score: number; // Similarity score (distance)
  updated_at?: string; // ISO date string
  user_id?: string;
  // Potentially add title or snippet if fetched by Python service in future
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

export interface SkillResponse<T = any> { // Default T to any if not specified
  ok: boolean;
  data?: T;
  error?: SkillError;
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

export interface SlackMessageResponse { // Added this type
  ok: boolean;
  ts?: string;
  channel?: string;
  error?: string; // Matches WebClient's possible error response structure
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
  originalMessage: string; // Changed from originalMessage?: string to ensure it's always present
  error?: string;
  requires_clarification?: boolean;
  clarification_question?: string;
  conversation_context?: any; // Consider making this more specific if possible
  sub_tasks?: Array<{intent: string | null; entities: Record<string, any>; summary_for_sub_task?: string;}>;
}

// --- QuickBooks Online (QBO) Types ---
export interface QuickBooksAuthTokens {
  accessToken: string;
  refreshToken: string;
  realmId: string;
  accessTokenExpiresAt: number; // Milliseconds since epoch
  refreshTokenExpiresAt: number; // Milliseconds since epoch
  tokenCreatedAt: number; // Milliseconds since epoch when these tokens (or the original ones they were refreshed from) were created
}


export interface ListQBInvoicesData {
  invoices: QuickBooksInvoice[];
  queryResponse?: any; // Raw response from QB for pagination etc.
}

export interface QuickBooksInvoice {
  Id: string;
  DocNumber?: string;
  TxnDate?: string; // YYYY-MM-DD
  DueDate?: string;  // YYYY-MM-DD
  CustomerRef?: { value: string; name?: string; };
  BillEmail?: { Address: string; };
  TotalAmt?: number;
  Balance?: number;
  CurrencyRef?: { value: string; name?: string; }; // e.g., { value: "USD", name: "United States Dollar" }
  Line?: any[]; // Can be complex, define further if needed
  PrivateNote?: string;
  CustomerMemo?: string;
  EmailStatus?: 'EmailSent' | 'NotSet' | string; // Other statuses like 'Pending', 'Void' might exist
  [key: string]: any; // Allow other properties
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
  created: number; // Unix timestamp
  receipt_url?: string | null;
  description?: string | null;
}

export interface StripePaymentIntent {
  id: string;
  amount: number;
  currency: string;
  status: 'succeeded' | 'requires_payment_method' | 'requires_confirmation' | 'requires_action' | 'processing' | 'canceled';
  created: number; // Unix timestamp
  customer?: string | null; // Customer ID
  description?: string | null;
  latest_charge?: StripeCharge | string | null; // Can be an ID or an expanded object
}

// --- Slack Message Type for Agent ---
export interface SlackMessageFile {
  id: string;
  created: number;
  timestamp: number;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  pretty_type: string;
  user?: string; // User ID of uploader
  editable?: boolean; // Optional as not all file objects might have it
  size: number;
  mode?: string; // Optional
  is_external?: boolean; // Optional
  external_type?: string; // Optional
  is_public?: boolean; // Optional
  public_url_shared?: boolean; // Optional
  display_as_bot?: boolean; // Optional
  username?: string; // Optional
  url_private?: string;
  url_private_download?: string;
  permalink?: string;
  permalink_public?: string;
  // Potentially more fields like 'thumb_64', 'thumb_80', etc. for images
}

export interface SlackMessageReaction {
  name: string; // Emoji name, e.g., "thumbsup"
  users: string[]; // Array of user IDs who reacted
  count: number;
}

export interface SlackMessage {
  id: string; // Slack message 'ts' (timestamp) is used as the primary ID
  threadId?: string; // 'thread_ts' if part of a thread
  userId?: string; // User ID of the sender (e.g., "U012ABCDEF")
  userName?: string; // User's display name or real name (needs resolution or comes from API)
  botId?: string; // Bot ID if message is from a bot
  channelId?: string; // Channel ID (e.g., "C012AB3CD")
  channelName?: string; // Channel name (e.g., "general") (needs resolution or comes from API)
  text?: string; // Message text content
  blocks?: any[]; // Slack Block Kit structure, if present
  files?: SlackMessageFile[]; // Array of attached files
  reactions?: SlackMessageReaction[]; // Array of reactions
  timestamp: string; // ISO 8601 string representation of the 'ts'
  permalink?: string; // Permalink to the message
  raw?: any; // Store the original raw Slack message object for extensibility
}

// --- Microsoft Graph / Teams Types ---
export interface ListMSTeamsMeetingsData { // Renamed from ListMSGraphEventsData for clarity
  events: MSGraphEvent[];
  nextLink?: string;
}

export interface MSGraphDateTimeTimeZone {
  dateTime: string; // ISO 8601 format
  timeZone: string; // e.g., "Pacific Standard Time"
}

export interface MSGraphOnlineMeetingInfo {
  joinUrl?: string | null;
  conferenceId?: string | null;
  tollNumber?: string | null;
  [key: string]: any; // Allow other properties
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
  [key: string]: any; // Allow other properties
}

export interface MSGraphTokenResponse {
  token_type: string;
  expires_in: number; // Seconds
  ext_expires_in?: number; // Seconds
  access_token: string;
}

// --- Microsoft Teams Message Types for Agent ---
export interface MSTeamsMessageAttachment {
  id: string;
  name?: string | null;
  contentType?: string | null;
  contentUrl?: string | null; // Direct link to the content if available
  size?: number | null;
  // Add other relevant fields from Graph API's attachment resource type if needed
}

export interface MSTeamsMessageMentionedUser {
  id?: string | null; // User's AAD ID if available from mention object
  displayName?: string | null;
  userIdentityType?: string | null; // e.g., "aadUser"
}
export interface MSTeamsMessageMention {
  id: number; // The ID of the mention in the message.
  mentionText?: string | null; // The display text of the mention.
  mentioned?: { // Details of the entity mentioned.
    user?: MSTeamsMessageMentionedUser | null;
    application?: any | null; // if an app is mentioned
    conversation?: any | null; // if a channel/chat is mentioned
    tag?: any | null; // if a tag is mentioned
  } | null;
}

export interface MSTeamsMessage {
  id: string; // Message ID from Graph API
  chatId?: string | null; // ID of the 1:1 or group chat (if applicable)
  teamId?: string | null; // ID of the Team (if a channel message)
  channelId?: string | null; // ID of the Channel (if a channel message)
  replyToId?: string | null; // ID of the parent message if this is a reply
  userId?: string | null; // Sender's AAD User ID
  userName?: string | null; // Sender's display name
  content: string; // Message body content (HTML or text)
  contentType: 'html' | 'text';
  createdDateTime: string; // ISO 8601 timestamp
  lastModifiedDateTime?: string | null; // ISO 8601 timestamp
  webUrl?: string | null; // Permalink to the message
  attachments?: MSTeamsMessageAttachment[] | null;
  mentions?: MSTeamsMessageMention[] | null;
  raw?: any; // Store the original raw Graph API message object for extensibility
}


// --- Zoom Types ---
export interface ZoomTokenResponse {
  access_token: string;
  token_type: string; // Typically "bearer"
  expires_in: number; // Typically 3600 seconds (1 hour)
  scope: string; // e.g., "meeting:read meeting:write user:read"
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
  id: string; // Numeric meeting ID
  host_id?: string;
  topic: string;
  type: number; // 1: Instant, 2: Scheduled, 3: Recurring no fixed time, 8: Recurring fixed time
  start_time?: string; // ISO 8601 date-time string
  duration?: number; // In minutes
  timezone?: string;
  agenda?: string;
  created_at: string; // ISO 8601 date-time string
  join_url: string;
  [key: string]: any; // Allow other properties
}

// --- Notion Task Management Types ---

export type NotionTaskStatus = "To Do" | "In Progress" | "Done" | "Blocked" | "Cancelled";

export type NotionTaskPriority = "High" | "Medium" | "Low";

export interface NotionTask {
  id: string; // Notion Page ID
  description: string;
  dueDate?: string | null; // ISO date string or null
  status: NotionTaskStatus;
  priority?: NotionTaskPriority | null;
  listName?: string | null; // Corresponds to a custom "List" or "Project" property in Notion
  createdDate: string; // ISO date string (from Notion's created_time)
  url: string; // Notion page URL
  notes?: string | null; // Additional text content or a summary from the page body
  last_edited_time?: string; // ISO 8601 string, from Notion's last_edited_time
}

export interface CreateNotionTaskParams {
  description: string;
  dueDate?: string | null;
  status?: NotionTaskStatus;
  priority?: NotionTaskPriority | null;
  listName?: string | null;
  notes?: string | null;
  notionTasksDbId: string; // ID of the Notion database for tasks
}

export interface NotionTaskResponse { // Kept for potential direct Notion API calls, but Python responses are preferred
  success: boolean;
  message: string;
  taskId?: string;
  taskUrl?: string;
  error?: string;
}

export interface QueryNotionTasksParams {
  status?: NotionTaskStatus | NotionTaskStatus[]; // Allow single or multiple statuses
  dueDateBefore?: string | null; // ISO Date string
  dueDateAfter?: string | null;  // ISO Date string
  dateQuery?: string | null;     // For NLU like "today", "next week" to be parsed by backend
  priority?: NotionTaskPriority | null;
  listName?: string | null;
  descriptionContains?: string | null;
  notionTasksDbId: string; // ID of the Notion database for tasks
  limit?: number;
}

export interface TaskQueryResponse { // This is returned by the queryNotionTasks skill
  success: boolean;
  tasks: NotionTask[];
  message?: string;
  error?: string; // Error message if success is false
}

export interface UpdateNotionTaskParams {
  taskId: string; // Notion Page ID of the task to update
  description?: string;
  dueDate?: string | null;
  status?: NotionTaskStatus;
  priority?: NotionTaskPriority | null;
  listName?: string | null;
  notes?: string | null;
  // notionTasksDbId: string; // Usually not needed for page update by ID
}

// Specific data types for responses from Python backend for task operations
// These align with the 'data' field within PythonApiResponse<T>

export interface CreateTaskData {
  taskId: string; // Notion Page ID of the created task
  taskUrl: string; // URL to the Notion task page
  message?: string; // Optional success message from backend
}

export interface UpdateTaskData {
  taskId: string; // Notion Page ID of the updated task
  updatedProperties: string[]; // List of properties that were actually changed
  message?: string; // Optional success message from backend
}
// Add EmailActionType if not already defined
export type EmailActionType =
  | "FIND_SPECIFIC_INFO"
  | "GET_SENDER"
  | "GET_SUBJECT"
  | "GET_DATE"
  | "GET_FULL_CONTENT"
  | "SUMMARIZE_EMAIL";

// --- Contact / Attendee Resolution Types ---
export interface ResolvedAttendee {
  email: string; // Mandatory
  name?: string;
  userId?: string; // Atom user ID, if applicable
  source: "atom_user" | "google_contact" | "hubspot_contact" | "email_direct" | "unresolved";
  status?: "found" | "not_found" | "error_resolving";
  errorMessage?: string;
}

export interface ContactSkillResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

// --- User Availability Types (for OptaPlanner) ---
export interface UserWorkTime {
  dayOfWeek: "MONDAY" | "TUESDAY" | "WEDNESDAY" | "THURSDAY" | "FRIDAY" | "SATURDAY" | "SUNDAY";
  startTime: string; // Format: HH:MM or HH:MM:SS
  endTime: string;   // Format: HH:MM or HH:MM:SS
  // userId?: string; // Link to user, might be implicit if nested under UserAvailability
}

export interface UserAvailability {
  userId: string;
  workTimes: UserWorkTime[];
  calendarEvents: CalendarEvent[]; // Existing events in the queried window
}

// --- Smart Meeting Preparation Types ---
export interface NotionPageContext {
  id: string;
  title: string;
  url?: string; // Notion page URL
  briefSnippet?: string; // A short relevant snippet from the page content
}

export interface EmailContext {
  id: string; // Email message ID
  subject: string;
  sender?: string; // Sender's email or name
  receivedDate?: string; // ISO 8601 string
  url?: string; // URL to view the email if available (e.g., Gmail link)
  briefSnippet?: string; // Short snippet from the email body
}

export interface TaskContext {
  id: string; // Notion Task Page ID
  description: string;
  dueDate?: string | null; // ISO date string or null
  status?: NotionTaskStatus;
  url?: string; // URL to the Notion task page
}

export interface MeetingPreparationData {
  targetMeeting: CalendarEvent; // The meeting being prepared for
  relatedNotionPages?: NotionPageContext[];
  relatedEmails?: EmailContext[];
  relatedTasks?: TaskContext[];
  keyPointsFromLastMeeting?: string; // Optional: summary from previous similar meeting
  errorMessage?: string; // If preparation is partial or fails (e.g., "Could not fetch Notion documents.")
}

// Response for the PrepareForMeeting skill
export interface PrepareForMeetingResponse extends SkillResponse<MeetingPreparationData> {}

// NLU Entities expected for the PrepareForMeeting intent
export interface PrepareForMeetingEntities {
  meeting_identifier?: string; // e.g., "Project Alpha discussion", "next meeting", "call with John"
  meeting_date_time?: string; // e.g., "tomorrow", "2024-07-15T14:00:00Z", "next Monday at 3pm"
  // Future: could include specific attendees to focus on, or types of info (e.g., "only show tasks")
}

// --- Automated Weekly Digest Types ---
export interface WeeklyDigestData {
  periodStart: string; // ISO Date string
  periodEnd: string; // ISO Date string
  completedTasks: NotionTask[]; // Using existing NotionTask type
  attendedMeetings: CalendarEvent[]; // Using existing CalendarEvent type
  // For attendedMeetings, consider adding a briefOutcome?: string if V2 summarization is done
  upcomingCriticalTasks: NotionTask[];
  upcomingCriticalMeetings: CalendarEvent[];
  errorMessage?: string;
}

// Response for the GenerateWeeklyDigest skill
export interface GenerateWeeklyDigestResponse extends SkillResponse<{
  digest: WeeklyDigestData;
  formattedSummary: string; // The user-facing text summary
}> {}

// NLU Entities expected for the GenerateWeeklyDigest intent
export interface GenerateWeeklyDigestEntities {
  time_period?: "this week" | "last week" | string; // Allow specific date ranges in future if NLU supports
}

// --- Intelligent Follow-up Suggester Types ---
export type PotentialFollowUpType = "action_item" | "decision" | "question" | "information";

export interface PotentialFollowUp {
  type: PotentialFollowUpType;
  description: string; // The text of the action, decision, or question
  suggestedAssignee?: string; // If an action item and an assignee is suggested by LLM
  sourceContext?: string; // e.g., "From meeting notes: Project Phoenix Q1 Review"
  existingTaskFound?: boolean;
  existingTaskId?: string;
  existingTaskUrl?: string;
  // priority?: "High" | "Medium" | "Low"; // Optional: Could be set by LLM or user later
}

// Data structure returned by the LLM analysis (conceptual)
export interface ExtractedFollowUpItems {
  action_items: Array<{ description: string; assignee?: string }>;
  decisions: Array<{ description: string }>;
  questions: Array<{ description: string }>;
  // general_info_points?: Array<{ description: string }>; // Optional for other key info
}


export interface FollowUpSuggestionData {
  contextName: string; // e.g., "Project Phoenix Meeting - July 26" or "Client Onboarding Project"
  sourceDocumentSummary?: string; // Brief summary or link to the source document analyzed
  suggestions: PotentialFollowUp[];
  errorMessage?: string;
}

// Response for the SuggestFollowUps skill
export interface SuggestFollowUpsResponse extends SkillResponse<FollowUpSuggestionData> {}

// NLU Entities expected for the SuggestFollowUps intent
export interface SuggestFollowUpsEntities {
  context_identifier: string; // e.g., "Project Phoenix meeting", "Client Onboarding project", "my last meeting"
  context_type?: "meeting" | "project" | string; // Helps skill narrow down search for context
}

// --- Meeting Preparation Use Case Types ---

/**
 * Represents the parsed entities from the NLU service for a RequestMeetingPreparation intent.
 * This should align with the 'entities' structure defined for intent #35 in nluService.ts.
 */
export interface MeetingPrepNluEntities {
  meeting_reference: string;
  information_requests: InformationRequest[];
  overall_lookback_period?: string;
}

/**
 * Defines a single information request within a meeting preparation task.
 */
export interface InformationRequest {
  source: 'gmail' | 'slack' | 'notion' | 'calendar_events';
  search_parameters: GmailSearchParameters | SlackSearchParameters | NotionSearchParameters | CalendarEventsSearchParameters;
}

// Parameter types for each source, aligning with NLU output for RequestMeetingPreparation
export interface GmailSearchParameters {
  from_sender?: string;
  subject_keywords?: string;
  body_keywords?: string;
  date_query?: string;
  has_attachment_only?: boolean;
}

export interface SlackSearchParameters {
  channel_name?: string;
  from_user?: string;
  text_keywords?: string;
  date_query?: string;
  mentions_user?: string;
}

export interface NotionSearchParameters {
  database_name_or_id?: string;
  page_title_keywords?: string;
  content_keywords?: string;
  filter_by_meeting_reference_context?: boolean;
}

export interface CalendarEventsSearchParameters {
  related_to_attendees_of_meeting_reference?: boolean;
  keywords_in_summary_or_description?: string;
  date_query_lookback?: string;
  type_filter?: 'past_events' | 'future_events' | 'all_related_events';
}

/**
 * Represents the aggregated results from all information requests for meeting preparation.
 * This is what the meeting preparation skill would aim to construct.
 */
export interface AggregatedPrepResults {
  meeting_reference_identified: string; // The meeting_reference string from NLU
  identified_calendar_event?: CalendarEventSummary; // Details if the meeting_reference was resolved to a specific calendar event
  results_by_source: PrepResultSourceEntry[];
  overall_summary_notes?: string; // Optional AI-generated summary of all findings
  errors_encountered?: PrepErrorMessage[]; // List of errors encountered during the process
}

export interface PrepResultSourceEntry {
  source: 'gmail' | 'slack' | 'notion' | 'calendar_events';
  search_parameters_used: GmailSearchParameters | SlackSearchParameters | NotionSearchParameters | CalendarEventsSearchParameters;
  // Results can be an array of specific types based on the source.
  // Using more specific types than 'any[]' for better type safety.
  results: GmailMessageSnippet[] | SlackMessageSnippet[] | NotionPageSummary[] | CalendarEventSummary[];
  error_message?: string; // If an error occurred fetching from this specific source
  count: number; // Number of items found
  search_query_executed?: string; // Optional: the actual query string run against the source API
}

export interface PrepErrorMessage {
    source_attempted?: 'gmail' | 'slack' | 'notion' | 'calendar_events' | 'overall_process' | 'nlu_parsing' | 'calendar_lookup';
    message: string;
    details?: string; // Stringified version of any underlying error object or additional context
}

// Specific result item types (re-declaring here for clarity if not already globally available or slightly different context)
// If these are identical to global ones, they can be imported. Assuming for now they might have slight variations or are good to have co-located.

export interface GmailMessageSnippet { // Consistent with previous definition if it exists
  id: string;
  threadId?: string;
  subject?: string;
  from?: string;
  date?: string; // ISO string
  snippet?: string;
  link?: string;
}

export interface SlackMessageSnippet { // Consistent with previous definition
  ts: string; // Using 'ts' as the primary ID for Slack messages
  channel?: { id: string; name?: string };
  user?: { id: string; name?: string };
  text?: string;
  permalink?: string;
  files?: any[];
  reactions?: any[];
  thread_ts?: string; // To know if it's part of a thread
}

export interface NotionPageSummary { // Consistent with previous definition
  id: string;
  title?: string;
  url?: string;
  last_edited_time?: string;
  created_time?: string;
  preview_text?: string;
  icon?: { type: string; emoji?: string; external?: { url: string }; file?: { url: string; expiry_time: string } } | null;
}

export interface CalendarEventSummary { // Consistent with previous definition
  id: string;
  summary?: string;
  description?: string;
  start?: string; // ISO string
  end?: string; // ISO string
  htmlLink?: string;
  attendees?: Array<{ email?: string; displayName?: string; responseStatus?: string }>;
  organizer?: { email?: string; displayName?: string; };
}

// --- Automated Post-Meeting Workflow Use Case Types ---

/**
 * Represents the parsed entities from the NLU service for a ProcessMeetingOutcomes intent.
 * Aligns with intent #36 in nluService.ts.
 */
export interface ProcessMeetingOutcomesNluEntities {
  meeting_reference: string;
  source_document_id?: string;
  outcome_source_type?: 'transcript' | 'meeting_notes' | 'audio_recording_summary';
  requested_actions: Array<'SUMMARIZE_KEY_DECISIONS' | 'EXTRACT_ACTION_ITEMS' | 'DRAFT_FOLLOW_UP_EMAIL' | 'CREATE_TASKS_IN_NOTION'>;
  email_draft_details?: {
    recipients: string[] | string; // e.g., ["attendees", "manager@example.com"] or "all meeting attendees"
    additional_instructions?: string;
  };
  task_creation_details?: {
    notion_database_id?: string;
    default_assignee?: string; // e.g., "me" or a user ID/email
  };
}

/**
 * Represents structured information extracted from meeting outcomes.
 * This would be an interim result after an LLM processes the source document.
 */
export interface ExtractedMeetingInsights {
  meeting_title_or_reference: string; // From the source or NLU
  source_document_id_processed?: string;
  key_decisions?: string[];
  action_items?: Array<{
    description: string;
    suggested_assignee?: string; // Name or email
    suggested_due_date?: string; // Natural language or ISO
  }>;
  overall_summary?: string; // A general summary if not just decisions
}

/**
 * Represents the results of performing the requested post-meeting actions.
 */
export interface PostMeetingActionsResults {
  processed_meeting_reference: string;
  summary_of_decisions?: string; // Result of SUMMARIZE_KEY_DECISIONS
  extracted_action_items_summary?: string; // Narrative summary of extracted action items
  drafted_email_content?: {
    to?: string[]; // Resolved recipients
    cc?: string[];
    subject?: string;
    body?: string;
  };
  created_notion_tasks?: Array<{
    taskId: string; // Notion page ID
    taskUrl: string;
    description: string;
    assignee?: string;
    dueDate?: string;
  }>;
  errors_encountered?: Array<{
    action_attempted: 'SUMMARIZE_KEY_DECISIONS' | 'EXTRACT_ACTION_ITEMS' | 'DRAFT_FOLLOW_UP_EMAIL' | 'CREATE_TASKS_IN_NOTION' | 'SOURCE_PROCESSING';
    message: string;
    details?: string;
  }>;
}

// Potential structure for the skill's output
export interface ProcessMeetingOutcomesSkillResponse extends SkillResponse<PostMeetingActionsResults> {}

// --- Unified Priority Dashboard (Daily Briefing) Use Case Types ---

/**
 * Represents the parsed entities from the NLU service for a GetDailyPriorityBriefing intent.
 * Aligns with intent #37 in nluService.ts.
 */
export interface GetDailyPriorityBriefingNluEntities {
  date_context?: string; // e.g., "today", "tomorrow"
  focus_areas?: Array<'tasks' | 'meetings' | 'urgent_emails' | 'urgent_slack_messages' | 'urgent_teams_messages'>;
  project_filter?: string;
  urgency_level?: 'high' | 'critical' | 'all';
}

/**
 * Represents a summarized item for the daily briefing.
 * Generic enough to hold different types of priority items.
 */
export interface BriefingItem {
  type: 'task' | 'meeting' | 'email' | 'slack_message' | 'teams_message';
  title: string; // e.g., Task description, Meeting summary, Email subject
  details?: string; // e.g., Due date, Meeting time, Sender info
  urgency_score?: number; // Calculated score to help with sorting (0-100)
  source_id?: string; // Original ID from the source system
  link?: string; // Direct link to the item if available
  // Storing the original item allows for richer display or actions later
  raw_item?: NotionTask | CalendarEventSummary | GmailMessageSnippet | SlackMessageSnippet | MSTeamsMessage;
}

/**
 * Represents the consolidated data for the daily priority briefing.
 * This is what the skill would construct.
 */
export interface DailyBriefingData {
  briefing_date: string; // ISO date for which the briefing is generated
  user_id: string;
  priority_items: BriefingItem[];
  overall_summary_message?: string; // e.g., "You have 3 high-priority tasks and 2 important meetings today."
  errors_encountered?: Array<{
    source_area: 'tasks' | 'meetings' | 'emails' | 'slack' | 'teams' | 'overall';
    message: string;
    details?: string;
  }>;
}

// Potential structure for the skill's output
export interface GetDailyPriorityBriefingSkillResponse extends SkillResponse<DailyBriefingData> {}

// --- Smart Task Creation from Chat Message Use Case Types ---

/**
 * Represents the parsed entities from the NLU service for a CreateTaskFromChatMessage intent.
 * Aligns with intent #38 in nluService.ts.
 */
export interface CreateTaskFromChatMessageNluEntities {
  chat_message_reference: string;
  source_platform: 'slack' | 'msteams' | 'gmail_thread_item'; // Reflects enum in NLU
  task_description_override?: string;
  target_task_list_or_project?: string;
  assignee?: string;
  due_date?: string;
  priority?: 'high' | 'medium' | 'low';
}

/**
 * Represents the fetched content of a chat message from Slack, Teams, or a Gmail item.
 * This structure would be populated by a skill that retrieves the message.
 */
export interface ChatMessageContent {
  platform: 'slack' | 'msteams' | 'gmail_thread_item';
  message_id?: string; // Original message ID from the platform (e.g., Slack ts, Teams message ID, Gmail message ID)
  channel_id?: string; // Optional, e.g., Slack channel ID, Teams channel/chat ID
  thread_id?: string; // Optional, if it's part of a thread
  sender_id?: string;
  sender_name?: string;
  text_content: string; // The main textual content of the message
  html_content?: string; // Optional HTML version
  message_url?: string; // Permalink to the message/item
  timestamp: string; // ISO 8601 timestamp of when the message was sent
  attachments?: Array<{ name?: string; url?: string; type?: string }>; // Simplified attachment info
}

/**
 * Represents the result of attempting to create a task.
 * This would be part of the skill's output.
 */
export interface TaskCreationResultFromMessage {
  success: boolean;
  message: string; // e.g., "Task created successfully" or error message
  taskId?: string; // Notion Page ID or ID from other task system
  taskUrl?: string; // Link to the created task
  taskTitle?: string; // The actual title/description used for the task
  original_message_link_included?: boolean;
}

// Potential structure for the skill's output for this use case
export interface CreateTaskFromChatMessageSkillResponse extends SkillResponse<TaskCreationResultFromMessage> {}

// --- Complex Task Orchestration Types (e.g., for Use Case 5: Voice-Activated Info & Action Relay) ---

/**
 * Represents the NLU structure for a sub-task within a ComplexTask.
 * This is already part of ProcessedNLUResponse's sub_tasks definition,
 * but defined here for clarity in the context of execution results.
 */
export interface ComplexTaskSubTaskNlu {
  intent: string | null;
  entities: Record<string, any>;
  summary_for_sub_task?: string;
}

/**
 * Represents the result of executing a single sub-task identified within a ComplexTask.
 */
export interface ExecutedSubTaskResult {
  sub_task_nlu: ComplexTaskSubTaskNlu;
  execution_order: number;
  status: 'success' | 'failure' | 'skipped' | 'partial_success';
  message_from_handler?: string; // User-facing message from the specific handler for this sub-task
  error_details?: string;
  returned_data?: any; // Data returned by the sub-task's handler (e.g., an ID, a list of items)
}

/**
 * Represents the overall report of an orchestrated ComplexTask execution.
 * This would be constructed by the logic handling the main ComplexTask intent.
 */
export interface OrchestratedComplexTaskReport {
  original_user_query: string;
  overall_status: 'completed_fully' | 'completed_partially' | 'failed_entirely' | 'clarification_needed_mid_sequence';
  final_summary_message_for_user?: string; // Overall summary message for the user
  sub_task_results: ExecutedSubTaskResult[];
  // Optional context passed between tasks, managed by the orchestrator.
  // Example: output of sub-task 1 (e.g., an email ID) could be stored here to be used as input for sub-task 2.
  inter_task_context?: Record<string, any>;
}

// --- Agent Skill Context and Client Command Types (centralized from handler.ts) ---

/**
 * Defines the structure of commands sent from the agent to the client (e.g., via WebSocket)
 * This should align with the command structure expected by the frontend client.
 */
export interface AgentClientCommand {
  command_id: string; // Unique ID for tracking the command
  action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION'; // Specific actions client can perform
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
    // Other relevant parameters for the client action, e.g. recording quality hints
  };
}

/**
 * Defines the context object that will be passed to agent skills.
 * It includes common utilities or functions that skills might need.
 */
export interface AgentSkillContext {
  userId: string;
  // Function to send a command to the connected client.
  // The actual implementation of this function is expected to be injected by the calling environment (e.g., WebSocket handler in server.ts).
  sendCommandToClient: (userId: string, command: AgentClientCommand) => Promise<boolean>;
  // Potentially add other context items:
  // - Access to LTM/STM (though memoryManager functions are currently imported directly)
  // - User preferences relevant to skills
  // - API clients if they are not globally available or need user-specific configuration
}

// --- LanceDB Semantic Search Types ---
export type SearchResultSourceType = "document_chunk" | "email_snippet" | "notion_summary";

export interface UniversalSearchResultItem {
  // Common fields
  id: string;
  user_id: string;
  source_type: SearchResultSourceType;
  title: string;
  snippet: string;
  vector_score: number;
  original_url_or_link?: string;
  created_at?: string; // ISO 8601
  last_modified_at?: string; // ISO 8601
  ingested_at?: string; // ISO 8601

  // For "document_chunk"
  document_id?: string;
  parent_document_title?: string;
  chunk_sequence?: number;
  document_source_uri?: string;
  document_doc_type?: string;

  // For "email_snippet"
  email_thread_id?: string;
  email_from_sender?: string;
  email_date?: string; // ISO 8601

  // For "notion_summary"
  notion_icon_json?: string;

  metadata_json?: string;
}


// --- Hybrid Search Types ---
export type HybridMatchSource = 'semantic' | 'keyword';

/**
 * Represents a unified search result item from the hybrid search backend.
 * Mirrors the `UnifiedSearchResultItem` Pydantic model in `hybrid_search_service.py`.
 */
export interface HybridSearchResultItem {
  doc_id: string;
  user_id: string;
  title?: string | null;
  snippet?: string | null;
  source_uri?: string | null;
  doc_type?: string | null;
  created_at_source?: string | null; // ISO datetime string
  last_modified_source?: string | null; // ISO datetime string
  ingested_at: string; // ISO datetime string
  score?: number | null; // Original score from the source system
  match_type: HybridMatchSource; // 'semantic' or 'keyword'
  extracted_text_preview?: string | null;
  additional_properties?: Record<string, any> | null;
}

/**
 * Defines the structure for the filters object used in hybrid search.
 * This should be constructed by the frontend and passed to the search skill.
 */
export interface HybridSearchFilters {
  doc_types?: string[];
  date_after?: string; // ISO 8601 string
  date_before?: string; // ISO 8601 string
  date_field_to_filter?: 'ingested_at' | 'created_at_source' | 'last_modified_source';
  metadata_properties?: Record<string, string>;
}
