import { Time } from '@chat/_libs/types/EventType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences

type MethodType =
  | 'create-time-preferences'
  | 'remove-time-preferences'
  | 'edit-add-time-preferences'
  | 'edit-remove-time-preferences';

export type ResolveConflictingEventsType = {
  userId: string;
  timezone: string;
  title?: string;
  priority?: number;
  timePreferences: TimePreferenceType[];
  method: MethodType;
};
