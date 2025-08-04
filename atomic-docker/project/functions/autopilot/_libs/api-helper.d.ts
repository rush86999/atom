import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType, UserPreferenceType, AutopilotApiResponse } from './types';
export declare const triggerFeaturesApplyUrl: (body: ScheduleAssistWithMeetingQueueBodyType) => Promise<AutopilotApiResponse<{
    success: boolean;
    details?: any;
}>>;
export declare const triggerScheduleAssistUrl: (body: ScheduleAssistWithMeetingQueueBodyType) => Promise<AutopilotApiResponse<{
    success: boolean;
    details?: any;
}>>;
export declare const getUserPreferences: (userId: string) => Promise<AutopilotApiResponse<UserPreferenceType | null>>;
export declare const createDailyFeaturesApplyEventTrigger: (autopilot: AutopilotType, body: ScheduleAssistWithMeetingQueueBodyType) => Promise<AutopilotApiResponse<string | null>>;
export declare const upsertAutopilotOne: (autopilot: AutopilotType) => Promise<AutopilotApiResponse<AutopilotType | null>>;
export declare const createInitialFeaturesApplyToEventTrigger: (oldAutopilot: AutopilotType, oldBody: ScheduleAssistWithMeetingQueueBodyType) => Promise<AutopilotApiResponse<void>>;
export declare const listAutopilotsGivenUserId: (userId: string) => Promise<AutopilotApiResponse<AutopilotType | null>>;
export declare const deleteAutopilotGivenId: (id: string) => Promise<AutopilotApiResponse<AutopilotType | null>>;
export declare const onScheduleDailyFeaturesApply7DayWindowToEventTrigger: (oldAutopilot: AutopilotType, oldBody: ScheduleAssistWithMeetingQueueBodyType) => Promise<AutopilotApiResponse<void>>;
export declare const upsertAutopilotMany: (autopilots: AutopilotType[]) => Promise<AutopilotApiResponse<AutopilotType[] | null>>;
export declare const getAutopilotGivenId: (id: string) => Promise<AutopilotApiResponse<AutopilotType | null>>;
export declare const deleteScheduledEventForAutopilot: (eventId: string) => Promise<AutopilotApiResponse<{
    success: boolean;
}>>;
