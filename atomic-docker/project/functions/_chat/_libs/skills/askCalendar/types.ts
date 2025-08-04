export type MonthType = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11;
// 1 - 31
export type DayType =
  | 1
  | 2
  | 3
  | 4
  | 5
  | 6
  | 7
  | 8
  | 9
  | 10
  | 11
  | 12
  | 13
  | 14
  | 15
  | 16
  | 17
  | 18
  | 19
  | 20
  | 21
  | 22
  | 23
  | 24
  | 25
  | 26
  | 27
  | 28
  | 29
  | 30
  | 31;

export type DD =
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
  | '31';

export type mm =
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

export type HH =
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

export type h =
  | '1'
  | '2'
  | '3'
  | '4'
  | '5'
  | '6'
  | '7'
  | '8'
  | '9'
  | '10'
  | '11'
  | '12';

export type a = 'am' | 'pm';

export type Time = `${HH}:${mm}`;

export type time = `${h}:${mm} ${a}`;

export type MonthDayType = `--${mm}-${DD}`;

export type DayOfWeekType =
  | 'MONDAY'
  | 'TUESDAY'
  | 'WEDNESDAY'
  | 'THURSDAY'
  | 'FRIDAY'
  | 'SATURDAY'
  | 'SUNDAY';

export type UserTimeSlotType = {
  dayOfWeek: DayOfWeekType;
  startTime: Time;
  endTime: Time;
};

export type UserWorkTimeType = {
  dayOfWeek: DayOfWeekType;
  startTime: time;
  endTime: time;
};

export type DataAttributesType =
  | 'count'
  | 'all'
  | 'none'
  | 'id'
  | 'userId'
  | 'title'
  | 'startDate'
  | 'endDate'
  | 'allDay'
  | 'recurrenceRule'
  | 'location'
  | 'notes'
  | 'timezone'
  | 'taskId'
  | 'priority'
  | 'isFollowUp'
  | 'isPreEvent'
  | 'isPostEvent'
  | 'modifiable'
  | 'conferenceId'
  | 'recurringEventId'
  | 'organizer'
  | 'dailyTaskList'
  | 'weeklyTaskList'
  | 'isBreak'
  | 'bufferTime'
  | 'hardDeadline'
  | 'softDeadline'
  | 'duration'
  | 'conference-name'
  | 'conference-notes'
  | 'conference-joinUrl'
  | 'conference-startUrl'
  | 'task'
  | 'task-listName'
  | 'task-status';

// To find what attributes are needed
export type QueryCalendarExtractedAttributesType = {
  attributes: DataAttributesType[];
  isMeeting: boolean;
};

// availability, single event, many events, single meeting, many meetings, next single event, next single meeting.
export type CategoriesForUserIntentType =
  | 'availability'
  | 'single event'
  | 'many events'
  | 'next single event';
