declare const Contact_Event: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        contactId: {
            type: string;
        };
        eventId: {
            type: string;
        };
        userId: {
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
    indexes: string[][];
};
export default Contact_Event;
