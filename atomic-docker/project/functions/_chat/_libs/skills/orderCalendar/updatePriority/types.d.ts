type MethodType = 'edit-event-property';
export type AddPriorityType = {
    userId: string;
    timezone: string;
    title: string;
    priority: number;
    method: MethodType;
};
export {};
