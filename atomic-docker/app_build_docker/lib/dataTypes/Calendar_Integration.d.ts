declare const Calendar_Integration: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        token: {
            type: string[];
        };
        refreshToken: {
            type: string[];
        };
        resource: {
            type: string[];
        };
        name: {
            type: string[];
        };
        enabled: {
            type: string;
        };
        syncEnabled: {
            type: string;
        };
        expiresAt: {
            type: string[];
        };
        pageToken: {
            type: string[];
        };
        syncToken: {
            type: string[];
        };
        appId: {
            type: string[];
        };
        appEmail: {
            type: string[];
        };
        appAccountId: {
            type: string[];
        };
        contactName: {
            type: string[];
        };
        contactEmail: {
            type: string[];
        };
        colors: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    id: {
                        type: string;
                    };
                    background: {
                        type: string;
                    };
                    foreground: {
                        type: string;
                    };
                    itemType: {
                        type: string;
                    };
                };
            };
        };
        updatedAt: {
            type: string;
        };
        createdDate: {
            type: string;
        };
        userId: {
            type: string;
        };
    };
    required: string[];
    indexes: string[];
};
export default Calendar_Integration;
