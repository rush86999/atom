import {
  BufferTimeObjectType,
  EventPartPlannerRequestBodyType,
  EventPlusType,
  MeetingAssistEventType,
  PlannerBodyResponseType,
  RemindersForEventType,
} from '@post_process_calendar/_libs/types';

export type sendUpdates = 'all' | 'externalOnly' | 'none';

export type transparency = 'opaque' | 'transparent'; // available or not

export type visibility = 'default' | 'public' | 'private' | 'confidential';

export type link = {
  title: string;
  link: string;
};

export type override = {
  location?: {
    title?: string;
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
  dateString?: string;
  dateNumber?: number;
};

export type alarms = {
  overrides: override[];
  useDefault: boolean;
};

export type attachment = {
  title: string;
  fileUrl: string;
  mimeType: string;
  iconLink: string;
  fileId: string;
};

export type recurrenceRule =
  | {
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

export type location = {
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

export type creator = {
  id?: string;
  email?: string;
  displayName?: string;
  self?: boolean;
};

export type organizer = {
  id: string;
  email: string;
  displayName: string;
  self: boolean;
};

export type extendedProperties = {
  private?: {
    keys?: string[];
    values?: string[];
  };
  shared?: {
    keys?: string[];
    values?: string[];
  };
};

// export type source = { [eventVectorName]: number[], userId: string }

type HH =
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
type MM =
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
  | '23'
  | '24'
  | '25'
  | '26'
  | '27'
  | '28'
  | '29'
  | '30'
  | '31'
  | '32'
  | '33'
  | '34'
  | '35'
  | '36'
  | '37'
  | '38'
  | '39'
  | '40'
  | '41'
  | '42'
  | '43'
  | '44'
  | '45'
  | '46'
  | '47'
  | '48'
  | '49'
  | '50'
  | '51'
  | '52'
  | '53'
  | '54'
  | '55'
  | '56'
  | '57'
  | '58'
  | '59';
// type SS = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23' | '24' | '25' | '26' | '27' | '28' | '29' | '30' | '31' | '32' | '33' | '34' | '35' | '36' | '37' | '38' | '39' | '40' | '41' | '42' | '43' | '44' | '45' | '46' | '47' | '48' | '49' | '50' | '51' | '52' | '53' | '54' | '55' | '56' | '57' | '58' | '59'

type Time = `${HH}:${MM}`;

export type ReminderType = {
  id: string;
  userId: string;
  eventId: string;
  reminderDate?: string;
  timezone?: string;
  minutes?: number;
  useDefault?: boolean;
  updatedAt: string;
  createdDate: string;
  deleted: boolean;
};

export type PreAndPostTimeBlockType = {
  beforeEvent: EventPlusType;
  afterEvent: EventPlusType;
};

type defaultPreAndPostTimeBlock = {
  beforeEvent: number;
  afterEvent: number;
};

type defaultReminders = number[];

type defaultTimePreference = {
  dayOfWeek?: number;
  startTime: Time;
  endTime: Time;
}[];

export type CategoryType = {
  id: string;
  userId: string;
  name: string;
  updatedAt: string;
  createdDate: string;
  deleted: boolean;
  copyAvailability?: boolean;
  copyTimeBlocking?: boolean;
  copyTimePreference?: boolean;
  copyReminders?: boolean;
  copyPriorityLevel?: boolean;
  copyModifiable?: boolean;
  defaultAvailability?: boolean;
  defaultTimeBlocking?: defaultPreAndPostTimeBlock;
  defaultTimePreference?: defaultTimePreference;
  defaultReminders?: defaultReminders;
  defaultPriorityLevel?: number;
  defaultModifiable?: boolean;
  copyIsBreak?: boolean;
  defaultIsBreak?: boolean;
  color?: string;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  defaultIsMeeting?: boolean;
  defaultIsExternalMeeting?: boolean;
  defaultMeetingModifiable?: boolean;
  defaultExternalMeetingModifiable?: boolean;
};

export type calendarQueueBody = {
  userId: string;
  startDate: string;
  endDate: string;
  timezone?: string;
};

export type PostProcessQueueBodyForCalendarType = {
  plannerBodyResponse: PlannerBodyResponseType;
  eventParts: EventPartPlannerRequestBodyType[];
  allEvents: EventPlusType[];
  newHostBufferTimes?: BufferTimeObjectType[];
  newHostReminders?: RemindersForEventType[];
  breaks?: EventPlusType[];
  oldEvents: EventPlusType[];
  oldAttendeeEvents?: MeetingAssistEventType[];
  hostTimezone: string;
  // New fields for replan context
  isReplan?: boolean;
  originalGoogleEventId?: string;
  originalCalendarId?: string;
};

export type MessageQueueType = {
  messageId: string;
  receiptHandle: string;
  body: string; // json stringified
  attributes: {
    ApproximateReceiveCount: string; // stringified number
    SentTimestamp: string; // stringified number
    SenderId: string; // function id
    ApproximateFirstReceiveTimestamp: string; // stringified number
  };
  messageAttributes: object;
  md5OfMessageAttributes: null;
  md5OfBody: string;
  eventSource: string; // 'aws:sqs',
  eventSourceARN: string; // 'arn:aws:sqs:us-east-1:767299747852:googlecalendarsync-dev-atomic-create-calendar-queue',
  awsRegion: string; // 'us-east-1'
};
