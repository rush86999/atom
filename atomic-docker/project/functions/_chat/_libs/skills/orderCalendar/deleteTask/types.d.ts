type MethodType = 'remove-event';
export type DeleteTaskType = {
    userId: string;
    timezone: string;
    title: string;
    method: MethodType;
};
export type SearchBoundaryType = {
    startDate: string;
    endDate: string;
};
export {};
