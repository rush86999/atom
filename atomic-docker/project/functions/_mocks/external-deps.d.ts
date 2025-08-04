export declare class MockOpenAI {
    constructor(config: any);
    chat: {
        completions: {
            create: (params: any) => Promise<{
                id: string;
                object: string;
                created: number;
                model: any;
                choices: {
                    index: number;
                    message: {
                        role: string;
                        content: string;
                    };
                    finish_reason: string;
                }[];
                usage: {
                    prompt_tokens: number;
                    completion_tokens: number;
                    total_tokens: number;
                };
            }>;
        };
    };
    embeddings: {
        create: (params: any) => Promise<{
            object: string;
            data: {
                object: string;
                embedding: any[];
                index: number;
            }[];
            model: any;
            usage: {
                prompt_tokens: number;
                total_tokens: number;
            };
        }>;
    };
}
export declare const mockDateFns: {
    startOfWeek: (date: Date, options?: any) => Date;
    endOfWeek: (date: Date, options?: any) => Date;
    startOfMonth: (date: Date) => Date;
    endOfMonth: (date: Date) => Date;
    add: (date: Date, duration: any) => Date;
    sub: (date: Date, duration: any) => Date;
    format: (date: Date, formatStr: string) => string;
    getISODay: (date: Date) => number;
};
export declare const mockGoogleApis: {
    google: {
        auth: {
            OAuth2: {
                new (clientId?: string, clientSecret?: string, redirectUri?: string): {
                    credentials: any;
                    setCredentials(tokens: any): void;
                    getAccessToken(): Promise<{
                        token: string;
                        res: null;
                    }>;
                    refreshAccessToken(): Promise<{
                        credentials: {
                            access_token: string;
                            refresh_token: string;
                            expiry_date: number;
                        };
                    }>;
                };
            };
        };
        calendar: (options: any) => {
            events: {
                list: (params: any) => Promise<{
                    data: {
                        items: never[];
                        nextPageToken: null;
                        summary: string;
                        updated: string;
                    };
                }>;
                get: (params: any) => Promise<{
                    data: {
                        id: any;
                        summary: string;
                        start: {
                            dateTime: string;
                        };
                        end: {
                            dateTime: string;
                        };
                    };
                }>;
                insert: (params: any) => Promise<{
                    data: any;
                }>;
                update: (params: any) => Promise<{
                    data: any;
                }>;
                delete: (params: any) => Promise<{}>;
            };
            calendarList: {
                list: () => Promise<{
                    data: {
                        items: {
                            id: string;
                            summary: string;
                            primary: boolean;
                            accessRole: string;
                        }[];
                    };
                }>;
            };
        };
    };
};
export declare class MockOpenSearchClient {
    constructor(config: any);
    search(params: any): Promise<{
        body: {
            took: number;
            timed_out: boolean;
            hits: {
                total: {
                    value: number;
                    relation: string;
                };
                hits: never[];
            };
        };
    }>;
    index(params: any): Promise<{
        body: {
            _index: any;
            _id: any;
            _version: number;
            result: string;
        };
    }>;
    bulk(params: any): Promise<{
        body: {
            took: number;
            errors: boolean;
            items: never[];
        };
    }>;
    delete(params: any): Promise<{
        body: {
            _index: any;
            _id: any;
            result: string;
        };
    }>;
}
export declare class MockS3Client {
    constructor(config: any);
    send(command: any): Promise<{
        ETag: string;
        VersionId: string;
    } | {
        ETag?: undefined;
        VersionId?: undefined;
    }>;
}
export declare class MockPutObjectCommand {
    params: any;
    constructor(params: any);
}
export declare class MockKafka {
    constructor(config: any);
    producer(): {
        connect: () => Promise<void>;
        send: (params: any) => Promise<{
            topicName: any;
            partition: number;
            errorCode: number;
        }[]>;
        disconnect: () => Promise<void>;
    };
    consumer(config: any): {
        connect: () => Promise<void>;
        subscribe: (params: any) => Promise<void>;
        run: (params: any) => Promise<void>;
        disconnect: () => Promise<void>;
    };
}
export declare const mockIp: {
    address: () => string;
    isPrivate: (addr: string) => boolean;
    isLoopback: (addr: string) => addr is "127.0.0.1" | "::1";
    loopback: (family?: string) => "127.0.0.1" | "::1";
};
export declare const mockGot: {
    get: (url: string, options?: any) => Promise<{
        body: {};
        statusCode: number;
        headers: {};
    }>;
    post: (url: string, options?: any) => Promise<{
        body: {};
        statusCode: number;
        headers: {};
    }>;
    put: (url: string, options?: any) => Promise<{
        body: {};
        statusCode: number;
        headers: {};
    }>;
    delete: (url: string, options?: any) => Promise<{
        body: {};
        statusCode: number;
        headers: {};
    }>;
};
export declare const mockAxios: {
    get: (url: string, config?: any) => Promise<{
        data: {};
        status: number;
        statusText: string;
        headers: {};
        config: any;
    }>;
    post: (url: string, data?: any, config?: any) => Promise<{
        data: {};
        status: number;
        statusText: string;
        headers: {};
        config: any;
    }>;
    put: (url: string, data?: any, config?: any) => Promise<{
        data: {};
        status: number;
        statusText: string;
        headers: {};
        config: any;
    }>;
    delete: (url: string, config?: any) => Promise<{
        data: {};
        status: number;
        statusText: string;
        headers: {};
        config: any;
    }>;
};
declare const _default: {
    OpenAI: typeof MockOpenAI;
    dateFns: {
        startOfWeek: (date: Date, options?: any) => Date;
        endOfWeek: (date: Date, options?: any) => Date;
        startOfMonth: (date: Date) => Date;
        endOfMonth: (date: Date) => Date;
        add: (date: Date, duration: any) => Date;
        sub: (date: Date, duration: any) => Date;
        format: (date: Date, formatStr: string) => string;
        getISODay: (date: Date) => number;
    };
    googleapis: {
        google: {
            auth: {
                OAuth2: {
                    new (clientId?: string, clientSecret?: string, redirectUri?: string): {
                        credentials: any;
                        setCredentials(tokens: any): void;
                        getAccessToken(): Promise<{
                            token: string;
                            res: null;
                        }>;
                        refreshAccessToken(): Promise<{
                            credentials: {
                                access_token: string;
                                refresh_token: string;
                                expiry_date: number;
                            };
                        }>;
                    };
                };
            };
            calendar: (options: any) => {
                events: {
                    list: (params: any) => Promise<{
                        data: {
                            items: never[];
                            nextPageToken: null;
                            summary: string;
                            updated: string;
                        };
                    }>;
                    get: (params: any) => Promise<{
                        data: {
                            id: any;
                            summary: string;
                            start: {
                                dateTime: string;
                            };
                            end: {
                                dateTime: string;
                            };
                        };
                    }>;
                    insert: (params: any) => Promise<{
                        data: any;
                    }>;
                    update: (params: any) => Promise<{
                        data: any;
                    }>;
                    delete: (params: any) => Promise<{}>;
                };
                calendarList: {
                    list: () => Promise<{
                        data: {
                            items: {
                                id: string;
                                summary: string;
                                primary: boolean;
                                accessRole: string;
                            }[];
                        };
                    }>;
                };
            };
        };
    };
    OpenSearchClient: typeof MockOpenSearchClient;
    S3Client: typeof MockS3Client;
    PutObjectCommand: typeof MockPutObjectCommand;
    Kafka: typeof MockKafka;
    ip: {
        address: () => string;
        isPrivate: (addr: string) => boolean;
        isLoopback: (addr: string) => addr is "127.0.0.1" | "::1";
        loopback: (family?: string) => "127.0.0.1" | "::1";
    };
    got: {
        get: (url: string, options?: any) => Promise<{
            body: {};
            statusCode: number;
            headers: {};
        }>;
        post: (url: string, options?: any) => Promise<{
            body: {};
            statusCode: number;
            headers: {};
        }>;
        put: (url: string, options?: any) => Promise<{
            body: {};
            statusCode: number;
            headers: {};
        }>;
        delete: (url: string, options?: any) => Promise<{
            body: {};
            statusCode: number;
            headers: {};
        }>;
    };
    axios: {
        get: (url: string, config?: any) => Promise<{
            data: {};
            status: number;
            statusText: string;
            headers: {};
            config: any;
        }>;
        post: (url: string, data?: any, config?: any) => Promise<{
            data: {};
            status: number;
            statusText: string;
            headers: {};
            config: any;
        }>;
        put: (url: string, data?: any, config?: any) => Promise<{
            data: {};
            status: number;
            statusText: string;
            headers: {};
            config: any;
        }>;
        delete: (url: string, config?: any) => Promise<{
            data: {};
            status: number;
            statusText: string;
            headers: {};
            config: any;
        }>;
    };
};
export default _default;
