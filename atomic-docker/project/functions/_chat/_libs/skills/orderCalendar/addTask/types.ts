import { BufferTimeNumberType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';
import ByMonthDayType from '@chat/_libs/types/ByMonthDayType';
import {
  EventType,
  TransparencyType,
  VisibilityType,
} from '@chat/_libs/types/EventType';

import {
  DeadlineType,
  MutateCalendarExtractedJSONTaskType,
} from '@chat/_libs/types/UserInputToJSONType';
import { TaskType } from '@chat/_libs/types/TaskType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property

type MethodType = 'create-event-forward';

export type AddTaskType = {
  userId: string;
  timezone: string;
  title: string;
  method: MethodType;
  duration?: number;
  description?: string;
  startDate?: string;
  dueDate?: string;
  bufferTime?: BufferTimeNumberType;
  reminders?: number[];
  priority?: number;
  timePreferences?: TimePreferenceType[];
  location?: string;
  transparency?: TransparencyType;
  visibility?: VisibilityType;
  isBreak?: boolean;
  allDay: boolean;
  deadlineType?: DeadlineType;
  taskList?: MutateCalendarExtractedJSONTaskType[];
  recur?: {
    frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
    endDate?: string;
    occurrence?: number;
    interval: number;
    byWeekDay?: DayOfWeekType[];
    byMonthDay?: ByMonthDayType[];
  };
};

export type TaskAndEventType = {
  task: TaskType;
  event: EventType;
};
