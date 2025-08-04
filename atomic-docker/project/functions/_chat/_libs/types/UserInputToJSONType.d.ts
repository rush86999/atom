import { TransparencyType, VisibilityType } from './EventType';
import { RecurrenceFrequencyType } from '@libs/types/EventType';
export type MutatedCalendarExtractedJSONAttendeeType = {
    name: string;
    email?: string;
    isHost?: boolean;
};
export type MutateCalendarExtractedJSONTaskType = {
    task: string;
    duration?: number;
    status: 'todo' | 'doing' | 'done';
    tasklistName?: string;
};
export type AppType = 'zoom' | 'google';
export type DeadlineType = 'hardDeadline' | 'softDeadline';
type UserInputToJSONType = {
    action: string;
    params: {
        attendees: MutatedCalendarExtractedJSONAttendeeType[];
        description: string;
        taskList: MutateCalendarExtractedJSONTaskType[];
        summary: string;
        title: string;
        oldTitle: string;
        notes: string;
        priority: number;
        project: string;
        location: string;
        alarms: number[];
        reminderMessage: string;
        attachments: string[];
        isFollowUp: boolean;
        conference: {
            app: AppType;
        };
        transparency: TransparencyType;
        visibility: VisibilityType;
        isBreak: boolean;
        bufferTime: {
            beforeEvent: number;
            afterEvent: number;
        };
        deadlineType: DeadlineType;
        startTime: string;
        endTime: string;
        recurrence: {
            frequency: RecurrenceFrequencyType;
            interval: number;
            endDate: string;
        };
    };
};
export default UserInputToJSONType;
