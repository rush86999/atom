import { Agenda, Job } from 'agenda';
export interface ScheduledAgentTaskData {
    originalUserIntent: string;
    entities: Record<string, any>;
    userId: string;
    conversationId?: string;
}
export interface SendTaskReminderData {
    userId: string;
    taskId: string;
    taskDescription: string;
}
export declare const agenda: Agenda;
export declare function defineJob<T>(name: string, handler: (job: Job<T>) => Promise<void>): void;
export declare function startAgenda(): Promise<void>;
export declare function stopAgenda(): Promise<void>;
