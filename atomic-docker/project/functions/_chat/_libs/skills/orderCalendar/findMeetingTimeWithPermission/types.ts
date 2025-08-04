import { BufferTimeNumberType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
import {
  AppType,
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';

import { TransparencyType } from '@chat/_libs/types/EventType';
import { VisibilityType } from 'aws-sdk/clients/appstream';
import ByMonthDayType from '@chat/_libs/types/ByMonthDayType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property | find-time

type MethodType = 'find-time';

export type FindMeetingTimeWithPermissionType = {
  userId: string;
  timezone: string;
  title: string;
  attendees: MutatedCalendarExtractedJSONAttendeeType[];
  method: MethodType;
  duration?: number;
  description?: string;
  conferenceApp?: AppType;
  windowStartDate: string;
  windowEndDate: string;
  bufferTime?: BufferTimeNumberType;
  reminders?: number[];
  priority?: number;
  timePreferences?: TimePreferenceType[];
  location?: string;
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  recur?: {
    frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
    endDate?: string;
    occurrence?: number;
    interval: number;
    byWeekDay?: DayOfWeekType[];
    ByMonthDay?: ByMonthDayType[];
  };
};

export type AttendeeDetailsType = {
  email: string;
  name: string;
  link: string;
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
