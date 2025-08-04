import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { EventType, Time } from '@lib/dataTypes/EventType';
import { PreferredTimeRangeType } from '@lib/dataTypes/PreferredTimeRangeType';
export declare const dayOfWeekIntToString: {
    1: string;
    2: string;
    3: string;
    4: string;
    5: string;
    6: string;
    7: string;
};
export declare const addToSearchIndex: (event: EventType) => Promise<any>;
export declare const insertPreferredTimeRangeOneForEvent: (client: ApolloClient<NormalizedCacheObject>, id: string, eventId: string, startTime: Time, endTime: Time, dayOfWeek: number, userId: string, createdDate: string, updatedAt: string, toast?: any) => Promise<any>;
export declare const insertPreferredTimeRangesForEvent: (client: ApolloClient<NormalizedCacheObject>, preferredTimeRanges: PreferredTimeRangeType[]) => Promise<any>;
export declare const deletePreferredTimeRangeWithId: (client: ApolloClient<NormalizedCacheObject>, id: string) => Promise<any>;
export declare const deletePreferredTimeRangesByEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
export declare const listPreferredTimeRangesByEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
export declare const trainEventForPlanning: (client: ApolloClient<NormalizedCacheObject>, id: string, copyAvailability?: boolean | null, copyTimeBlocking?: boolean | null, copyTimePreference?: boolean | null, copyReminders?: boolean | null, copyPriorityLevel?: boolean | null, copyModifiable?: boolean | null, copyCategories?: boolean | null, copyIsBreak?: boolean | null, copyIsMeeting?: boolean | null, copyIsExternalMeeting?: boolean | null, copyDuration?: boolean | null, copyColor?: boolean | null) => Promise<any>;
