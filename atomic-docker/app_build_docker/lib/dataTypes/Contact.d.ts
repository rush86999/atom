declare const Contact: {
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
        firstName: {
            type: string[];
        };
        middleName: {
            type: string[];
        };
        lastName: {
            type: string[];
        };
        maidenName: {
            type: string[];
        };
        namePrefix: {
            type: string[];
        };
        nameSuffix: {
            type: string[];
        };
        nickname: {
            type: string[];
        };
        phoneticFirstName: {
            type: string[];
        };
        phoneticMiddleName: {
            type: string[];
        };
        phoneticLastName: {
            type: string[];
        };
        company: {
            type: string[];
        };
        jobTitle: {
            type: string[];
        };
        department: {
            type: string[];
        };
        notes: {
            type: string[];
        };
        imageAvailable: {
            type: string;
        };
        image: {
            type: string[];
        };
        contactType: {
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
        linkAddresses: {
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
        app: {
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
export default Contact;
