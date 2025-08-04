import { UserPreferenceType } from '@chat/_libs/types/UserPreferenceType';
import { DataAttributesType, UserWorkTimeType } from './types';
export declare const generateWorkTimesForUser: (userPreference: UserPreferenceType, timezone: string) => UserWorkTimeType[];
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType | null>;
export declare const getEventObjectCount: (userId: string, startDate: string, endDate: string) => Promise<number | undefined>;
export declare const listAttendeesGivenEventIds: (eventIds: string[]) => Promise<AttendeeType[] | undefined>;
export declare const listTasksGivenIds: (ids: string[]) => Promise<TaskType[] | undefined>;
export declare const listConferencesGivenIds: (ids: string[]) => Promise<ConferenceType[] | undefined>;
export declare const listSortedObjectsForUserGivenDatesAndAttributes: (userId: string, startDate: string, endDate: string, attributes: DataAttributesType[], isMeeting: boolean, ids?: string[]) => Promise<{
    events: EventType[];
    conferences: ConferenceType[];
    attendees: AttendeeType[];
    tasks: TaskType[];
    count: number;
} | undefined>;
