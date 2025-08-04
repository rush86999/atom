declare const Conference: {
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
        requestId: {
            type: string[];
        };
        type: {
            type: string[];
        };
        status: {
            type: string[];
        };
        calendarId: {
            type: string;
        };
        iconUri: {
            type: string[];
        };
        name: {
            type: string[];
        };
        notes: {
            type: string[];
        };
        entryPoints: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    entryPointFeatures: {
                        type: string;
                        uniqueItems: boolean;
                        items: {
                            type: string;
                        };
                    };
                    regionCode: {
                        type: string;
                    };
                    entryPointType: {
                        type: string;
                    };
                    uri: {
                        type: string;
                    };
                    label: {
                        type: string;
                    };
                    pin: {
                        type: string;
                    };
                    accessCode: {
                        type: string;
                    };
                    meetingCode: {
                        type: string;
                    };
                    passcode: {
                        type: string;
                    };
                    password: {
                        type: string;
                    };
                };
            };
        };
        parameters: {
            type: string[];
            properties: {
                addOnParameters: {
                    type: string;
                    properties: {
                        parameters: {
                            type: string;
                            uniqueItems: boolean;
                            items: {
                                type: string;
                                properties: {
                                    keys: {
                                        type: string;
                                        uniqueItems: boolean;
                                        items: {
                                            type: string;
                                        };
                                    };
                                    values: {
                                        type: string;
                                        uniqueItems: boolean;
                                        items: {
                                            type: string;
                                        };
                                    };
                                };
                            };
                        };
                    };
                };
            };
        };
        app: {
            type: string;
        };
        key: {
            type: string[];
        };
        hangoutLink: {
            type: string[];
        };
        joinUrl: {
            type: string[];
        };
        startUrl: {
            type: string[];
        };
        zoomPrivateMeeting: {
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
export default Conference;
