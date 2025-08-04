type MethodType = 'remove-time-preferences';
export type RemoveAllPreferredTimes = {
    userId: string;
    timezone: string;
    title?: string;
    method: MethodType;
};
export {};
