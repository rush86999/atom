import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';
type MethodType = 'edit-remove-time-preferences';
export type EditRemovePreferredTimeToPreferredTimesType = {
    userId: string;
    timezone: string;
    title?: string;
    timePreferences: TimePreferenceType[];
    method: MethodType;
};
export {};
