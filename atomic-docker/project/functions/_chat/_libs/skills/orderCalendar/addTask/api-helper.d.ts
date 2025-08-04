import { TaskType } from '@chat/_libs/types/TaskType';
import { TaskStatus } from './constants';
import { EventType, RecurrenceFrequencyType } from '@chat/_libs/types/EventType';
import { RecurrenceRuleType, TransparencyType, VisibilityType } from '@chat/_libs/types/EventType';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import { AddTaskType } from './types';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import OpenAI from 'openai';
import { SkillMessageHistoryType } from '@chat/_libs/types/Messaging/MessagingTypes';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
export declare const createDeadlineEventForTaskList: (generatedId: string, userId: string, title: string, duration: number, taskId: string, taskListName: string, priority: number, timezone: string, startDate: string, softDeadline?: string, hardDeadline?: string, allDay?: boolean, reminders?: number[], recurObject?: RecurrenceRuleType, transparency?: TransparencyType, visibility?: VisibilityType, location?: string) => Promise<EventType>;
export declare const insertTaskInDb: (task: TaskType) => Promise<any>;
export declare const createTaskAndEvent: (userId: string, taskListName: string | undefined, text: string, timezone: string, startDate?: string, important?: boolean, softDeadline?: string, hardDeadline?: string, status?: TaskStatus, eventId?: string, duration?: number, priority?: number, allDay?: boolean, reminders?: number[], recurObject?: RecurrenceRuleType, transparency?: TransparencyType, visibility?: VisibilityType, location?: string) => Promise<{
    task: TaskType;
    event: EventType;
} | undefined>;
export declare const createTask: (userId: string, taskListName: string | undefined, text: string, important?: boolean, softDeadline?: string, hardDeadline?: string, status?: TaskStatus, eventId?: string, duration?: number, priority?: number) => Promise<any>;
export declare const createEventForTask: (userId: string, taskListName: string | undefined, taskId: string, text: string, timezone: string, startDate?: string, softDeadline?: string, hardDeadline?: string, eventId?: string, duration?: number, priority?: number, allDay?: boolean, reminders?: number[], recurObject?: RecurrenceRuleType, transparency?: TransparencyType, visibility?: VisibilityType, location?: string) => Promise<any>;
export declare const getTaskStatus: (status: "todo" | "doing" | "done") => any;
export declare const getRruleFreq: (freq: RecurrenceFrequencyType) => any;
type DayTimeWindowType = {
    dayWindowStartDate: string;
    dayWindowEndDate: string;
};
export declare const getDayjsUnitFromFrequency: (frequency: RecurrenceFrequencyType) => "y" | "m" | "d" | "w";
export declare enum Day {
    MO = "MO",
    TU = "TU",
    WE = "WE",
    TH = "TH",
    FR = "FR",
    SA = "SA",
    SU = "SU"
}
export declare const generateDatesUsingRrule: (startTime: string, frequency: RecurrenceFrequencyType, interval: number, until: string, timezone: string, userId: string, byWeekDay?: DayOfWeekType[], byMonthDay?: number[]) => Promise<DayTimeWindowType[] | undefined>;
export declare const finalStepAddTask: (body: AddTaskType, timezone: string, userCurrentTime: string, response: any) => Promise<any>;
export declare const processAddTaskPending: (userId: string, timezone: string, jsonBody: UserInputToJSONType, dateJSONBody: DateTimeJSONType, currentTime: string) => Promise<ResponseActionType>;
export declare const processAddTaskMissingFieldsReturned: (userId: string, timezone: string, jsonBody: UserInputToJSONType, dateJSONBody: DateTimeJSONType, currentTime: string, messageHistoryObject: SkillMessageHistoryType) => Promise<ResponseActionType>;
export declare const addTaskControlCenter: (openai: OpenAI, userId: string, timezone: string, messageHistoryObject: SkillMessageHistoryType, userCurrentTime: string, query: "missing_fields" | "completed" | "event_not_found" | "pending") => Promise<any>;
export {};
