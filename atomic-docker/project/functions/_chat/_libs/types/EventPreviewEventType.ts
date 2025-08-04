// EventPreviewEventType - representing condensed event data for preview purposes
export type EventPreviewEventType = {
  id: string;
  eventId: string;
  summary: string;
  startDate: string;
  endDate: string;
  timezone: string;
  allDay: boolean;
  color: string;
  calendarId: string;
  calendarName?: string | null;
  description?: string;
  location?: string | null;
  conference?: string | null;
  attendees?: Array<{
    id: string;
    displayName?: string | null;
    email: string;
    responseStatus?: string;
    organizer?: boolean;
    isSelf?: boolean;
  }> | null;
  recurrenceRule?: string | null;
  recurrenceId?: string | null;
  reminders?: Array<{
    method: string;
    minutes: number;
  }> | null;
  created: string;
  updated: string;
  creator?: {
    id?: string | null;
    email?: string | null;
    displayName?: string | null;
  } | null;
  organizer?: {
    id?: string | null;
    email?: string | null;
    displayName?: string | null;
  } | null;
  priority?: number | null;
  status?: string;
  transparency?: string;
  visibility?: string;
  hangoutLink?: string | null;
  privateCopy?: boolean;
  extendedProperties?: {
    private?: Record<string, string>;
    shared?: Record<string, string>;
  };
  customProperties?: Record<string, string>;
  source?: {
    title?: string | null;
    url?: string | null;
  };
  attachments?: Array<{
    fileUrl?: string | null;
    title?: string | null;
    mimeType?: string | null;
    iconLink?: string | null;
    fileId?: string | null;
  }> | null;
  eventType?: string | null;
  transparencySpecified?: boolean;
  userId?: string;
  userEmail?: string;
  originalSyncToken?: string | null;
  isDeleted?: boolean;
  recurringEventId?: string | null;
  originalStartDateTime?: string | null;
  originalStartTimezone?: string | null;
  originalEndDateTime?: string | null;
  originalEndTimezone?: string | null;
  isRecurring?: boolean;
  isException?: boolean;
  recurringPattern?: string | null;
  duration?: number;
  extendedPropertiesMap?: Record<string, string>;
  colorId?: string | null;
  kind?: string;
  etag?: string;
};
