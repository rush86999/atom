import { EventType } from '@lib/dataTypes/EventType';

export type DefaultTimeBlockingType = {
  beforeEvent: number;
  afterEvent: number;
};

export type DefaultRemindersType = number[];

type HH =
  | '00'
  | '01'
  | '02'
  | '03'
  | '04'
  | '05'
  | '06'
  | '07'
  | '08'
  | '09'
  | '10'
  | '11'
  | '12'
  | '13'
  | '14'
  | '15'
  | '16'
  | '17'
  | '18'
  | '19'
  | '20'
  | '21'
  | '22'
  | '23';
type MM =
  | '00'
  | '01'
  | '02'
  | '03'
  | '04'
  | '05'
  | '06'
  | '07'
  | '08'
  | '09'
  | '10'
  | '11'
  | '12'
  | '13'
  | '14'
  | '15'
  | '16'
  | '17'
  | '18'
  | '19'
  | '20'
  | '21'
  | '22'
  | '23'
  | '24'
  | '25'
  | '26'
  | '27'
  | '28'
  | '29'
  | '30'
  | '31'
  | '32'
  | '33'
  | '34'
  | '35'
  | '36'
  | '37'
  | '38'
  | '39'
  | '40'
  | '41'
  | '42'
  | '43'
  | '44'
  | '45'
  | '46'
  | '47'
  | '48'
  | '49'
  | '50'
  | '51'
  | '52'
  | '53'
  | '54'
  | '55'
  | '56'
  | '57'
  | '58'
  | '59';
// type SS = '00'|'01'|'02'|'03'|'04'|'05'|'06'|'07'|'08'|'09'|'10'|'11'|'12'|'13'|'14'|'15'|'16'|'17'|'18'|'19'|'20'|'21'|'22'|'23'|'24'|'25'|'26'|'27'|'28'|'29'|'30'|'31'|'32'|'33'|'34'|'35'|'36'|'37'|'38'|'39'|'40'|'41'|'42'|'43'|'44'|'45'|'46'|'47'|'48'|'49'|'50'|'51'|'52'|'53'|'54'|'55'|'56'|'57'|'58'|'59'

export type Time = `${HH}:${MM}`;

export type DefaultTimePreferenceType = {
  dayOfWeek?: -1 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
  startTime: Time;
  endTime: Time;
};

export type DefaultTimePreferenceTypes = DefaultTimePreferenceType[];

export type CategoryType = {
  id: string;
  userId: string;
  name: string;
  updatedAt: string;
  createdDate: string;
  deleted: boolean;
  copyAvailability?: boolean;
  copyTimeBlocking?: boolean;
  copyTimePreference?: boolean;
  copyReminders?: boolean;
  copyPriorityLevel?: boolean;
  copyModifiable?: boolean;
  defaultAvailability?: boolean;
  defaultTimeBlocking?: DefaultTimeBlockingType;
  defaultTimePreference?: DefaultTimePreferenceTypes;
  defaultReminders?: DefaultRemindersType;
  defaultPriorityLevel?: number;
  defaultModifiable?: boolean;
  copyIsBreak?: boolean;
  defaultIsBreak?: boolean;
  color?: string;
  copyIsMeeting?: boolean;
  copyIsExternalMeeting?: boolean;
  defaultIsMeeting?: boolean;
  defaultIsExternalMeeting?: boolean;
  defaultMeetingModifiable?: boolean;
  defaultExternalMeetingModifiable?: boolean;
};
