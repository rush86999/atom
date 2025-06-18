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
  // Potential future additions: attendees, recurrence rules etc.
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
