import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { DefaultRemindersType, DefaultTimeBlockingType, DefaultTimePreferenceTypes } from '@lib/dataTypes/CategoryType';
export declare const createCategory: (client: ApolloClient<NormalizedCacheObject>, category: string, userId: string) => Promise<any>;
export declare const listUserCategories: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<any>;
export declare const updateCategoryName: (client: ApolloClient<NormalizedCacheObject>, newName: string, categoryId: string) => Promise<any>;
export declare const removeCategory: (client: ApolloClient<NormalizedCacheObject>, categoryId: string) => Promise<any>;
export declare const removeEventConnectionsForCategory: (client: ApolloClient<NormalizedCacheObject>, categoryId: string) => Promise<any>;
export declare const upsertCategoryEventConnection: (client: ApolloClient<NormalizedCacheObject>, userId: string, categoryId: string, eventId: string) => Promise<void>;
export declare const listEventsForCategory: (client: ApolloClient<NormalizedCacheObject>, categoryId: string) => Promise<any>;
export declare const listCategoriesForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
export declare const removeCategoryConnectionForEvent: (client: ApolloClient<NormalizedCacheObject>, categoryId: string, eventId: string) => Promise<any>;
export declare const removeAllCategoriesForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<void>;
export declare const addCategoryToUser: (client: ApolloClient<NormalizedCacheObject>, userId: string, name: string) => Promise<any>;
export declare const getCategoryWithId: (client: ApolloClient<NormalizedCacheObject>, categoryId: string) => Promise<any>;
export declare const updateCategoryHelper: (client: ApolloClient<NormalizedCacheObject>, categoryId: string, name: string, copyAvailability?: boolean, copyTimeBlocking?: boolean, copyTimePreference?: boolean, copyReminders?: boolean, copyPriorityLevel?: boolean, copyModifiable?: boolean, defaultAvailability?: boolean, defaultTimeBlocking?: DefaultTimeBlockingType | null, defaultTimePreference?: DefaultTimePreferenceTypes | null, defaultReminders?: DefaultRemindersType | null, defaultPriorityLevel?: number, defaultModifiable?: boolean, copyIsBreak?: boolean, defaultIsBreak?: boolean, color?: string, copyIsMeeting?: boolean, copyIsExternalMeeting?: boolean, defaultIsMeeting?: boolean, defaultIsExternalMeeting?: boolean, defaultMeetingModifiable?: boolean, defaultExternalMeetingModifiable?: boolean) => Promise<any>;
/**
End */
