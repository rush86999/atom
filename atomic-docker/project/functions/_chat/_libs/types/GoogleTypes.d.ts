export type GoogleEventType1 = 'default' | 'outOfOffice' | 'focusTime';
export type GoogleAttachmentType = {
    title?: string;
    fileUrl: string;
    mimeType?: string;
    iconLink?: string;
    fileId?: string;
};
export type GoogleSourceType = {
    title?: string;
    url?: string;
};
export type ReminderType = {
    id: string;
    userId: string;
    eventId: string;
    reminderDate?: string;
    timezone?: string;
    minutes?: number;
    useDefault?: boolean;
    updatedAt: string;
    createdDate: string;
    deleted: boolean;
};
export type GoogleSendUpdatesType = 'all' | 'externalOnly' | 'none';
export type GoogleAttendeeType = {
    additionalGuests?: number;
    comment?: string;
    displayName?: string;
    email: string;
    id?: string;
    responseStatus?: 'needsAction' | 'declined' | 'tentative' | 'accepted';
};
export type GoogleConferenceDataType = {
    type: 'hangoutsMeet' | 'addOn';
    iconUri?: string;
    name?: string;
    requestId?: string;
    conferenceId?: string;
    createRequest?: {
        requestId: string;
        conferenceSolutionKey: {
            type: 'hangoutsMeet' | 'addOn';
        };
    };
    entryPoints?: GoogleEntryPointType[];
};
type GoogleEntryPointType = {
    accessCode?: string;
    label?: string;
    entryPointType: 'video' | 'phone' | 'sip' | 'more';
    meetingCode?: string;
    passcode?: string;
    password?: string;
    pin?: string;
    uri?: string;
};
export type GoogleExtendedPropertiesType = {
    private?: object;
    shared?: object;
};
export type GoogleTransparencyType = 'opaque' | 'transparent';
export type GoogleVisibilityType = 'default' | 'public' | 'private' | 'confidential';
export {};
