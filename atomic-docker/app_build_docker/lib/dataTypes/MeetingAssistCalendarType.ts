type DefaultReminderType = {
  method: string;
  minutes: number;
};

export type MeetingAssistCalendarType = {
  id: string;
  attendeeId: string;
  title?: string;
  backgroundColor?: string;
  account?: object;
  accessLevel?: string;
  modifiable: boolean;
  defaultReminders?: DefaultReminderType[];
  resource?: string;
  primary: boolean;
  colorId?: string;
  foregroundColor?: string;
};
