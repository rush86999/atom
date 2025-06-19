

// --- Generic Skill Error and Response Types ---
// (Mirrors the structure from project/functions/atom-agent/types.ts for consistency)
export interface SkillError {
  code: string;
  message: string;
  details?: any;
}

export interface HandshakeApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

export type ColorType = {
    id: string,
    background: string,
    foreground: string,
    itemType: 'calendar' | 'event',
}

export type CalendarIntegrationType = {
    id: string,
    userId: string,
    token?: string,
    refreshToken?: string,
    resource?: string,
    name?: string,
    enabled?: boolean,
    syncEnabled?: boolean,
    deleted?: boolean,
    appId?: string,
    appEmail?: string,
    appAccountId?: string,
    contactName?: string,
    contactEmail?: string,
    colors?: ColorType[],
    clientType?: 'ios' | 'android' | 'web',
    expiresAt?: string,
    updatedAt: string,
    createdDate: string,
    pageToken?: string,
    syncToken?: string,
}

export type appType = 'zoom' | 'google'

export type BufferTimeNumberType = {
    beforeEvent: number
    afterEvent: number
}


export type MeetingAssistType = {
    id: string,
    eventId?: string,
    userId: string,
    summary?: string,
    notes?: string,
    windowStartDate: string,
    windowEndDate: string,
    timezone?: string,
    location?: object,
    priority: number,
    enableConference: boolean,
    conferenceApp?: appType,
    sendUpdates?: 'all' | 'externalOnly' | 'none',
    guestsCanInviteOthers: boolean,
    transparency?: 'opaque' | 'transparent',
    visibility?: 'default' | 'public' | 'private',
    createdDate: string,
    updatedAt: string,
    colorId?: string,
    backgroundColor?: string,
    foregroundColor?: string,
    useDefaultAlarms?: boolean,
    reminders?: number[],
    cancelIfAnyRefuse?: boolean, // todo
    enableHostPreferences?: boolean, // not needed?
    enableAttendeePreferences?: boolean, // done
    attendeeCanModify?: boolean,
    startDate?: string,
    endDate?: string,
    attendeeCount?: number,
    expireDate?: string,
    attendeeRespondedCount: number, // todo
    cancelled: boolean, // to do
    duration: number,
    calendarId: string,
    bufferTime: BufferTimeNumberType,
    anyoneCanAddSelf: boolean,
    guestsCanSeeOtherGuests: boolean,
    minThresholdCount?: number,
    allowAttendeeUpdatePreferences?: boolean,
    guaranteeAvailability?: boolean,
    frequency?: RecurrenceFrequencyType,
    interval?: number,
    until?: string, // no timezone
    originalMeetingId?: string,
}

export type EmailType = {
    primary: boolean,
    value: string,
    type: 'home' | 'work' | 'other',
    displayName: string,
}

export type PhoneNumberType = {
    primary: boolean,
    value: string,
    type: string,
}

export type ImAddressType = {
    primary: boolean,
    username: string,
    service: string,
    type: string,
}


export type MeetingAssistAttendeeType = {
    id: string,
    name?: string,
    hostId: string,
    userId: string,
    emails: EmailType[],
    contactId?: string,
    phoneNumbers?: PhoneNumberType[],
    imAddresses?: ImAddressType[],
    meetingId: string,
    createdDate: string,
    timezone?: string,
    updatedAt: string,
    externalAttendee: boolean,
    primaryEmail?: string,
}

export type UserContactInfoType = {
    createdDate: string,
    id: string,
    name?: string,
    primary: boolean,
    type: 'email' | 'phone',
    updatedAt: string,
    userId: string,
}

// type DefaultReminderType = {
//     method: string,
//     minutes: number,
// }

export type MeetingAssistCalendarType = {
    id: string,
    attendeeId: string,
    title?: string,
    backgroundColor?: string,
    account?: object,
    accessLevel?: string,
    modifiable: boolean,
    defaultReminders?: DefaultReminderType[],
    resource?: string,
    primary: boolean,
    colorId?: string,
    foregroundColor?: string,
}

export type CalendarListResponseType = {
    kind: 'calendar#calendarList'
    etag: EtagType
    nextPageToken: string
    nextSyncToken: string
    items: CalendarListItemResponseType[]
}

type EtagType = string

export type DefaultReminderType = {
    minutes: number
    method: string
}

export type NotificationType = {
    type:
    | 'eventCreation'
    | 'eventChange'
    | 'eventCancellation'
    | 'eventResponse'
    | 'agenda'
    method: 'email'
}

export type CalendarListItemResponseType = {
    kind: 'calendar#calendarListEntry'
    etag: EtagType
    id: string
    summary: string
    description: string
    location: string
    timeZone: string
    summaryOverride: string
    colorId: string
    backgroundColor: string
    foregroundColor: string
    hidden: boolean
    selected: boolean
    accessRole: string
    defaultReminders: DefaultReminderType[]
    notificationSettings: {
        notifications: NotificationType[]
    }
    primary: boolean
    deleted: boolean
    conferenceProperties: {
        allowedConferenceSolutionTypes: [string]
    }
}

export type RecurrenceRuleType = {
    frequency: string,
    endDate: string,
    occurrence?: number,
    interval: number,
    byWeekDay?: string[],
} | {
    frequency: string,
    endDate?: string,
    occurrence: number,
    interval: number,
    byWeekDay?: string[],
}

export type LocationType = {
    title: string,
    proximity?: string,
    radius?: number,
    coords?: {
        latitude?: number,
        longitude?: number,
    },
    address?: {
        houseNumber?: number,
        prefixDirection?: string,
        prefixType?: string,
        streetName?: string,
        streetType?: string,
        suffixDirection?: string,
        city?: string,
        state?: string,
        postalCode?: string,
        country?: string
    }
}

export type LinkType = {
    title: string,
    link: string
}

export type AttachmentType = {
    title: string,
    fileUrl: string,
    mimeType: string,
    iconLink: string,
    fileId: string
}

export type SendUpdatesType = 'all' | 'externalOnly' | 'none'

export type TransparencyType = 'opaque' | 'transparent' // available or not

export type VisibilityType = 'default' | 'public' | 'private' | 'confidential'

export type CreatorType = {
    id?: string,
    email?: string,
    displayName?: string,
    self?: boolean
}

export type OrganizerType = {
    id: string,
    email: string,
    displayName: string,
    self: boolean
}

export type ExtendedPropertiesType = {
    private?: {
        keys?: string[],
        values?: string[],
    },
    shared?: {
        keys?: string[],
        values?: string[]
    },
}

export type SourceType = {
    title?: string,
    url?: string,
}

export type MeetingAssistEventType = {
    id: string,
    attendeeId: string,
    startDate: string,
    endDate: string,
    allDay?: boolean,
    recurrenceRule?: RecurrenceRuleType,
    location?: LocationType,
    notes?: string,
    attachments?: AttachmentType[],
    links?: LinkType[],
    timezone?: string,
    createdDate: string,
    summary?: string,
    transparency?: TransparencyType,
    visibility?: VisibilityType,
    recurringEventId?: string,
    updatedAt: string,
    iCalUID?: string,
    htmlLink?: string,
    colorId?: string,
    creator?: CreatorType,
    organizer?: OrganizerType,
    endTimeUnspecified?: boolean,
    recurrence?: string[],
    attendeesOmitted?: boolean,
    extendedProperties?: ExtendedPropertiesType,
    hangoutLink?: string,
    guestsCanModify?: boolean,
    locked?: boolean,
    source?: SourceType,
    eventType?: string,
    privateCopy?: boolean,
    calendarId: string,
    backgroundColor?: string,
    foregroundColor?: string,
    useDefaultAlarms?: boolean,
    externalUser: boolean,
    meetingId?: string,
    eventId: string,
}

type date = string

type datetime = string

export type EventResourceType = {
    "kind": "calendar#event",
    "etag": EtagType,
    "id": string,
    "status": string,
    "htmlLink": string,
    "created": datetime,
    "updated": datetime,
    "summary": string,
    "description": string,
    "location": string,
    "colorId": string,
    "creator": {
        "id": string,
        "email": string,
        "displayName": string,
        "self": boolean
    },
    "organizer": {
        "id": string,
        "email": string,
        "displayName": string,
        "self": boolean
    },
    "start": {
        "date": date,
        "dateTime": datetime,
        "timeZone": string
    },
    "end": {
        "date": date,
        "dateTime": datetime,
        "timeZone": string
    },
    "endTimeUnspecified": boolean,
    "recurrence": string[],
    "recurringEventId": string,
    "originalStartTime": {
        "date": date,
        "dateTime": datetime,
        "timeZone": string
    },
    "transparency": string,
    "visibility": string,
    "iCalUID": string,
    "sequence": number,
    "attendees": {
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
    }[],
    "attendeesOmitted": boolean,
    extendedProperties?: {
        private?: {
            [key: string]: string;
        };
        shared?: {
            [key: string]: string;
        };
    } | null,
    "hangoutLink": string,
    "conferenceData"?: {
        "createRequest"?: {
            "requestId"?: string,
            "conferenceSolutionKey"?: {
                "type"?: string
            },
            "status"?: {
                "statusCode"?: string
            }
        },
        "entryPoints"?: {
            entryPointType: 'video' | 'phone' | 'sip' | 'more',
            uri?: string,
            label?: string,
            pin?: string,
            accessCode?: string,
            meetingCode?: string,
            passcode?: string,
            password?: string
        }[],
        "conferenceSolution"?: {
            "key"?: {
                "type"?: string
            },
            "name"?: string,
            "iconUri"?: string
        },
        "conferenceId"?: string,
        "signature"?: string,
        "notes"?: string,
    },
    "gadget"?: {
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
    } | null,
    "anyoneCanAddSelf": boolean,
    "guestsCanInviteOthers": boolean,
    "guestsCanModify": boolean,
    "guestsCanSeeOtherGuests": boolean,
    "privateCopy": boolean,
    "locked": boolean,
    "reminders": {
        "useDefault": boolean,
        "overrides": [
            {
                "method": string,
                "minutes": number
            }
        ]
    },
    "source": {
        "url": string,
        "title": string
    },
    "attachments": [
        {
            "fileUrl": string,
            "title": string,
            "mimeType": string,
            "iconLink": string,
            "fileId": string
        }
    ],
    "eventType": 'default' | 'outOfOffice' | 'focusTime'
}

export type HH = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23'
export type MM = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12'

export type Time = `${HH}:${MM}`

export type EventType = {
    id: string,
    userId: string,
    title?: string,
    startDate: string,
    endDate: string,
    allDay?: boolean,
    recurrenceRule?: RecurrenceRuleType,
    location?: LocationType,
    notes?: string,
    attachments?: AttachmentType[],
    links?: LinkType[],
    timezone?: string,
    createdDate: string,
    deleted: boolean,
    taskId?: string,
    taskType?: string,
    priority: number,
    followUpEventId?: string,
    isFollowUp: boolean,
    isPreEvent: boolean,
    isPostEvent: boolean,
    preEventId?: string,
    postEventId?: string,
    modifiable: boolean,
    forEventId?: string,
    conferenceId?: string,
    maxAttendees?: number,
    sendUpdates?: SendUpdatesType,
    anyoneCanAddSelf: boolean,
    guestsCanInviteOthers: boolean,
    guestsCanSeeOtherGuests: boolean,
    originalStartDate: string,
    originalAllDay: boolean,
    status?: string,
    summary?: string,
    transparency?: TransparencyType,
    visibility?: VisibilityType,
    recurringEventId?: string,
    updatedAt: string,
    iCalUID?: string,
    htmlLink?: string,
    colorId?: string,
    creator?: CreatorType,
    organizer?: OrganizerType,
    endTimeUnspecified?: boolean,
    recurrence?: string[],
    originalTimezone?: string,
    attendeesOmitted?: boolean,
    extendedProperties?: ExtendedPropertiesType,
    hangoutLink?: string,
    guestsCanModify?: boolean,
    locked?: boolean,
    source?: SourceType,
    eventType?: string,
    privateCopy?: boolean,
    calendarId: string,
    backgroundColor?: string,
    foregroundColor?: string,
    useDefaultAlarms?: boolean,
    positiveImpactScore?: number,
    negativeImpactScore?: number,
    positiveImpactDayOfWeek?: number,
    positiveImpactTime?: Time,
    negativeImpactDayOfWeek?: number,
    negativeImpactTime?: Time,
    preferredDayOfWeek?: number,
    preferredTime?: Time,
    isExternalMeeting?: boolean,
    isExternalMeetingModifiable?: boolean,
    isMeetingModifiable?: boolean,
    isMeeting?: boolean,
    dailyTaskList?: boolean,
    weeklyTaskList?: boolean,
    isBreak?: boolean,
    preferredStartTimeRange?: Time,
    preferredEndTimeRange?: Time,
    copyAvailability?: boolean,
    copyTimeBlocking?: boolean,
    copyTimePreference?: boolean,
    copyReminders?: boolean,
    copyPriorityLevel?: boolean,
    copyModifiable?: boolean,
    copyCategories?: boolean,
    copyIsBreak?: boolean,
    timeBlocking?: BufferTimeNumberType,
    userModifiedAvailability?: boolean,
    userModifiedTimeBlocking?: boolean,
    userModifiedTimePreference?: boolean,
    userModifiedReminders?: boolean,
    userModifiedPriorityLevel?: boolean,
    userModifiedCategories?: boolean,
    userModifiedModifiable?: boolean,
    userModifiedIsBreak?: boolean,
    hardDeadline?: string,
    softDeadline?: string,
    copyIsMeeting?: boolean,
    copyIsExternalMeeting?: boolean,
    userModifiedIsMeeting?: boolean,
    userModifiedIsExternalMeeting?: boolean,
    duration?: number,
    copyDuration?: boolean,
    userModifiedDuration?: boolean,
    method?: 'create' | 'update',
    unlink?: boolean,
    copyColor?: boolean,
    userModifiedColor?: boolean,
    byWeekDay?: string[],
    localSynced?: boolean,
    meetingId?: string,
    eventId: string,
}

export type AvailableSlot = {
    id: string,
    startDate: string,
    endDate: string,
    selected?: boolean,
}

export type AvailableSlotsByDate = {
    [key: string]: AvailableSlot[]
}

export type NotAvailableSlot = {
    startDate: string,
    endDate: string,
}

export type MeetingAssistPreferredTimeRangeType = {
    id: string,
    meetingId: string,
    dayOfWeek?: number,
    startTime: Time,
    endTime: Time,
    updatedAt: string,
    createdDate: string,
    hostId: string,
    attendeeId: string,
}

export type MeetingAssistPreferredDateRangeType = {
    id: string,
    meetingId: string,
    dayOfWeek?: number,
    startTime: string,
    endTime: string,
    updatedAt: string,
    createdDate: string,
    hostId: string,
    attendeeId: string,
}

type DayOfWeekIntType = 1 | 2 | 3 | 4 | 5 | 6 | 7

type StartTimeType = {
    day: DayOfWeekIntType,
    hour: number,
    minutes: number,
}

type EndTimeType = {
    day: DayOfWeekIntType,
    hour: number,
    minutes: number,
}

export type UserPreferenceType = {
    id: string,
    userId: string,
    reminders?: number[], // invite part
    followUp?: number[], // invite part
    isPublicCalendar?: boolean,
    publicCalendarCategories?: string[],
    startTimes?: StartTimeType[],
    endTimes?: EndTimeType[],
    copyAvailability?: boolean,
    copyTimeBlocking?: boolean,
    copyTimePreference?: boolean,
    copyReminders?: boolean,
    copyPriorityLevel?: boolean,
    copyModifiable?: boolean,
    copyCategories?: boolean,
    copyIsBreak?: boolean,
    maxWorkLoadPercent: number,
    minNumberOfBreaks: number,
    breakLength: number,
    breakColor?: string,
    backToBackMeetings: boolean,
    maxNumberOfMeetings: number,
    copyIsMeeting?: boolean,
    copyIsExternalMeeting?: boolean,
    copyColor?: boolean,
    updatedAt?: string,
    createdDate?: string,
    deleted: boolean
}

export type ScheduleAssistWithMeetingQueueBodyType = {
    userId: string,
    windowStartDate: string,
    windowEndDate: string,
    timezone: string,
}

export type CustomAvailableTimeType = {
    startTime: Time,
    endTime: Time,
    dayOfWeekInt: number,
}

export type MeetingAssistInviteType = {
    id: string,
    hostId: string,
    email: string,
    hostName?: string,
    meetingId: string,
    name: string,
    createdDate: string,
    updatedAt: string,
    userId?: string,
    response?: 'PENDING' | 'CANCELLED' | 'ATTENDING'
}

export type RecurrenceFrequencyType = 'daily' | 'weekly'
    | 'monthly' | 'yearly'

export type UserType = {
    id: string,
    name?: string,
    email?: string,
    updatedAt: string,
    createdDate: string,
    deleted: boolean
}

