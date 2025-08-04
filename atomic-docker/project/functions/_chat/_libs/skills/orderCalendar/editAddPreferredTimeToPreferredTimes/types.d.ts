import TimePreferenceType from '../../../types/TimePreferenceType';
type MethodType = 'edit-add-time-preferences';
export type EditAddPreferredTimeToPreferredTimesType = {
    userId: string;
    timezone: string;
    title?: string;
    timePreferences: TimePreferenceType[];
    method: MethodType;
    startDate?: string;
    endDate?: string;
};
export {};
