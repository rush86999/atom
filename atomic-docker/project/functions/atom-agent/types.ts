// Main types for Atom agent

export interface AtomMessage {
  id: string;
  text: string;
  // Potentially add a timestamp, sender, etc.
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

export interface ListGoogleMeetEventsResponse {
  ok: boolean;
  events?: CalendarEvent[]; // Reusing CalendarEvent as it will contain Meet details
  error?: string;
}

export interface GetGoogleMeetEventDetailsResponse {
  ok: boolean;
  event?: CalendarEvent; // Reusing CalendarEvent
  error?: string;
}


export interface CreateEventResponse {
  success: boolean;
  eventId?: string;
  message: string;
  htmlLink?: string; // Link to the created event in Google Calendar
}

// Generic skill response structure (optional, but can be useful)
export interface SkillResponse {
  success: boolean;
  message: string;
  data?: any; // Any data returned by the skill
}

// --- Email Types ---
export interface Email {
  id: string;
  sender: string;
  recipient: string;
  subject: string;
  body: string;
  timestamp: string; // ISO 8601 date-time string
  read: boolean;
  // attachments?: Attachment[]; // Future enhancement
}

export interface SendEmailResponse {
  success: boolean;
  emailId?: string; // ID of the sent email, if successful/applicable
  message: string;
}

export interface ReadEmailResponse {
  success: boolean;
  email?: Email;
  message?: string;
}

// We might also want a type for EmailAttachment if we implement that
// export interface EmailAttachment {
//   filename: string;
//   contentType: string;
//   size: number;
//   // data: string; // Base64 encoded or a link
// }

// --- Web Research Types ---
export interface SearchResult {
  title: string;
  link: string;
  snippet: string;
  // Potentially add source, relevance score, etc.
}

// --- Zapier Types ---
export interface ZapTriggerResponse {
  success: boolean;
  zapName?: string;
  runId?: string; // A unique identifier for the Zap run, if available
  message: string;
  // data?: any; // Optional: any data returned by Zapier upon trigger
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

export type GetHubSpotContactResponse = HubSpotContact | null;

export interface CreateHubSpotContactResponse {
  success: boolean;
  contactId?: string;
  message?: string;
  hubSpotContact?: HubSpotContact;
}

// --- HubSpot Engagement Types ---
export interface HubSpotEmailEngagementProperties {
  activityTimestamp: number; // Epoch milliseconds
  subject: string;
  htmlBody: string;
  direction?: 'INCOMING' | 'OUTGOING'; // Optional: direction of the email
  // disposition?: string; // Optional: HubSpot call/email disposition ID (e.g., "Connected")
  // external_url?: string; // Optional: Link to the email in an external system
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
    hs_timestamp?: string; // Engagement timestamp (e.g., when an email was sent/received or meeting occurred)
    hs_body_preview?: string; // Preview of the engagement body
    hs_email_subject?: string; // Subject of the email
    hs_email_direction?: 'INCOMING' | 'OUTGOING';
    // hs_meeting_title?: string; // Title of the meeting (if type is MEETING)
    // hs_meeting_start_time?: string; // Start time of the meeting
    // hs_meeting_end_time?: string; // End time of the meeting
    // hs_call_disposition?: string; // Disposition of the call
    // hs_call_duration?: string; // Duration of the call in milliseconds
    // hs_call_status?: string; // Status of the call (e.g., COMPLETED, NO_ANSWER)
    createdate?: string;
    lastmodifieddate?: string;
    [key: string]: any; // Allow other properties
  };
  associations?: { // Optional, as it might not always be populated depending on the API call
    contacts?: { results: { id: string, type: string }[] };
    companies?: { results: { id: string, type: string }[] };
    // Add other object types as needed (deals, tickets, etc.)
  };
  createdAt: string;
  updatedAt: string;
  archived: boolean;
}

export interface LogEngagementResponse {
  success: boolean;
  engagementId?: string;
  message: string;
  hubSpotEngagement?: HubSpotEngagement; // Optional: The created engagement object
}

export interface GetContactActivitiesResponse {
  success: boolean;
  activities: HubSpotEngagement[];
  message?: string;
  nextPage?: string; // For pagination, 'after' cursor
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
  topic?: {
    value: string;
    creator: string;
    last_set: number;
  };
  purpose?: {
    value: string;
    creator: string;
    last_set: number;
  };
  created?: number;
  creator?: string;
}

export interface SlackMessageResponse {
  ok: boolean;
  ts?: string; // Timestamp of the message
  channel?: string; // Channel ID where the message was posted
  message?: { // Detailed message object, structure can vary
    text?: string;
    user?: string; // User ID of the sender (could be bot_id or user_id)
    bot_id?: string; // ID of the bot if message sent by a bot
    ts?: string; // Timestamp of the message
    type?: string; // e.g., 'message'
    subtype?: string; // e.g., 'bot_message', 'channel_join'
    [key: string]: any; // Allow other properties as message structure varies
  };
  error?: string; // Error message if ok is false
  // response_metadata?: { // For errors like 'ratelimited'
  //   messages?: string[];
  //   retry_after?: number;
  // };
}

export interface ListSlackChannelsResponse {
  ok: boolean;
  channels?: SlackChannel[];
  error?: string;
  nextPageCursor?: string; // For pagination
}

// --- Calendly Types ---
// Note: These are simplified. The Calendly SDK might provide more detailed types.
// We will aim to use SDK types directly in calendlySkills.ts if possible and adapt these if necessary.

export interface CalendlyUser {
  uri: string; // e.g., "https://api.calendly.com/users/AAAAAAAAAAAAAAAA"
  name: string;
  slug: string; // User's Calendly username/slug (e.g., "acmesales")
  email: string;
  scheduling_url: string; // e.g., "https://calendly.com/acmesales"
  timezone: string; // e.g., "America/New_York"
  avatar_url?: string | null;
  created_at: string; // ISO 8601 Timestamp
  updated_at: string; // ISO 8601 Timestamp
  // current_organization: string; // URI of the organization
}

export interface CalendlyEventType {
  uri: string; // e.g., "https://api.calendly.com/event_types/AAAAAAAAAAAAAAAA"
  name: string;
  active: boolean;
  slug: string; // Event type slug (e.g., "15min")
  scheduling_url: string; // Full URL to schedule this event type
  duration: number; // Duration in minutes
  kind: 'solo' | 'group'; // Type of event
  pooling_type?: 'round_robin' | 'collective' | null; // For group events
  type: string; // e.g., "StandardEventType" (there can be others)
  color: string;
  created_at: string;
  updated_at: string;
  // internal_note?: string | null;
  // description_plain?: string | null;
  // description_html?: string | null;
  // profile?: {
  //   name: string;
  //   owner: string; // URI of the user or organization
  //   type: 'User' | 'Organization';
  // };
  // custom_questions: any[]; // Define more strictly if needed
  // locations: CalendlyScheduledEventLocation[]; // Possible locations
}

export interface CalendlyScheduledEventLocation {
  type: 'physical' | 'inbound_call' | 'outbound_call' | 'custom' | 'google_conference' | 'gotomeeting_conference' | 'microsoft_teams_conference' | 'zoom_conference' | string; // string for future types
  location?: string | null; // Details like address, phone number, meeting URL
  // join_url?: string | null; // For video conferences, specifically Zoom, Google Meet, etc.
  // status?: 'initiated' | 'pushed' | 'failed'; // For some integrations like Zoom
}

export interface CalendlyInvitee {
  uri: string; // e.g., "https://api.calendly.com/scheduled_events/EVENT_UUID/invitees/INVITEE_UUID"
  email: string;
  name: string;
  first_name?: string | null;
  last_name?: string | null;
  status: 'active' | 'canceled';
  questions_and_answers: { question: string; answer: string; position: number }[];
  timezone: string; // e.g., "America/New_York"
  event_uri: string;
  cancel_url: string; // URL to cancel the event for this invitee
  reschedule_url: string; // URL to reschedule the event for this invitee
  created_at: string;
  updated_at: string;
  // payment?: {
  //   id: string;
  //   provider: 'stripe' | 'paypal';
  //   amount: number;
  //   currency: string;
  //   terms: string;
  //   successful: boolean;
  // } | null;
  // old_invitee?: string | null; // URI if this invitee was rescheduled
  // new_invitee?: string | null; // URI if this invitee rescheduled to a new one
  // tracking: {
  //   utm_campaign?: string | null;
  //   utm_source?: string | null;
  //   utm_medium?: string | null;
  //   utm_content?: string | null;
  //   utm_term?: string | null;
  //   salesforce_uuid?: string | null;
  // };
}

export interface CalendlyScheduledEvent {
  uri: string; // e.g., "https://api.calendly.com/scheduled_events/EVENT_UUID"
  name: string; // Name of the event (often Event Type name)
  status: 'active' | 'canceled';
  start_time: string; // ISO 8601 Timestamp
  end_time: string; // ISO 8601 Timestamp
  event_type: string; // URI of the EventType
  location: CalendlyScheduledEventLocation;
  // invitees_counter: {
  //   total: number;
  //   active: number;
  //   limit: number;
  // };
  created_at: string;
  updated_at: string;
  // event_memberships: { user: string /* URI */ }[]; // Users assigned to the event if it's a team event
  // event_guests: { email: string; created_at: string; updated_at: string }[]; // Guests added by invitee
  // cancellation?: {
  //   canceler_uri: string; // URI of user who canceled
  //   canceled_by: string; // Name of person who canceled
  //   reason: string;
  //   canceler_type: 'host' | 'invitee';
  // } | null;
  // no_show?: {
  //   uri: string; // URI of the no_show object
  //   created_at: string;
  // } | null;
}

export interface CalendlyPagination {
  count: number;
  next_page?: string | null; // URL for the next page
  previous_page?: string | null; // URL for the previous page
  next_page_token?: string | null; // Token for next page (if token-based)
  previous_page_token?: string | null; // Token for previous page
}

export interface ListCalendlyEventTypesResponse {
  ok: boolean;
  collection?: CalendlyEventType[];
  pagination?: CalendlyPagination;
  error?: string;
}

// --- Microsoft Graph / Teams Types ---
export interface MSGraphDateTimeTimeZone {
  dateTime: string; // ISO 8601 format e.g., "2024-03-20T10:00:00.0000000"
  timeZone: string; // e.g., "UTC" or "Pacific Standard Time"
}

export interface MSGraphOnlineMeetingInfo {
  joinUrl?: string | null;
  conferenceId?: string | null; // Often the numeric ID for joining by phone
  tollNumber?: string | null;
  // quickDial?: string | null; // Pre-formatted dial string
  // phones?: { type: string; number: string; }[];
  // Passcode/conference ID might be in other properties or in meeting body/details
  [key: string]: any; // Allow other properties
}

export interface MSGraphEvent {
  id: string;
  subject?: string | null;
  bodyPreview?: string | null; // Plain text preview of the body
  body?: { // Full body, usually HTML
    contentType?: 'html' | 'text';
    content?: string | null;
  } | null;
  start?: MSGraphDateTimeTimeZone | null;
  end?: MSGraphDateTimeTimeZone | null;
  isOnlineMeeting?: boolean | null;
  onlineMeetingProvider?: 'teamsForBusiness' | 'skypeForBusiness' | 'skypeForConsumer' | string | null;
  onlineMeeting?: MSGraphOnlineMeetingInfo | null; // Contains joinUrl etc. if it's a Teams meeting
  webLink?: string | null; // Link to the event in Outlook on the web
  attendees?: { // Simplified, full Attendee type is more complex
    emailAddress?: { address?: string | null; name?: string | null; };
    type?: 'required' | 'optional' | 'resource';
    status?: { response?: string; time?: string; }; // e.g. "accepted", "tentativelyAccepted"
  }[];
  location?: { // Simplified
    displayName?: string | null;
    locationType?: 'default' | 'conferenceRoom' | 'homeAddress' | 'businessAddress' | string;
    uniqueId?: string | null; // If it's a known location like a conference room
    address?: any; // PhysicalAddress type
    coordinates?: any; // GeoCoordinates type
  } | null;
  locations?: any[]; // Array of location objects
  organizer?: { // Simplified
    emailAddress?: { name?: string | null; address?: string | null; };
  } | null;
  [key: string]: any; // Allow other properties from MS Graph API
}

export interface ListMSTeamsMeetingsResponse {
  ok: boolean;
  events?: MSGraphEvent[];
  error?: string;
  nextLink?: string; // OData nextLink for pagination
}

export interface GetMSTeamsMeetingDetailsResponse {
  ok: boolean;
  event?: MSGraphEvent;
  error?: string;
}

export interface MSGraphTokenResponse { // For MSAL client credential flow
  token_type: string; // e.g., "Bearer"
  expires_in: number; // Seconds until expiry, e.g., 3599
  ext_expires_in?: number; // Additional extended expiry
  access_token: string;
  // expires_on might be provided by MSAL in its AuthenticationResult, not directly in API response
}

// --- Zoom Types ---
export interface ZoomTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number; // Typically 3600 seconds (1 hour)
  scope: string; // e.g. "meeting:read user:read"
}

export interface ZoomMeeting {
  uuid: string;
  id: string; // Meeting ID (numeric)
  host_id?: string;
  topic: string;
  type: number; // 1: Instant, 2: Scheduled, 3: Recurring no fixed time, 8: Recurring fixed time
  start_time?: string; // ISO 8601 Timestamp (only for scheduled/recurring)
  duration?: number; // In minutes
  timezone?: string;
  agenda?: string;
  created_at: string; // ISO 8601 Timestamp
  join_url: string;
  // status?: 'waiting' | 'started' | 'finished'; (May vary based on API endpoint)
  // recurrence?: any; // Define if needed
  // occurrences?: any[]; // Define if needed for recurring meetings
  // settings?: any; // Define if needed
  [key: string]: any; // Allow other properties as Zoom API is extensive
}

export interface ListZoomMeetingsResponse {
  ok: boolean;
  meetings?: ZoomMeeting[];
  error?: string;
  // Pagination fields from Zoom API for list meetings
  page_count?: number;
  page_number?: number;
  page_size?: number;
  total_records?: number;
  next_page_token?: string;
}

export interface GetZoomMeetingDetailsResponse {
  ok: boolean;
  meeting?: ZoomMeeting;
  error?: string;
}

export interface ListCalendlyScheduledEventsResponse {
  ok: boolean;
  collection?: CalendlyScheduledEvent[];
  pagination?: CalendlyPagination;
  error?: string;
}
