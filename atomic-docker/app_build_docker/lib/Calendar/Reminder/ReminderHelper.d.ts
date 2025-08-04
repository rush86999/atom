import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { ReminderType } from '@lib/dataTypes/ReminderType';
export declare const deleteRemindersForEvents: (client: ApolloClient<NormalizedCacheObject>, eventIds: string[], userId: string) => Promise<any>;
export declare const removeRemindersForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
export declare const updateRemindersForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string, userId: string, alarms?: string[] | number[], timezone?: string, useDefaultAlarms?: boolean) => Promise<void>;
export declare const createRemindersForEvent: (client: ApolloClient<NormalizedCacheObject>, reminderValuesToUpsert: ReminderType[]) => Promise<any>;
export declare const createReminderForEvent: (client: ApolloClient<NormalizedCacheObject>, userId: string, eventId: string, reminderDate?: string, timezone?: string, minutes?: number, useDefault?: boolean) => Promise<any>;
export declare const listRemindersForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
/** end */
