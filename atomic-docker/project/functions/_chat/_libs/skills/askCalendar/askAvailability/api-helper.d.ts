import QueryCalendarExtractedJSONType from '@chat/_libs/datetime/QueryCalendarExtractedDateJSONType';
import { NotAvailableSlotType } from './types';
import { UserPreferenceType } from '@chat/_libs/types/UserPreferenceType';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { SkillMessageHistoryType } from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
export declare const generateAvailableSlotsForDateForUser: (slotDuration: number, startDateInUserTimezone: string, userPreferences: UserPreferenceType, timezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[], isFirstDay?: boolean, isLastDay?: boolean, endDateInUserTimezone?: string) => AvailableSlotType[];
export declare const generateAvailableSlotsforTimeWindowForUser: (windowStartDate: string, windowEndDate: string, slotDuration: number, userPreferences: UserPreferenceType, timezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[]) => {
    availableSlots: AvailableSlotType[];
};
export declare const generateAvailabilityForUser: (userId: string, windowStartDate: string, windowEndDate: string, timezone: string, slotDuration: number) => Promise<AvailableSlotType[] | undefined>;
export declare const processAvailability: (userId: string, timezone: string, dateTimeJSONBody: DateTimeJSONType, queryDateJSONBody: QueryCalendarExtractedJSONType, currentTime: string) => Promise<ResponseActionType>;
export declare const askAvailabilityControlCenterForPending: (openai: OpenAI, userId: string, timezone: string, messageHistoryObject: SkillMessageHistoryType, userCurrentTime: string) => Promise<any>;
