import { BufferTimeNumberType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';

import { TransparencyType } from '@chat/_libs/types/EventType';
import { VisibilityType } from 'aws-sdk/clients/appstream';
import ByMonthDayType from '@chat/_libs/types/ByMonthDayType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property

type MethodType = 'create-event-forward';

export type BlockOffTimeType = {
  userId: string;
  timezone: string;
  title: string;
  method: MethodType;
  duration?: number;
  description?: string;
  startDate: string;
  bufferTime?: BufferTimeNumberType;
  reminders?: number[];
  priority?: number;
  timePreferences?: TimePreferenceType[];
  location?: string;
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  isBreak?: boolean;
  recur?: {
    frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
    endDate?: string;
    occurrence?: number;
    interval: number;
    byWeekDay?: DayOfWeekType[];
    ByMonthDay?: ByMonthDayType[];
  };
};
