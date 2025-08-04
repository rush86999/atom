type MethodType = 'remove-event';
export type CancelMeetingType = {
    userId: string;
    timezone: string;
    title: string;
    method: MethodType;
};
export {};
