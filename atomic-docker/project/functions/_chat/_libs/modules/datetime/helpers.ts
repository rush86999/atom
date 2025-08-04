// DateTime Helper Module - comprehensive date/time utilities for calendar operations
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { v4 as uuid } from 'uuid';
import { RecurrenceFrequencyType } from '../../types/EventType';

// Extend dayjs
dayjs.extend(utc);
dayjs.extend(timezone);

// Logger for datetime operations
const datetimeLogger = {
  info: console.log.bind(console, '[DateTimeHelpers] INFO:'),
  error: console.error.bind(console, '[DateTimeHelpers] ERROR:'),
  warn: console.warn.bind(console, '[DateTimeHelpers] WARN:'),
};

// Utility types
export interface DateRangeType {
  start: string;
  end: string;
}

export interface RRuleType {
  freq: RecurrenceFrequencyType;
  interval: number;
  until?: string;
  count?: number;
  byweekday?: string[];
  bymonthday?: number[];
}

export interface ExtrapolatedDateType {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  timezone: string;
  isValid: boolean;
}

// Event search boundary calculation
export const eventSearchBoundary = async (
  startDate: string,
  duration: number = 1,
  timezone: string = 'UTC'
): Promise<{ start: string; end: string }> => {
  try {
    const start = dayjs.tz(startDate, timezone).startOf('day');
    const end = start.add(duration, 'day').endOf('day');

    return {
      start: start.toISOString(),
      end: end.toISOString()
    };
  } catch (error) {
    datetimeLogger.error('Error calculating search boundary:', error);
    return {
      start: dayjs().startOf('day').toISOString(),
      end: dayjs().add(1, 'day').endOf('day').toISOString()
    };
  }
};

// Extrapolate date from JSON data
export const extrapolateDateFromJSONData = async (
  jsonData: any,
  userTimezone: string = 'UTC'
): Promise<ExtrapolatedDateType> => {
  try {
    const now = dayjs().tz(userTimezone);
    let targetDate = now;

    // Handle relative dates
    if (jsonData.relative) {
      switch (jsonData.relative) {
        case 'today':
          targetDate = now;
          break;
        case 'tomorrow':
          targetDate = now.add(1, 'day');
          break;
        case 'yesterday':
          targetDate = now.subtract(1, 'day');
          break;
        case 'next_week':
          targetDate = now.add(1, 'week');
          break;
        case 'this_week':
          targetDate = now.endOf('week');
          break;
      }
    }

    // Handle specific dates
    if (jsonData.year && jsonData.month && jsonData.day) {
      targetDate = dayjs.tz(`${jsonData.year}-${jsonData.month}-${jsonData.day}`, userTimezone)
        .hour(jsonData.hour || 9)
        .minute(jsonData.minute || 0);
    }

    // Handle durations
    if (jsonData.daysFromNow !== undefined) {
      targetDate = now.add(jsonData.daysFromNow, 'day');
    }

    return {
      year: targetDate.year(),
      month: targetDate.month() + 1,
      day: targetDate.date(),
      hour: targetDate.hour(),
      minute: targetDate.minute(),
      timezone: userTimezone,
      isValid: true
    };
  } catch (error) {
    datetimeLogger.error('Error extrapolating date from JSON:', error);
    return {
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      day: new Date().getDate(),
      hour: 9,
      minute: 0,
      timezone: userTimezone,
      isValid: false
    };
  }
};

// Extrapolate start date specifically
export const extrapolateStartDateFromJSONData = async (
  jsonData: any,
  userTimezone: string = 'UTC'
): Promise<string> => {
  try {
    const extracted = await extrapolateDateFromJSONData(jsonData, userTimezone);
    const date = dayjs.tz({
      year: extracted.year,
      month: extracted.month - 1,
      day: extracted.day,
      hour: extracted.hour,
      minute: extracted.minute
    }, extracted.timezone);

    return date.toISOString();
  } catch (error) {
    datetimeLogger.error('Error extrapolating start date:', error);
    return dayjs().add(1, 'day').toISOString();
  }
};

// Extrapolate end date based on duration
export const extrapolateEndDateFromJSONData = async (
  jsonData: any,
  startDate: string,
  userTimezone: string = 'UTC'
): Promise<string> => {
  try {
    let duration = 60; // Default 60 minutes
    if (jsonData.duration) {
      duration = jsonData.duration;
    } else if (jsonData.endHour && jsonData.endMinute) {
      const start = dayjs(startDate);
      const end = dayjs.tz({
        year: start.year(),
        month: start.month(),
        day: start.date(),
        hour: jsonData.endHour,
        minute: jsonData.endMinute
      }, userTimezone);
      return end.toISOString();
    }

    return dayjs(startDate).add(duration, 'minute').toISOString();
  } catch (error) {
    datetimeLogger.error('Error extrapolating end date:', error);
    return dayjs(startDate).add(1, 'hour').toISOString();
  }
};

// RRule generation
export const createRRuleString = (rruleData: RRuleType): string => {
  try {
    const parts: string[] = ['FREQ=' + rruleData.freq.toUpperCase()];

    if (rruleData.interval > 1) {
      parts.push(`INTERVAL=${rruleData.interval}`);
    }

    if (rruleData.until) {
      parts.push(`UNTIL=${dayjs(rruleData.until).format('YYYYMMDD')}T235959Z`);
    } else if (rruleData.count) {
      parts.push(`COUNT=${rruleData.count}`);
    }

    if (rruleData.byweekday && rruleData.byweekday.length > 0) {
      const weekdayMap: { [key: string]: string } = {
        'sunday': 'SU',
        'monday': 'MO',
        'tuesday': 'TU',
        'wednesday': 'WE',
        'thursday': 'TH',
        'friday': 'FR',
        'saturday': 'SA'
      };
      parts.push(`BYDAY=${rruleData.byweekday.map(w => weekdayMap[w]).join(',')}`);
    }

    if (rruleData.bymonthday) {
      parts.push(`BYMONTHDAY=${rruleData.bymonthday.join(',')}`);
    }

    return `RRULE:${parts.join(';')}`;
  } catch (error) {
    datetimeLogger.error('Error creating RRule string:', error);
    return 'RRULE:FREQ=DAILY;INTERVAL=1';
  }
};

// Get weekday number for RRule
export const getWeekdayNumber = (weekday: string): number => {
  const weekdays: { [key: string]: number } = {
    'sunday': 0, 'monday': 1, 'tuesday': 2, 'wednesday': 3,
    'thursday': 4, 'friday': 5, 'saturday': 6
  };
  return weekdays[weekday.toLowerCase()] || 1;
};

// Parse duration string to minutes
export const parseDurationString = (duration: string): number => {
  try {
    const match = duration.match(/(\d+)(\w+)/);
    if (!match) return 60;

    const [, num, unit] = match;
    const value = parseInt(num, 10);

    switch (unit.toLowerCase()) {
      case 'h': case 'hour': case 'hours': return value * 60;
      case 'd': case 'day': case 'days': return value * 24 * 60;
      case 'w': case 'week': case 'weeks': return value * 7 * 24 * 60;
      case 'm': case 'min': case 'minute': case 'minutes': return value;
      default: return 60;
    }
  } catch (error) {
    datetimeLogger.error('Error parsing duration:', error);
    return 60;
  }
};

// Get business hours for a date
export const getBusinessHours = (
  date: string,
  timezone: string = 'UTC',
  startHour = 9,
  endHour = 17
): DateRangeType => {
  try {
    const day = dayjs.tz(date, timezone)
      .hour(startHour).minute(0).second(0);
    const end = day.hour(endHour).minute(0).second(0);

    return {
      start: day.toISOString(),
      end: end.toISOString()
    };
  } catch (error) {
    datetimeLogger.error('Error getting business hours:', error);
    return {
      start: dayjs().hour(9).toISOString(),
      end: dayjs().hour(17).toISOString()
    };
  }
};

// Check if two date ranges overlap
export const dateRangesOverlap = (
  range1: DateRangeType,
  range2: DateRangeType
): boolean => {
  try {
    const start1 = dayjs(range1.start);
    const end1 = dayjs(range1.end);
    const start2 = dayjs(range2.start);
    const end2 = dayjs(range2.end);

    return start1.isBefore(end2) && end1.isAfter(start2);
  } catch (error) {
    datetimeLogger.error('Error checking date overlap:', error);
    return false;
  }
};

// Get timezone offset
export const getTimezoneOffset = (timezone: string): string => {
  try {
    const offset = dayjs().tz(timezone).format('Z');
    return offset;
  } catch (error) {
    datetimeLogger.error('Error getting timezone offset:', error);
    return '+00:00';
  }
};

// Convert to UTC
export const convertToUTC = (date: string, timezone: string): string => {
  try {
    return dayjs.tz(date, timezone).utc().toISOString();
  } catch (error) {
    datetimeLogger.error('Error converting to UTC:', error);
    return new Date().toISOString();
  }
};

// Find next occurrence after a date
export const findNextOccurrence = async (
  rruleString: string,
  startDate: string,
  timezone: string = 'UTC'
): Promise<string | null> => {
  try {
    // This would need rrule library integration in real implementation
    const nextLoop = dayjs(startDate).add(1, 'day').toISOString();
    return nextLoop;
  } catch (error) {
    datetimeLogger.error('Error finding next occurrence:', error);
    return null;
  }
};

// Validate date string
export const validateDateString = (dateString: string): boolean => {
  try {
    const date = dayjs(dateString);
    return date.isValid();
  } catch (error) {
    datetimeLogger.error('Error validating date string:', error);
    return false;
  }
};

// Export all functions
export default {
  eventSearchBoundary,
  extrapolateDateFromJSONData,
  extrapolateStartDateFromJSONData,
  extrapolateEndDateFromJSONData,
  createRRuleString,
  getWeekdayNumber,
  parseDurationString,
  getBusinessHours,
  dateRangesOverlap,
  getTimezoneOffset,
  convertToUTC,
  findNextOccurrence,
  validateDateString
};
