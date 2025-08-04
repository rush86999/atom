type dayOfWeekInt = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type StartTimeType = {
  day: dayOfWeekInt;
  hour: number;
  minutes: number;
};

export type EndTimeType = {
  day: dayOfWeekInt;
  hour: number;
  minutes: number;
};

export type UserPreferenceType = {
  id: string;
  userId: string;
  reminders?: number[];
  followUp?: number[]; // invite part
  isPublicCalendar?: boolean;
  publicCalendarCategories?: string[];
  startTimes?: StartTimeType[];
  endTimes?: EndTimeType[];
  copyAvailability?: boolean;
  copyTimeBlocking?: boolean;
  copyTimePreference?: boolean;
  copyReminders?: boolean;
  copyPriorityLevel?: boolean;
  copyModifiable?: boolean;
  copyCategories?: boolean;
  copyIsBreak?: boolean;
  maxWorkLoadPercent: number;
  backToBackMeetings: boolean;
  maxNumberOfMeetings: number;
  minNumberOfBreaks: number;
  breakLength: number;
  breakColor?: string;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  copyColor?: boolean;
  onBoarded?: boolean;
  updatedAt?: string;
  createdDate?: string;
  deleted: boolean;
};
