type MethodType = 'remove-event';
export type DeleteEventType = {
    userId: string;
    timezone: string;
    title: string;
    method: MethodType;
};
export {};
