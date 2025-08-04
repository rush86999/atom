import DayOfWeekType from './DayOfWeekType';
import { Time } from './EventType';
type TimePreferenceType = {
    dayOfWeek: DayOfWeekType[];
    timeRange: {
        startTime: Time;
        endTime: Time;
    };
};
export default TimePreferenceType;
