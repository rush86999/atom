type etag = string;
type date = string;
type datetime = string;
/**
{
  entryPointType: 'video' | 'phone' | 'sip' | 'more',
  entryPointFeatures?: string[],
  uri?: string,
  label?: string,
  pin?: string,
  accessCode?: string,
  meetingCode?: string,
  passcode?: string,
  password?: string
} */
export type entryPoint = {
    accessCode?: string;
    label?: string;
    entryPointType: 'video' | 'phone' | 'sip' | 'more';
    meetingCode?: string;
    passcode?: string;
    password?: string;
    pin?: string;
    uri?: string;
};
export type parameterType = {
    keys: string[];
    values: string[];
};
export type appType = 'zoom' | 'google';
export type conferenceNameType = 'Zoom Meeting' | 'Google Meet';
export type ConferenceType = {
    id: string;
    userId: string;
    calendarId: string;
    app: appType;
    requestId?: string;
    type?: string;
    status?: string;
    iconUri?: string;
    name?: string;
    notes?: string;
    entryPoints?: entryPoint[];
    parameters?: {
        addOnParameters?: {
            parameters?: parameterType[];
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
    isHost: boolean;
};
export type EmailType = {
    primary: boolean;
    value: string;
    type: string;
    displayName: string;
};
export type PhoneNumberType = {
    primary: boolean;
    value: string;
    type: string;
};
export type ImAddressType = {
    primary: boolean;
    username: string;
    service: string;
    type: string;
};
export type AttendeeType = {
    id: string;
    userId: string;
    name?: string;
    contactId?: string;
    emails: EmailType[];
    phoneNumbers?: PhoneNumberType[];
    imAddresses?: ImAddressType[];
    eventId: string;
    additionalGuests?: number;
    comment?: string;
    responseStatus?: string;
    optional?: boolean;
    resource?: boolean;
    updatedAt: string;
    createdDate: string;
    deleted: boolean;
};
export type eventTriggerResponse = {
    message: string;
    event_id: string;
};
export type colorTypeResponse = {
    kind: string;
    updated: datetime;
    calendar: {
        /** colorId */
        [key: string]: {
            background: string;
            foreground: string;
        };
    };
    event: {
        /** colorId */
        [key: string]: {
            background: string;
            foreground: string;
        };
    };
};
export type EventResourceType = {
    kind: 'calendar#event';
    etag: etag;
    id: string;
    status: string;
    htmlLink: string;
    created: datetime;
    updated: datetime;
    summary: string;
    description: string;
    location: string;
    colorId: string;
    creator: {
        id: string;
        email: string;
        displayName: string;
        self: boolean;
    };
    organizer: {
        id: string;
        email: string;
        displayName: string;
        self: boolean;
    };
    start: {
        date: date;
        dateTime: datetime;
        timeZone: string;
    };
    end: {
        date: date;
        dateTime: datetime;
        timeZone: string;
    };
    endTimeUnspecified: boolean;
    recurrence: string[];
    recurringEventId: string;
    originalStartTime: {
        date: date;
        dateTime: datetime;
        timeZone: string;
    };
    transparency: string;
    visibility: string;
    iCalUID: string;
    sequence: number;
    attendees: {
        /**
         * Number of additional guests. Optional. The default is 0.
         */
        additionalGuests?: number | null;
        /**
         * The attendee's response comment. Optional.
         */
        comment?: string | null;
        /**
         * The attendee's name, if available. Optional.
         */
        displayName?: string | null;
        /**
         * The attendee's email address, if available. This field must be present when adding an attendee. It must be a valid email address as per RFC5322.
         * Required when adding an attendee.
         */
        email?: string | null;
        /**
         * The attendee's Profile ID, if available.
         */
        id?: string | null;
        /**
         * Whether this is an optional attendee. Optional. The default is False.
         */
        optional?: boolean | null;
        /**
         * Whether the attendee is the organizer of the event. Read-only. The default is False.
         */
        organizer?: boolean | null;
        /**
         * Whether the attendee is a resource. Can only be set when the attendee is added to the event for the first time. Subsequent modifications are ignored. Optional. The default is False.
         */
        resource?: boolean | null;
        /**
         * The attendee's response status. Possible values are:
         * - "needsAction" - The attendee has not responded to the invitation.
         * - "declined" - The attendee has declined the invitation.
         * - "tentative" - The attendee has tentatively accepted the invitation.
         * - "accepted" - The attendee has accepted the invitation.
         */
        responseStatus?: string | null;
        /**
         * Whether this entry represents the calendar on which this copy of the event appears. Read-only. The default is False.
         */
        self?: boolean | null;
    }[];
    attendeesOmitted: boolean;
    extendedProperties?: {
        private?: {
            [key: string]: string;
        };
        shared?: {
            [key: string]: string;
        };
    } | null;
    hangoutLink: string;
    conferenceData?: {
        createRequest?: {
            requestId?: string;
            conferenceSolutionKey?: {
                type?: string;
            };
            status?: {
                statusCode?: string;
            };
        };
        entryPoints?: {
            entryPointType: 'video' | 'phone' | 'sip' | 'more';
            uri?: string;
            label?: string;
            pin?: string;
            accessCode?: string;
            meetingCode?: string;
            passcode?: string;
            password?: string;
        }[];
        conferenceSolution?: {
            key?: {
                type?: string;
            };
            name?: string;
            iconUri?: string;
        };
        conferenceId?: string;
        signature?: string;
        notes?: string;
    };
    gadget?: {
        display?: string;
        height?: number;
        iconLink?: string;
        link?: string;
        preferences?: {
            [key: string]: string;
        };
        title?: string;
        type?: string;
        width?: number;
    } | null;
    anyoneCanAddSelf: boolean;
    guestsCanInviteOthers: boolean;
    guestsCanModify: boolean;
    guestsCanSeeOtherGuests: boolean;
    privateCopy: boolean;
    locked: boolean;
    reminders: {
        useDefault: boolean;
        overrides: [
            {
                method: string;
                minutes: number;
            }
        ];
    };
    source: {
        url: string;
        title: string;
    };
    attachments: [
        {
            fileUrl: string;
            title: string;
            mimeType: string;
            iconLink: string;
            fileId: string;
        }
    ];
    eventType: 'default' | 'outOfOffice' | 'focusTime';
};
export type eventListResponse = {
    kind: 'calendar#events';
    etag: etag;
    summary: string;
    description: string;
    updated: datetime;
    timeZone: string;
    accessRole: string;
    defaultReminders: [
        {
            method: string;
            minutes: number;
        }
    ];
    nextPageToken: string;
    nextSyncToken: string;
    items: EventResourceType[];
};
type DefaultReminder = {
    method: string;
    minutes: number;
};
export type CalendarType = {
    id: string;
    title?: string;
    backgroundColor?: string;
    foregroundColor?: string;
    colorId?: string;
    account?: object;
    accessLevel?: string;
    resource?: string;
    modifiable?: boolean;
    defaultReminders?: DefaultReminder[];
    globalPrimary?: boolean;
    pageToken?: string;
    syncToken?: string;
    deleted: boolean;
    createdDate: string;
    updatedAt: string;
    userId: string;
};
export type ColorType = {
    id: string;
    background: string;
    foreground: string;
    itemType: 'calendar' | 'event';
};
export type CalendarIntegrationType = {
    id: string;
    userId: string;
    token?: string;
    refreshToken?: string;
    resource?: string;
    name?: string;
    enabled?: boolean;
    syncEnabled?: boolean;
    deleted?: boolean;
    appId?: string;
    appEmail?: string;
    appAccountId?: string;
    contactName?: string;
    contactEmail?: string;
    colors?: ColorType[];
    clientType?: 'ios' | 'android' | 'web' | 'atomic-web';
    expiresAt?: string;
    updatedAt: string;
    createdDate: string;
    pageToken?: string;
    syncToken?: string;
};
export type CalendarWatchRequestResourceType = {
    id: string;
    token: string;
    type: string;
    address: string;
    params?: {
        ttl: string;
    };
};
export type CalendarWatchResponseResourceType = {
    kind: 'api#channel';
    id: string;
    resourceId: string;
    resourceUri: string;
    token: string;
    expiration: number;
};
export {};
