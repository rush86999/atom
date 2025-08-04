import { Time } from '@chat/_libs/skills/askCalendar/types';
import {
  RelativeTimeChangeFromNowType,
  RelativeTimeFromNowType,
} from '@chat/_libs/datetime/DateTimeJSONJSONType';

type ExtractedDateType = {
  relativeTimeChangeFromNow: RelativeTimeChangeFromNowType;
  relativeTimeFromNow: RelativeTimeFromNowType[];
  year: string;
  month: string;
  day: string;
  hour: number;
  minute: number;
  time: Time;
};
type QueryCalendarExtractedJSONType = {
  start_date: ExtractedDateType;
  end_date: ExtractedDateType;
};

export default QueryCalendarExtractedJSONType;
/**
 * {
    "start_date": {
        "relativeTimeChangeFromNow": "[add | subtract]",
        "relativeTimeFromNow": [{
            "unit": "[minute | hour | day | week | month | year]",
            "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "time": "[24 hour 2-digits]:[minutes] [STRING]"
    },
    "end_date": {
        "relativeTimeChangeFromNow": "[add | subtract]",
        "relativeTimeFromNow": [{
            "unit": "[minute | hour | day | week | month | year]",
            "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "time": "[24 hour 2-digits]:[minutes] [STRING]"
    }
}
 */
