import { PrepareForMeetingResponse } from '../../types';
export declare function handlePrepareForMeeting(userId: string, meetingIdentifier?: string, meetingDateTime?: string): Promise<PrepareForMeetingResponse>;
interface DateRange {
    startDate: Date;
    endDate: Date;
    nextPeriodStartDate: Date;
    nextPeriodEndDate: Date;
    displayRange: string;
}
/**
 * Determines the date ranges for the current/past week and the upcoming week.
 * @param timePeriod Optional string like "this week" or "last week". Defaults to "this week".
 * @returns Object containing startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, and displayRange.
 */
export declare function determineDateRange(timePeriod?: 'this week' | 'last week' | string): DateRange;
import { GenerateWeeklyDigestResponse } from '../../types';
export declare function handleGenerateWeeklyDigest(userId: string, timePeriodInput?: 'this week' | 'last week' | string): Promise<GenerateWeeklyDigestResponse>;
import { SuggestFollowUpsResponse } from '../../types';
export declare function handleSuggestFollowUps(userId: string, contextIdentifier: string, contextType?: 'meeting' | 'project' | string): Promise<SuggestFollowUpsResponse>;
export {};
