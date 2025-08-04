export type MarkedType = {
    [key: string]: {
        marked: boolean;
        dotColor?: string;
    };
};
export declare const HOURS_SIDEBAR_WIDTH = 72;
export type TagType = {
    id: string;
    name: string;
    color: string;
};
type source2 = {
    userId: string;
};
export type esResponseBody = {
    took?: number;
    timed_out?: false;
    _shards?: {
        total: number;
        successful: number;
        skipped: number;
        failed: number;
    };
    hits?: {
        total: {
            value: number;
            relation: string;
        };
        max_score: number;
        hits?: [
            {
                _index: string;
                _type: string;
                _id: string;
                _score: number;
                _source: source2;
            }
        ];
    };
};
export type accessRole = 'freeBusyReader' | 'reader' | 'writer' | 'owner';
export type RecurrenceFrequencyType = 'daily' | 'weekly' | 'monthly' | 'yearly';
export type email = {
    primary: boolean;
    value: string;
    type?: string;
    displayName?: string;
};
export type phoneNumber = {
    primary: boolean;
    value: string;
    type?: string;
};
export type imAddress = {
    primary: boolean;
    username: string;
    service: string;
    type?: string;
};
export type Person = {
    id: string;
    name?: string;
    emails: email[];
    phoneNumbers?: phoneNumber[];
    imAddresses?: imAddress[];
    additionalGuests?: number;
    optional?: boolean;
    resource?: boolean;
};
export {};
/**
end */
