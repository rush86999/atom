import { MeetingTypeStringType } from '@lib/zoom/types';
export type EntryPointType = {
    accessCode?: string;
    label?: string;
    entryPointType: 'video' | 'phone' | 'sip' | 'more';
    meetingCode?: string;
    passcode?: string;
    password?: string;
    pin?: string;
    uri?: string;
};
export type ParameterType = {
    keys: string[];
    values: string[];
};
export type AppType = 'zoom' | 'google';
export type ConferenceNameType = 'Zoom Meeting' | 'Google Meet';
export type ConferenceType = {
    id: string;
    userId: string;
    calendarId: string;
    app: AppType;
    requestId?: string;
    type?: MeetingTypeStringType;
    status?: string;
    iconUri?: string;
    name?: string;
    notes?: string;
    entryPoints?: EntryPointType[];
    parameters?: {
        addOnParameters?: {
            parameters?: ParameterType[];
        };
    };
    key?: string;
    hangoutLink?: string;
    joinUrl?: string;
    startUrl?: string;
    zoomPrivateMeeting?: boolean;
    updatedAt: string;
    createdDate: string;
    deleted: boolean;
};
