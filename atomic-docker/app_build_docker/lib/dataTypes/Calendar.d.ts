declare const Calendar: {
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
        title: {
            type: string[];
        };
        backgroundColor: {
            type: string[];
        };
        foregroundColor: {
            type: string[];
        };
        colorId: {
            type: string[];
        };
        account: {
            type: string[];
            properties: {
                id: {
                    type: string;
                };
                isLocal: {
                    type: string;
                };
                name: {
                    type: string[];
                };
                type: {
                    type: string[];
                };
            };
        };
        accessLevel: {
            type: string[];
        };
        resource: {
            type: string[];
        };
        modifiable: {
            type: string;
        };
        globalPrimary: {
            type: string;
        };
        defaultReminders: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    method: {
                        type: string[];
                    };
                    minutes: {
                        type: string[];
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
    };
    required: string[];
    indexes: string[];
};
export default Calendar;
