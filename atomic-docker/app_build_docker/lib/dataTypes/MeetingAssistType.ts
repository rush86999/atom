import { RecurrenceFrequencyType } from '@lib/Calendar/types';
import { LocationType } from './EventType';

export type BufferTimeNumberType = {
  beforeEvent: number;
  afterEvent: number;
};

export type ConferenceAppType = 'zoom' | 'google';

export type MeetingAssistType = {
  id: string;
  eventId?: string;
  userId: string;
  summary?: string;
  notes?: string;
  windowStartDate: string;
  windowEndDate: string;
  timezone?: string;
  location?: LocationType;
  priority: number;
  enableConference: boolean;
  conferenceApp?: ConferenceAppType | null;
  sendUpdates?: 'all' | 'externalOnly' | 'none';
  guestsCanInviteOthers: boolean;
  transparency?: 'opaque' | 'transparent';
  visibility?: 'default' | 'public' | 'private';
  createdDate: string;
  updatedAt: string;
  colorId?: string;
  backgroundColor?: string;
  foregroundColor?: string;
  useDefaultAlarms?: boolean;
  reminders?: number[];
  cancelIfAnyRefuse?: boolean;
  enableHostPreferences?: boolean;
  enableAttendeePreferences?: boolean;
  attendeeCanModify?: boolean;
  startDate?: string;
  endDate?: string;
  attendeeCount?: number;
  expireDate?: string;
  attendeeRespondedCount: number;
  cancelled: boolean;
  duration: number;
  calendarId: string;
  bufferTime?: BufferTimeNumberType;
  anyoneCanAddSelf: boolean;
  guestsCanSeeOtherGuests: boolean;
  minThresholdCount?: number;
  allowAttendeeUpdatePreferences?: boolean;
  guaranteeAvailability?: boolean;
  frequency?: RecurrenceFrequencyType;
  interval?: number;
  until?: string; // no timezone
  originalMeetingId?: string;
  lockAfter?: boolean;
};
