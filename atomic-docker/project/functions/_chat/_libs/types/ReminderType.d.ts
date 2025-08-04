export type ReminderType = {
    id: string;
    userId: string;
    eventId: string;
    reminderDate?: string;
    timezone?: string;
    minutes?: number;
    useDefault?: boolean;
    updatedAt: string;
    createdDate: string;
    deleted: boolean;
};
