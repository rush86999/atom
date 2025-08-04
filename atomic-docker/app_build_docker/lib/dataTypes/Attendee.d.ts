declare const Attendee: {
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
        name: {
            type: string[];
        };
        contactId: {
            type: string[];
        };
        emails: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    primary: {
                        type: string;
                    };
                    value: {
                        type: string;
                    };
                    type: {
                        type: string;
                    };
                    displayName: {
                        type: string;
                    };
                };
            };
        };
        phoneNumbers: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    primary: {
                        type: string;
                    };
                    value: {
                        type: string;
                    };
                    type: {
                        type: string;
                    };
                };
            };
        };
        imAddresses: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    primary: {
                        type: string;
                    };
                    username: {
                        type: string;
                    };
                    service: {
                        type: string;
                    };
                    type: {
                        type: string;
                    };
                };
            };
        };
        eventId: {
            type: string;
        };
        additionalGuests: {
            type: string;
        };
        comment: {
            type: string[];
        };
        responseStatus: {
            type: string[];
        };
        optional: {
            type: string;
        };
        resource: {
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
export default Attendee;
