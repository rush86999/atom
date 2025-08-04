import { AutopilotType } from '@lib/dataTypes/AutopilotType';
export type ScheduleAssistWithMeetingQueueBodyType = {
    userId: string;
    windowStartDate: string;
    windowEndDate: string;
    timezone: string;
};
export type AddDailyFeaturesApplyEventTriggerType = {
    autopilot: AutopilotType;
    body: ScheduleAssistWithMeetingQueueBodyType;
};
export type StartDailyAssistEventTriggerType = {
    autopilot: AutopilotType;
    body: ScheduleAssistWithMeetingQueueBodyType;
};
