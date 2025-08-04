declare const User_Preference: {
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
        reminders: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        followUp: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        isPublicCalendar: {
            type: string;
        };
        publicCalendarCategories: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        startTimes: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    day: {
                        type: string;
                    };
                    hour: {
                        type: string;
                    };
                    minutes: {
                        type: string;
                    };
                };
            };
        };
        endTimes: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    day: {
                        type: string;
                    };
                    hour: {
                        type: string;
                    };
                    minutes: {
                        type: string;
                    };
                };
            };
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
        copyCategories: {
            type: string[];
        };
        copyIsBreak: {
            type: string[];
        };
        maxWorkLoadPercent: {
            type: string[];
        };
        backToBackMeetings: {
            type: string[];
        };
        maxNumberOfMeeting: {
            type: string[];
        };
        minNumberOfBreaks: {
            type: string[];
        };
        breakLength: {
            type: string[];
        };
        breakColor: {
            type: string[];
        };
        copyIsMeeting: {
            type: string[];
        };
        copyIsExternalMeeting: {
            type: string[];
        };
        copyColor: {
            type: string[];
        };
        onBoarded: {
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
export default User_Preference;
