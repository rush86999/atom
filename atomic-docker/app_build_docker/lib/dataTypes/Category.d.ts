declare const Category: {
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
            type: string;
        };
        copyAvailability: {
            type: string[];
        };
        copyTimeBlocking: {
            type: string[];
        };
        copyTimePreference: {
            type: string[];
        };
        copyReminders: {
            type: string[];
        };
        copyPriorityLevel: {
            type: string[];
        };
        copyModifiable: {
            type: string[];
        };
        defaultAvailability: {
            type: string[];
        };
        defaultTimeBlocking: {
            type: string[];
            properties: {
                beforeEvent: {
                    type: string[];
                };
                afterEvent: {
                    type: string[];
                };
            };
        };
        defaultTimePreference: {
            type: string[];
            properties: {
                preferredDayOfWeek: {
                    type: string[];
                };
                preferredTime: {
                    type: string[];
                    format: string;
                };
                preferredStartTimeRange: {
                    type: string[];
                    format: string;
                };
                preferredEndTimeRange: {
                    type: string[];
                    format: string;
                };
            };
        };
        defaultReminders: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        defaultPriorityLevel: {
            type: string[];
        };
        defaultModifiable: {
            type: string[];
        };
        copyIsBreak: {
            type: string[];
        };
        defaultIsBreak: {
            type: string[];
        };
        color: {
            type: string[];
        };
        copyIsMeeting: {
            type: string[];
        };
        copyIsExternalMeeting: {
            type: string[];
        };
        defaultIsMeeting: {
            type: string[];
        };
        defaultIsExternalMeeting: {
            type: string[];
        };
        defaultMeetingModifiable: {
            type: string[];
        };
        defaultExternalMeetingModifiable: {
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
export default Category;
