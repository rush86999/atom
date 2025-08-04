declare const Reminder: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        eventId: {
            type: string;
        };
        userId: {
            type: string;
        };
        reminderDate: {
            type: string[];
        };
        timezone: {
            type: string;
        };
        minutes: {
            type: string[];
        };
        method: {
            type: string;
        };
        useDefault: {
            type: string;
        };
        updatedAt: {
            type: string;
        };
        createdDate: {
            type: string;
        };
    };
    required: string[];
    indexes: string[];
};
export default Reminder;
