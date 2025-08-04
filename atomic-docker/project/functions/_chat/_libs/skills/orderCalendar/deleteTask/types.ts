// create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property | remove-event

type MethodType = 'remove-event';

export type DeleteTaskType = {
  userId: string;
  timezone: string;
  title: string;
  method: MethodType;
};

export type SearchBoundaryType = {
  startDate: string;
  endDate: string;
};
