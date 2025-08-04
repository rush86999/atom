import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import { DeleteEventType } from './types';
import OpenAI from 'openai';
import { SkillMessageHistoryType } from '@chat/_libs/types/Messaging/MessagingTypes';
export declare const finalStepDeleteEvent: (body: DeleteEventType, startDate: string, endDate: string, response: any) => Promise<any>;
export declare const processDeleteEventPending: (userId: string, timezone: string, jsonBody: UserInputToJSONType, dateJSONBody: DateTimeJSONType, currentTime: string) => Promise<any>;
export declare const processDeleteEventMissingFieldsReturned: (userId: string, timezone: string, jsonBody: UserInputToJSONType, dateJSONBody: DateTimeJSONType, currentTime: string, messageHistoryObject: SkillMessageHistoryType) => Promise<any>;
export declare const deleteEventControlCenter: (openai: OpenAI, userId: string, timezone: string, messageHistoryObject: SkillMessageHistoryType, userCurrentTime: string, query: "missing_fields" | "completed" | "event_not_found" | "pending") => Promise<any>;
