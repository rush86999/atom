// This file contains shared TypeScript types for the GPT functions.

export type GoogleSendUpdatesType = 'all' | 'externalOnly' | 'none';

export type GoogleAttendeeType = {
  additionalGuests?: number;
  comment?: string;
  displayName?: string;
  email: string;
  id?: string;
  responseStatus?: 'needsAction' | 'declined' | 'tentative' | 'accepted';
};

type GoogleEntryPointType = {
  accessCode?: string;
  label?: string;
  entryPointType: 'video' | 'phone' | 'sip' | 'more';
  meetingCode?: string;
  passcode?: string;
  password?: string;
  pin?: string;
  uri?: string;
};

export type GoogleConferenceDataType = {
  type: 'hangoutsMeet' | 'addOn';
  iconUri?: string;
  name?: string;
  requestId?: string; // This will be the generatedId passed to createGoogleEvent
  conferenceId?: string;
  createRequest?: {
    requestId: string;
    conferenceSolutionKey: {
      type: 'hangoutsMeet' | 'addOn';
    };
  };
  entryPoints?: GoogleEntryPointType[];
};

export type GoogleExtendedPropertiesType = {
  private?: Record<string, string>; // Changed to Record<string, string> for typical usage
  shared?: Record<string, string>; // Changed to Record<string, string>
};

type OverrideType = {
  method?: 'email' | 'popup'; // reminder type
  minutes?: number;
};

export type OverrideTypes = OverrideType[];

export type GoogleReminderType = {
  overrides?: OverrideTypes; // Made optional as per Google API
  useDefault: boolean;
};

export type GoogleSourceType = {
  title?: string;
  url?: string;
};

export type GoogleTransparencyType = 'opaque' | 'transparent';

export type GoogleVisibilityType =
  | 'default'
  | 'public'
  | 'private'
  | 'confidential';

export type GoogleAttachmentType = {
  title: string;
  fileUrl: string;
  mimeType: string;
  iconLink: string;
  fileId: string;
};

// GoogleEventType1 seems to be a typo, perhaps eventType from Google's API?
// Let's assume it's the 'eventType' field on the Event resource.
export type GoogleApiEventType =
  | 'default'
  | 'outOfOffice'
  | 'focusTime'
  | 'workingLocation';

export type ColorType = {
  // This is likely our internal ColorType, not Google's directly
  id: string;
  background: string;
  foreground: string;
  itemType: 'calendar' | 'event';
};

export type CalendarIntegrationType = {
  id: string;
  userId: string;
  token?: string;
  refreshToken?: string;
  resource?: string;
  name?: string;
  enabled?: boolean;
  syncEnabled?: boolean;
  deleted?: boolean;
  appId?: string;
  appEmail?: string;
  appAccountId?: string;
  contactName?: string;
  contactEmail?: string;
  colors?: ColorType[];
  clientType?: 'ios' | 'android' | 'web' | 'atomic-web';
  expiresAt?: string;
  updatedAt: string;
  createdDate: string;
  pageToken?: string;
  syncToken?: string;
  primaryCalendarId?: string;
};

export type RecurrenceRuleType =
  | {
      // This seems to be our internal type, not Google's directly
      frequency: string;
      endDate: string;
      occurrence?: number;
      interval: number;
      byWeekDay?: string[];
    }
  | {
      frequency: string;
      endDate?: string;
      occurrence: number;
      interval: number;
      byWeekDay?: string[];
    };

export type LocationType = {
  // Our internal location type
  title: string;
  proximity?: string;
  radius?: number;
  coords?: {
    latitude?: number;
    longitude?: number;
  };
  address?: {
    houseNumber?: number;
    prefixDirection?: string;
    prefixType?: string;
    streetName?: string;
    streetType?: string;
    suffixDirection?: string;
    city?: string;
    state?: string;
    postalCode?: string;
    country?: string;
  };
};

export type LinkType = {
  title: string;
  link: string;
};

// SendUpdatesType is already defined as GoogleSendUpdatesType

export type TransparencyType = 'opaque' | 'transparent';

export type VisibilityType = 'default' | 'public' | 'private' | 'confidential';

export type CreatorType = {
  id?: string;
  email?: string;
  displayName?: string;
  self?: boolean;
};

export type OrganizerType = {
  id?: string; // Google API makes organizer.id optional
  email: string;
  displayName?: string; // Optional
  self?: boolean;
};

// ExtendedPropertiesType is already defined as GoogleExtendedPropertiesType

export type BufferTimeNumberType = {
  beforeEvent: number;
  afterEvent: number;
};

export type MM =
  | '01'
  | '02'
  | '03'
  | '04'
  | '05'
  | '06'
  | '07'
  | '08'
  | '09'
  | '10'
  | '11'
  | '12';
export type HH =
  | '00'
  | '01'
  | '02'
  | '03'
  | '04'
  | '05'
  | '06'
  | '07'
  | '08'
  | '09'
  | '10'
  | '11'
  | '12'
  | '13'
  | '14'
  | '15'
  | '16'
  | '17'
  | '18'
  | '19'
  | '20'
  | '21'
  | '22'
  | '23';
export type Time = `${HH}:${MM}`;

export type EventType = {
  // This is our Hasura Event type
  id: string;
  userId: string;
  calendarId: string;
  gEventId?: string | null;
  provider?: string | null;
  title?: string;
  summary?: string | null;
  description?: string | null;
  startDate: string; // Potentially legacy if startDateTime is primary
  endDate: string; // Potentially legacy
  startDateTime?: string | null;
  endDateTime?: string | null;
  allDay?: boolean;
  recurrenceRule?: RecurrenceRuleType; // This would be our internal representation
  location?: LocationType; // Our internal representation
  notes?: string; // Potentially legacy, description is more standard for Google
  attachments?: GoogleAttachmentType[]; // If storing Google's attachment structure
  links?: LinkType[];
  timezone?: string;
  createdDate: string;
  deleted: boolean;
  isDeleted?: boolean | null;
  taskId?: string;
  taskType?: string;
  priority: number;
  followUpEventId?: string;
  isFollowUp: boolean;
  isPreEvent: boolean;
  isPostEvent: boolean;
  preEventId?: string;
  postEventId?: string;
  modifiable: boolean;
  forEventId?: string;
  conferenceId?: string; // Google's conference ID
  maxAttendees?: number;
  sendUpdates?: GoogleSendUpdatesType;
  anyoneCanAddSelf: boolean;
  guestsCanInviteOthers: boolean;
  guestsCanSeeOtherGuests: boolean;
  originalStartDate: string; // Potentially legacy
  originalAllDay: boolean; // Potentially legacy
  status?: string; // Google's event status e.g. 'confirmed', 'tentative', 'cancelled'
  summary?: string | null; // Already have this
  transparency?: GoogleTransparencyType;
  visibility?: GoogleVisibilityType;
  recurringEventId?: string; // Google's recurring event ID
  updatedAt: string;
  iCalUID?: string;
  htmlLink?: string;
  colorId?: string; // Google's colorId for the event
  creator?: CreatorType;
  organizer?: OrganizerType;
  endTimeUnspecified?: boolean;
  recurrence?: string[]; // Google's RRULE strings
  originalTimezone?: string; // Potentially legacy if start/end objects have timezone
  attendeesOmitted?: boolean;
  extendedProperties?: GoogleExtendedPropertiesType;
  hangoutLink?: string;
  guestsCanModify?: boolean;
  locked?: boolean;
  source?: GoogleSourceType;
  eventType?: GoogleApiEventType; // Google's eventType
  privateCopy?: boolean;
  backgroundColor?: string; // Our internal color mapping
  foregroundColor?: string; // Our internal color mapping
  useDefaultAlarms?: boolean; // Deprecated, use reminders.useDefault
  // ... (other fields from existing type)
  meetingId?: string;
  eventId: string; // This might be a duplicate of gEventId or our internal ID if different from Hasura's 'id'
};

type DefaultReminder = {
  method: string;
  minutes: number;
};

export type CalendarType = {
  id: string;
  userId: string;
  title?: string;
  backgroundColor?: string;
  foregroundColor?: string;
  colorId?: string;
  account?: object;
  accessLevel?: string;
  resource?: string;
  modifiable?: boolean;
  defaultReminders?: DefaultReminder[];
  primary?: boolean;
  globalPrimary?: boolean;
  pageToken?: string;
  syncToken?: string;
  deleted: boolean;
  createdDate: string;
  updatedAt: string;
  type?: string;
};

type DayOfWeekIntType = 1 | 2 | 3 | 4 | 5 | 6 | 7;

type StartTimeType = { day: DayOfWeekIntType; hour: number; minutes: number };
type EndTimeType = { day: DayOfWeekIntType; hour: number; minutes: number };

export type NotAvailableSlotType = { startDate: string; endDate: string };

export interface UserPreferencesType {
  id: string;
  userId: string;
  reminders?: number[];
  followUp?: number[];
  isPublicCalendar?: boolean;
  publicCalendarCategories?: string[];
  startTimes?: StartTimeType[];
  endTimes?: EndTimeType[];
  workHoursStartTime?: string;
  workHoursEndTime?: string;
  workDays?: number[];
  slotDuration?: number;
  timezone?: string;
  bufferBetweenMeetings?: number;
  // ... other fields from existing type
  maxWorkLoadPercent: number;
  minNumberOfBreaks: number;
  breakLength: number;
  breakColor?: string;
  backToBackMeetings: boolean;
  maxNumberOfMeetings: number;
  somePreference?: string;
  // Fields for copying from existing type
  copyAvailability?: boolean;
  copyTimeBlocking?: boolean;
  copyTimePreference?: boolean;
  copyReminders?: boolean;
  copyPriorityLevel?: boolean;
  copyModifiable?: boolean;
  copyCategories?: boolean;
  copyIsBreak?: boolean;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  copyColor?: boolean;
  updatedAt?: string;
  createdDate?: string;
  deleted: boolean;
}

export type AvailabilitySlotType = { startDate: string; endDate: string };

export type FindAvailabilityBodyType = {
  userId: string;
  email: string;
  shareAvailability: boolean;
  receiver: string;
  sender: string;
  receiverCharacteristics?: string[];
  receiverGoals?: string[];
  senderCharacteristics?: string[];
  senderGoals?: string[];
  windowStartDate?: string;
  windowEndDate?: string;
  senderTimezone?: string;
  receiverTimezone?: string;
  slotDuration?: number;
};

export interface MeetingRequestBodyType {
  userId: string;
  clientType: 'ios' | 'android' | 'web' | 'atomic-web';
  userTimezone: string;
  userDateContext: string;
  attendees: string;
  subject: string;
  prompt: string;
  durationMinutes: number;
  shareAvailability: boolean;
  availabilityUserDateStart?: string;
  availabilityUserDateEnd?: string;
  emailTo: string;
  emailName: string;
  yesLink: string;
  noLink: string;
  receiver: string;
  sender: string;
  [key: string]: any;
}

export type DailyScheduleObjectType = {
  start_time: string;
  end_time: string;
  task: string;
  description?: string;
};

export type HowToTaskRequestBodyType = {
  userId: string;
  task: string;
  isAllDay: boolean;
  timezone: string;
  startDate: string;
  endDate: string;
  email?: string;
  name?: string;
  isTwo?: boolean;
};

export type CreateDayScheduleBodyType = {
  userId: string;
  tasks: Array<{
    summary: string;
    description?: string;
    start_time?: string;
    end_time?: string;
    duration?: number;
  }>;
  isAllDay?: boolean;
  timezone: string;
  startDate: string;
  endDate: string;
  email?: string;
  name?: string;
  isTwo?: boolean;
  prompt?: string;
};

export type BreakDownTaskRequestBodyType = {
  userId: string;
  task: string;
  taskDescription?: string;
  isAllDay: boolean;
  timezone: string;
  startDate: string;
  endDate: string;
  email?: string;
  name?: string;
  isTwo?: boolean;
};

export type CreatePeriodSummaryRequestBodyType = {
  userId: string;
  startDate: string;
  endDate: string;
  timezone: string;
  email?: string;
  name?: string;
};

export type CreateAgendaRequestBodyType = {
  userId: string;
  clientType: CalendarIntegrationType['clientType'];
  isAllDay: boolean;
  timezone: string;
  email: string;
  name: string;
  startDate: string;
  endDate: string;
  mainTopic: string;
  relevantPoints?: string[];
  goals?: string[];
  location?: string;
  isTwo?: boolean;
};

export type GoogleResType = {
  id: string;
  googleEventId: string;
  generatedId: string;
  calendarId: string;
  generatedEventId: string;
};

// New Interface for createGoogleEvent options
export interface CreateGoogleEventOptions {
  summary?: string;
  description?: string;
  location?: string; // Simple text location
  colorId?: string; // Google Calendar colorId
  attendees?: GoogleAttendeeType[];
  conferenceData?: GoogleConferenceDataType; // Allows specifying 'eventHangout', 'hangoutsMeet', or null
  extendedProperties?: GoogleExtendedPropertiesType;
  recurrence?: string[]; // RRULE strings, e.g., ['RRULE:FREQ=WEEKLY;UNTIL=20241231T170000Z']
  reminders?: GoogleReminderType;
  source?: GoogleSourceType;
  status?: 'confirmed' | 'tentative' | 'cancelled';
  transparency?: GoogleTransparencyType;
  visibility?: GoogleVisibilityType;
  iCalUID?: string; // Usually generated by Google, but can be set
  attendeesOmitted?: boolean;
  hangoutLink?: string; // Read-only, but could be part of a template if creating from another event
  privateCopy?: boolean;
  locked?: boolean; // If true, only organizer can modify
  attachments?: GoogleAttachmentType[];
  eventType?: GoogleApiEventType;

  // Date and Time fields (mutually exclusive for timed vs all-day)
  startDateTime?: string; // ISO string for timed events
  endDateTime?: string; // ISO string for timed events
  startDate?: string; // YYYY-MM-DD for all-day events
  endDate?: string; // YYYY-MM-DD for all-day events (exclusive end for Google)
  timezone: string; // IANA timezone string, e.g., "America/New_York"
}

// Add other shared types below as needed.
