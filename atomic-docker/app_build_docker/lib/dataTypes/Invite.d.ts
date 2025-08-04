declare const Invite: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        userId: {
            type: string;
        };
        emails: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        phoneNumbers: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        imAddresses: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        categories: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        availableSlots: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        name: {
            type: string[];
        };
        eventId: {
            type: string;
        };
        emailId: {
            type: string;
        };
        contactId: {
            type: string[];
        };
        phoneId: {
            type: string[];
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
export default Invite;
