import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
import { Time } from '@chat/_libs/types/EventType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';
import ByMonthDayType from '@chat/_libs/types/ByMonthDayType';

type MethodType =
  | 'create-event-forward'
  | 'create-event-backward'
  | 'create-deadline-forward'
  | 'move-deadline-forward'
  | 'move-deadline-backward'
  | 'move-event-forward'
  | 'move-event-backward'
  | 'increase-duration'
  | 'decrease-duration'
  | 'create-time-preferences'
  | 'remove-time-preferences'
  | 'edit-add-time-preferences'
  | 'edit-remove-time-preferences | edit-event-property | ask-calendar-question | remove-event | find-time | invite';

/**
 * relativeTimeChangeFromNow: [add | subtract],
      relativeTimeFromNow: [{
        unit: [minute | hour | week | month | year],
        value: [NUMBER]
      }],
 */

export type RelativeTimeChangeFromNowType = 'add' | 'subtract';

export type RelativeTimeFromNowType = {
  unit: 'minute' | 'hour' | 'day' | 'week' | 'month' | 'year';
  value: number;
};

type ExtractedDateType = {
  relativeTimeChangeFromNow: RelativeTimeChangeFromNowType;
  relativeTimeFromNow: RelativeTimeFromNowType[];
  year: string;
  month: string;
  day: string;
  isoWeekday: number;
  hour: number;
  minute: number;
  duration: number;
  startTime: Time;
  endTime: Time;
};

type DateTimeJSONType = {
  relativeTimeChangeFromNow: RelativeTimeChangeFromNowType;
  relativeTimeFromNow: RelativeTimeFromNowType[];
  year: string;
  month: string;
  day: string;
  isoWeekday: number;
  hour: number;
  minute: number;
  duration: number;
  startTime: Time;
  endTime: Time;
  method: MethodType[];
  oldDate: ExtractedDateType;
  dueDate: ExtractedDateType;
  findTimeWindowStart: ExtractedDateType;
  findTimeWindowEnd: ExtractedDateType;
  recur: {
    frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
    endDate?: {
      relativeTimeChangeFromNow: RelativeTimeChangeFromNowType;
      relativeTimeFromNow: RelativeTimeFromNowType[];
      year: string;
      month: string;
      day: string;
      isoWeekday: number;
      hour: number;
      minute: number;
      duration: number;
      startTime: Time;
      endTime: Time;
    };
    occurrence?: number;
    interval: number;
    byWeekDay?: DayOfWeekType[];
    byMonthDay?: ByMonthDayType[];
  };
  timePreferences: TimePreferenceType[];
  allDay: boolean;
};

export default DateTimeJSONType;
