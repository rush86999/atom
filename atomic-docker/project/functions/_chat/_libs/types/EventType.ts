import DayOfWeekType from "./DayOfWeekType";
import ByMonthDayType from "./ByMonthDayType";

export type LocationType = {
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

export type RecurrenceFrequencyType = "daily" | "weekly" | "monthly" | "yearly";

export type LinkType = {
  title: string;
  link: string;
};

export type RecurrenceRuleType =
  | {
      frequency: RecurrenceFrequencyType;
      endDate: string;
      occurrence?: number;
      interval: number;
      byWeekDay?: DayOfWeekType[];
      byMonthDay?: ByMonthDayType[];
    }
  | {
      frequency: RecurrenceFrequencyType;
      endDate?: string;
      occurrence: number;
      interval: number;
      byWeekDay?: DayOfWeekType[];
      byMonthDay?: ByMonthDayType[];
    };

export type AttachmentType = {
  title?: string;
  fileUrl: string;
  mimeType?: string;
  iconLink?: string;
  fileId?: string;
};

export type SendUpdatesType = "all" | "externalOnly" | "none";

export type TransparencyType = "opaque" | "transparent"; // available or not

export type VisibilityType = "default" | "public" | "private" | "confidential";

export type CreatorType = {
  id?: string;
  email?: string;
  displayName?: string;
  self?: boolean;
};

export type OrganizerType = {
  id: string;
  email: string;
  displayName: string;
  self: boolean;
};

export type ExtendedPropertiesType = {
  private?: {
    keys?: string[];
    values?: string[];
  };
  shared?: {
    keys?: string[];
    values?: string[];
  };
};

export type SourceType = {
  url: string;
  title: string;
};

type HH =
  | "00"
  | "01"
  | "02"
  | "03"
  | "04"
  | "05"
  | "06"
  | "07"
  | "08"
  | "09"
  | "10"
  | "11"
  | "12"
  | "13"
  | "14"
  | "15"
  | "16"
  | "17"
  | "18"
  | "19"
  | "20"
  | "21"
  | "22"
  | "23";
type MM =
  | "00"
  | "01"
  | "02"
  | "03"
  | "04"
  | "05"
  | "06"
  | "07"
  | "08"
  | "09"
  | "10"
  | "11"
  | "12"
  | "13"
  | "14"
  | "15"
  | "16"
  | "17"
  | "18"
  | "19"
  | "20"
  | "21"
  | "22"
  | "23"
  | "24"
  | "25"
  | "26"
  | "27"
  | "28"
  | "29"
  | "30"
  | "31"
  | "32"
  | "33"
  | "34"
  | "35"
  | "36"
  | "37"
  | "38"
  | "39"
  | "40"
  | "41"
  | "42"
  | "43"
  | "44"
  | "45"
  | "46"
  | "47"
  | "48"
  | "49"
  | "50"
  | "51"
  | "52"
  | "53"
  | "54"
  | "55"
  | "56"
  | "57"
  | "58"
  | "59";
// type SS = '00'|'01'|'02'|'03'|'04'|'05'|'06'|'07'|'08'|'09'|'10'|'11'|'12'|'13'|'14'|'15'|'16'|'17'|'18'|'19'|'20'|'21'|'22'|'23'|'24'|'25'|'26'|'27'|'28'|'29'|'30'|'31'|'32'|'33'|'34'|'35'|'36'|'37'|'38'|'39'|'40'|'41'|'42'|'43'|'44'|'45'|'46'|'47'|'48'|'49'|'50'|'51'|'52'|'53'|'54'|'55'|'56'|'57'|'58'|'59'

export type Time = `${HH}:${MM}`;

export type BufferTimeType = {
  beforeEvent?: number;
  afterEvent?: number;
};

export type EventType = {
  __typename?: "Event";
  id: string;
  userId: string;
  title?: string;
  startDate: string;
  endDate: string;
  allDay?: boolean;
  recurrenceRule?: RecurrenceRuleType;
  location?: LocationType;
  notes?: string;
  attachments?: AttachmentType[];
  links?: LinkType[];
  // alarms?: alarms,
  timezone?: string;
  createdDate: string;
  deleted: boolean;
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
  conferenceId?: string;
  maxAttendees?: number;
  sendUpdates?: SendUpdatesType;
  anyoneCanAddSelf: boolean;
  guestsCanInviteOthers: boolean;
  guestsCanSeeOtherGuests: boolean;
  originalStartDate: string;
  originalAllDay: boolean;
  status?: string;
  summary?: string;
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  recurringEventId?: string;
  updatedAt: string;
  iCalUID?: string;
  htmlLink?: string;
  colorId?: string;
  creator?: CreatorType;
  organizer?: OrganizerType;
  endTimeUnspecified?: boolean;
  recurrence?: string[];
  originalTimezone?: string;
  attendeesOmitted?: boolean;
  extendedProperties?: ExtendedPropertiesType;
  hangoutLink?: string;
  guestsCanModify?: boolean;
  locked?: boolean;
  source?: SourceType;
  eventType?: string;
  privateCopy?: boolean;
  calendarId: string;
  backgroundColor?: string;
  foregroundColor?: string;
  useDefaultAlarms?: boolean;
  positiveImpactScore?: number;
  negativeImpactScore?: number;
  positiveImpactDayOfWeek?: number;
  positiveImpactTime?: Time;
  negativeImpactDayOfWeek?: number;
  negativeImpactTime?: Time;
  preferredDayOfWeek?: number;
  preferredTime?: Time;
  isExternalMeeting?: boolean;
  isExternalMeetingModifiable?: boolean;
  isMeetingModifiable?: boolean;
  isMeeting?: boolean;
  dailyTaskList?: boolean;
  weeklyTaskList?: boolean;
  isBreak?: boolean;
  preferredStartTimeRange?: Time;
  preferredEndTimeRange?: Time;
  copyAvailability?: boolean;
  copyTimeBlocking?: boolean;
  copyTimePreference?: boolean;
  copyReminders?: boolean;
  copyPriorityLevel?: boolean;
  copyModifiable?: boolean;
  copyCategories?: boolean;
  copyIsBreak?: boolean;
  timeBlocking?: BufferTimeType;
  userModifiedAvailability?: boolean;
  userModifiedTimeBlocking?: boolean;
  userModifiedTimePreference?: boolean;
  userModifiedReminders?: boolean;
  userModifiedPriorityLevel?: boolean;
  userModifiedCategories?: boolean;
  userModifiedModifiable?: boolean;
  userModifiedIsBreak?: boolean;
  hardDeadline?: string;
  softDeadline?: string;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  userModifiedIsMeeting?: boolean;
  userModifiedIsExternalMeeting?: boolean;
  duration?: number;
  copyDuration?: boolean;
  userModifiedDuration?: boolean;
  method?: "create" | "update";
  unlink?: boolean;
  copyColor?: boolean;
  userModifiedColor?: boolean;
  byWeekDay?: string[];
  localSynced?: boolean;
  eventId: string;
  meetingId?: string;
};
