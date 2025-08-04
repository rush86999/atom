type EtagType = string;
type date = string;
type datetime = string;
type entryPoint = {
    accessCode?: string;
    label?: string;
    entryPointType: 'video' | 'phone' | 'sip' | 'more';
    meetingCode?: string;
    passcode?: string;
    password?: string;
    pin?: string;
    uri?: string;
};
export type GoogleAttendeeType = {
    additionalGuests?: number;
    comment?: string;
    displayName?: string;
    email: string;
    id?: string;
    responseStatus?: 'needsAction' | 'declined' | 'tentative' | 'accepted';
};
/**
"conferenceData": {
    "conferenceId": "",
    "conferenceSolution": {
      "key": {
        "type": ""
      },
      "iconUri": "",
      "name": ""
    },
    "parameters": {
      "addOnParameters": {
        "parameters": {
          "": "",
          "": ""
        }
      }
    },
    "entryPoints": [
      {
        "accessCode": "",
        "entryPointFeatures": [
          "",
          ""
        ],
        "entryPointType": "",
        "meetingCode": "",
        "label": "",
        "passcode": "",
        "password": "",
        "pin": "",
        "regionCode": "",
        "uri": ""
      }
    ],
    "createRequest": {
      "conferenceSolutionKey": {
        "type": ""
      },
      "requestId": "",
      "status": {
        "statusCode": ""
      }
    },
    "notes": "",
    "signature": ""
  } */
export type ConferenceDataType = {
    type: 'hangoutsMeet' | 'addOn';
    iconUri?: string;
    name?: string;
    requestId?: string;
    conferenceId?: string;
    createRequest: boolean;
    entryPoints?: entryPoint[];
};
export type allowedConferenceSolutionType = 'eventHangout' | 'hangoutsMeet' | 'addOn';
export type extendedProperties = {
    private?: object;
    shared?: object;
};
type override = {
    method: 'email' | 'popup';
    minutes: number;
};
type overrides = override[];
export type GoogleReminderType = {
    overrides?: overrides;
    useDefault: boolean;
};
export type source = {
    title?: string;
    url?: string;
};
export type SendUpdatesType = 'all' | 'externalOnly' | 'none';
export type TransparencyType = 'opaque' | 'transparent';
export type VisibilityType = 'default' | 'public' | 'private' | 'confidential';
export type calendarResponse = {
    kind: 'calendar#calendar';
    etag: EtagType;
    id: string;
    summary: string;
    description: string;
    location: string;
    timeZone: string;
    conferenceProperties: {
        allowedConferenceSolutionTypes: [string];
    };
};
export type eventResponse = {
    kind: 'calendar#event';
    etag: EtagType;
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
    recurrence: [string];
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
    attendees: [
        {
            id: string;
            email: string;
            displayName: string;
            organizer: boolean;
            self: boolean;
            resource: boolean;
            optional: boolean;
            responseStatus: string;
            comment: string;
            additionalGuests: number;
        }
    ];
    attendeesOmitted: boolean;
    extendedProperties: {
        private: {
            (key: string): string;
        };
        shared: {
            (key: string): string;
        };
    };
    hangoutLink: string;
    conferenceData: {
        createRequest: {
            requestId: string;
            conferenceSolutionKey: {
                type: string;
            };
            status: {
                statusCode: string;
            };
        };
        entryPoints: [
            {
                entryPointType: string;
                uri: string;
                label: string;
                pin: string;
                accessCode: string;
                meetingCode: string;
                passcode: string;
                password: string;
            }
        ];
        conferenceSolution: {
            key: {
                type: string;
            };
            name: string;
            iconUri: string;
        };
        conferenceId: string;
        signature: string;
        notes: string;
    };
    gadget: {
        type: string;
        title: string;
        link: string;
        iconLink: string;
        width: number;
        height: number;
        display: string;
        preferences: {
            (key: any): string;
        };
    };
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
export type eventType1 = 'default' | 'outOfOffice' | 'focusTime';
export type attachment = {
    fileUrl: string;
    title: string;
    mimeType: string;
    iconLink: string;
    fileId: string;
};
export type DefaultReminderType = {
    minutes: number;
    method: string;
};
export type NotificationType = {
    type: 'eventCreation' | 'eventChange' | 'eventCancellation' | 'eventResponse' | 'agenda';
    method: 'email';
};
export type CalendarListResponseType = {
    kind: 'calendar#calendarList';
    etag: EtagType;
    nextPageToken: string;
    nextSyncToken: string;
    items: CalendarListItemResponseType[];
};
export type CalendarListItemResponseType = {
    kind: 'calendar#calendarListEntry';
    etag: EtagType;
    id: string;
    summary: string;
    description: string;
    location: string;
    timeZone: string;
    summaryOverride: string;
    colorId: string;
    backgroundColor: string;
    foregroundColor: string;
    hidden: boolean;
    selected: boolean;
    accessRole: string;
    defaultReminders: DefaultReminderType[];
    notificationSettings: {
        notifications: NotificationType[];
    };
    primary: boolean;
    deleted: boolean;
    conferenceProperties: {
        allowedConferenceSolutionTypes: [string];
    };
};
export type colorResponseType = {
    kind: 'calendar#colors';
    updated: string;
    calendar: {
        [key: string]: {
            background: string;
            foreground: string;
        };
    };
    event: {
        [key: string]: {
            background: string;
            foreground: string;
        };
    };
};
export type RefreshTokenResponseBodyType = {
    access_token: string;
    expires_in: number;
    scope: string;
    token_type: string;
};
export {};
