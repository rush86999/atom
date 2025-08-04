import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';

// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences

type MethodType = 'edit-remove-time-preferences';

export type EditRemovePreferredTimeToPreferredTimesType = {
  userId: string;
  timezone: string;
  title?: string;
  timePreferences: TimePreferenceType[];
  method: MethodType;
};
