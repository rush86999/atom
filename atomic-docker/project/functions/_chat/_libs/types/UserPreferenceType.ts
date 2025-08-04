type DayOfWeekIntType = 1 | 2 | 3 | 4 | 5 | 6 | 7;

type StartTimeType = {
  day: DayOfWeekIntType;
  hour: number;
  minutes: number;
};

type EndTimeType = {
  day: DayOfWeekIntType;
  hour: number;
  minutes: number;
};

export type UserPreferenceType = {
  id: string;
  userId: string;
  reminders?: number[]; // invite part
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
  minNumberOfBreaks: number;
  breakLength: number;
  breakColor?: string;
  backToBackMeetings: boolean;
  maxNumberOfMeetings: number;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  copyColor?: boolean;
  updatedAt?: string;
  createdDate?: string;
  deleted: boolean;
};
