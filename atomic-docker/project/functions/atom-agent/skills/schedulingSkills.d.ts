export interface ScheduleTaskParams {
    taskDescription?: string;
    when: string | Date;
    originalUserIntent: string;
    entities: Record<string, any>;
    userId: string;
    conversationId?: string;
    isRecurring?: boolean;
    repeatInterval?: string;
    repeatTimezone?: string;
}
/**
 * Schedules a task (agent action) to be executed at a specified time or interval using Agenda.
 *
 * @param params - The parameters for scheduling the task.
 * @returns A promise that resolves to a string message indicating success or failure.
 */
export declare function scheduleTask(params: ScheduleTaskParams): Promise<string>;
export interface CancelTaskParams {
    jobId?: string;
    jobName?: string;
    userId?: string;
    originalUserIntent?: string;
}
export declare function cancelTask(params: CancelTaskParams): Promise<string>;
import { UserAvailability, SkillResponse, NLUCreateTimePreferenceRuleEntities, NLUBlockTimeSlotEntities, NLUScheduleTeamMeetingEntities, SchedulingResponse } from '../types';
export declare function getUsersAvailability(userIds: string[], windowStart: string, windowEnd: string): Promise<SkillResponse<UserAvailability[]>>;
export declare function handleScheduleSkillActivation(userId: string, entities: any): Promise<string>;
export declare function createSchedulingRule(userId: string, ruleDetails: NLUCreateTimePreferenceRuleEntities): Promise<SchedulingResponse>;
export declare function blockCalendarTime(userId: string, blockDetails: NLUBlockTimeSlotEntities): Promise<SchedulingResponse>;
export declare function initiateTeamMeetingScheduling(userId: string, meetingDetails: NLUScheduleTeamMeetingEntities): Promise<SchedulingResponse>;
