import TimePreferenceType from '../../../types/TimePreferenceType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences

type MethodType = 'edit-add-time-preferences';

export type EditAddPreferredTimeToPreferredTimesType = {
  userId: string;
  timezone: string;
  title?: string;
  timePreferences: TimePreferenceType[];
  method: MethodType;
  startDate?: string;
  endDate?: string;
};
