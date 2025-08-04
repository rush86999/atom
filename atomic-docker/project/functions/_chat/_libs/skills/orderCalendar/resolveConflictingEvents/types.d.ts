import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';
type MethodType = 'create-time-preferences' | 'remove-time-preferences' | 'edit-add-time-preferences' | 'edit-remove-time-preferences';
export type ResolveConflictingEventsType = {
    userId: string;
    timezone: string;
    title?: string;
    priority?: number;
    timePreferences: TimePreferenceType[];
    method: MethodType;
};
export {};
