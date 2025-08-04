import {
  AppType,
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import {
  SendUpdatesType,
  TransparencyType,
  VisibilityType,
} from '@chat/_libs/types/EventType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property | find-time

type MethodType = 'invite';

export type SendMeetingInviteType = {
  userId: string;
  timezone: string;
  title: string;
  attendees: MutatedCalendarExtractedJSONAttendeeType[];
  method: MethodType;
  duration?: number;
  description?: string;
  conferenceApp?: AppType;
  reminders?: number[];
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  windowStartDate: string;
  windowEndDate: string;
  receiverTimezone: string;
};

export type ReceiverTimezoneFormDataResponseType = {
  type: 'select';
  value: string;
  name: string;
};

export type AttendeeDetailsType = {
  email: string;
  name: string;
  link: string;
};

export type MeetingUrlQueryParamsAttachmentType = {
  title: string;
  fileUrl: string;
};

// sequence is important for regex pattern matching
export type MeetingUrlQueryParamsType = {
  userId: string;
  timezone: string; // recipient timezone
  enableConference: 'true' | 'false';
  conferenceApp?: AppType;
  useDefaultAlarms?: 'true' | 'false';
  reminders?: string[]; // numbers[]
  attendeeEmails: string[];
  duration: string; // number
  calendarId: string;
  startTime: string; // iso8601 format
  name: string;
  primaryEmail: string;
  sendUpdates?: SendUpdatesType;
  anyoneCanAddSelf: 'true' | 'false';
  guestsCanInviteOthers: 'true' | 'false';
  guestsCanModify?: 'true' | 'false';
  guestsCanSeeOtherGuests: 'true' | 'false';
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  attachments?: MeetingUrlQueryParamsAttachmentType[];
};

export type AttendeeDetailsForBulkMeetingInviteType = {
  email: string;
  name: string;
  link: string;
};

export type AttendeeDetailsForBulkMeetingCancelledType = {
  email: string;
  name: string;
};

export type RecurrenceFrequencyType = 'daily' | 'weekly' | 'monthly' | 'yearly';

export type MeetingInviteDetailsToHostType = {
  attendees: AttendeeDetailsType[];
  hostEmail: string;
  hostName: string;
  title: string;
  notes: string;
  windowStartDate: string;
  windowEndDate: string;
  timezone: string;
};
