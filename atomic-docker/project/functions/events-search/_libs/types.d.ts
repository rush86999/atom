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
export type MonthType = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11;
export type DayType = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31;
export type DD = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23' | '24' | '25' | '26' | '27' | '28' | '29' | '30' | '31';
export type MM = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12';
export type MonthDayType = `--${MM}-${DD}`;
export type DayOfWeekType = 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
export type TimeSlotType = {
    dayOfWeek: DayOfWeekType;
    startTime: Time;
    endTime: Time;
    hostId: string;
    monthDay: MonthDayType;
};
export type WorkTimeType = {
    dayOfWeek: DayOfWeekType;
    startTime: Time;
    endTime: Time;
    userId: string;
    hostId: string;
};
export type MeetingAssistAttendeeType = {
    id: string;
    name?: string;
    hostId: string;
    userId: string;
    emails: EmailType[];
    contactId?: string;
    phoneNumbers?: PhoneNumberType[];
    imAddresses?: ImAddressType[];
    meetingId: string;
    createdDate: string;
    timezone?: string;
    updatedAt: string;
    externalAttendee: boolean;
    primaryEmail?: string;
};
export type appType = 'zoom' | 'google';
export type MeetingAssistType = {
    id: string;
    eventId?: string;
    userId: string;
    summary?: string;
    notes?: string;
    windowStartDate: string;
    windowEndDate: string;
    timezone?: string;
    location?: object;
    priority: number;
    enableConference: boolean;
    conferenceApp?: appType;
    sendUpdates?: 'all' | 'externalOnly' | 'none';
    guestsCanInviteOthers: boolean;
    transparency?: 'opaque' | 'transparent';
    visibility?: 'default' | 'public' | 'private';
    createdDate: string;
    updatedAt: string;
    colorId?: string;
    backgroundColor?: string;
    foregroundColor?: string;
    useDefaultAlarms?: boolean;
    reminders?: number[];
    cancelIfAnyRefuse?: boolean;
    enableHostPreferences?: boolean;
    enableAttendeePreferences?: boolean;
    attendeeCanModify?: boolean;
    startDate?: string;
    endDate?: string;
    attendeeCount?: number;
    expireDate?: string;
    attendeeRespondedCount: number;
    cancelled: boolean;
    duration: number;
    calendarId: string;
    bufferTime: BufferTimeNumberType;
    anyoneCanAddSelf: boolean;
    guestsCanSeeOtherGuests: boolean;
    minThresholdCount?: number;
    allowAttendeeUpdatePreferences?: boolean;
    guaranteeAvailability?: boolean;
};
export type RecurrenceRuleType = {
    frequency: string;
    endDate: string;
    occurrence?: number;
    interval: number;
    byWeekDay?: string[];
} | {
    frequency: string;
    endDate?: string;
    occurrence: number;
    interval: number;
    byWeekDay?: string[];
};
export type LocationType = {
    title: string;
    proximity?: string;
    radius?: number;
    coords?: {
        latitude?: number;
        longitude?: number;
    };
    address?: {
        houseNumber?: number;
        prefixDirection?: string;
        prefixType?: string;
        streetName?: string;
        streetType?: string;
        suffixDirection?: string;
        city?: string;
        state?: string;
        postalCode?: string;
        country?: string;
    };
};
export type LinkType = {
    title: string;
    link: string;
};
export type AttachmentType = {
    title: string;
    fileUrl: string;
    mimeType: string;
    iconLink: string;
    fileId: string;
};
export type SendUpdatesType = 'all' | 'externalOnly' | 'none';
export type TransparencyType = 'opaque' | 'transparent';
export type VisibilityType = 'default' | 'public' | 'private' | 'confidential';
export type CreatorType = {
    id?: string;
    email?: string;
    displayName?: string;
    self?: boolean;
};
export type OrganizerType = {
    id: string;
    email: string;
    displayName: string;
    self: boolean;
};
export type ExtendedPropertiesType = {
    private?: {
        keys?: string[];
        values?: string[];
    };
    shared?: {
        keys?: string[];
        values?: string[];
    };
};
export type SourceType = {
    title?: string;
    url?: string;
};
export type HH = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23';
export type Time = `${HH}:${MM}`;
export type BufferTimeNumberType = {
    beforeEvent: number;
    afterEvent: number;
};
export type MeetingAssistPreferredTimeRangeType = {
    id: string;
    meetingId: string;
    dayOfWeek?: number;
    startTime: Time;
    endTime: Time;
    updatedAt: string;
    createdDate: string;
    hostId: string;
    attendeeId: string;
};
export type EventType = {
    id: string;
    userId: string;
    title?: string;
    startDate: string;
    endDate: string;
    allDay?: boolean;
    recurrenceRule?: RecurrenceRuleType;
    location?: LocationType;
    notes?: string;
    attachments?: AttachmentType[];
    links?: LinkType[];
    timezone?: string;
    createdDate: string;
    deleted: boolean;
    taskId?: string;
    taskType?: string;
    priority: number;
    followUpEventId?: string;
    isFollowUp: boolean;
    isPreEvent: boolean;
    isPostEvent: boolean;
    preEventId?: string;
    postEventId?: string;
    modifiable: boolean;
    forEventId?: string;
    conferenceId?: string;
    maxAttendees?: number;
    sendUpdates?: SendUpdatesType;
    anyoneCanAddSelf: boolean;
    guestsCanInviteOthers: boolean;
    guestsCanSeeOtherGuests: boolean;
    originalStartDate: string;
    originalAllDay: boolean;
    status?: string;
    summary?: string;
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    recurringEventId?: string;
    updatedAt: string;
    iCalUID?: string;
    htmlLink?: string;
    colorId?: string;
    creator?: CreatorType;
    organizer?: OrganizerType;
    endTimeUnspecified?: boolean;
    recurrence?: string[];
    originalTimezone?: string;
    attendeesOmitted?: boolean;
    extendedProperties?: ExtendedPropertiesType;
    hangoutLink?: string;
    guestsCanModify?: boolean;
    locked?: boolean;
    source?: SourceType;
    eventType?: string;
    privateCopy?: boolean;
    calendarId: string;
    backgroundColor?: string;
    foregroundColor?: string;
    useDefaultAlarms?: boolean;
    positiveImpactScore?: number;
    negativeImpactScore?: number;
    positiveImpactDayOfWeek?: number;
    positiveImpactTime?: Time;
    negativeImpactDayOfWeek?: number;
    negativeImpactTime?: Time;
    preferredDayOfWeek?: number;
    preferredTime?: Time;
    isExternalMeeting?: boolean;
    isExternalMeetingModifiable?: boolean;
    isMeetingModifiable?: boolean;
    isMeeting?: boolean;
    dailyTaskList?: boolean;
    weeklyTaskList?: boolean;
    isBreak?: boolean;
    preferredStartTimeRange?: Time;
    preferredEndTimeRange?: Time;
    copyAvailability?: boolean;
    copyTimeBlocking?: boolean;
    copyTimePreference?: boolean;
    copyReminders?: boolean;
    copyPriorityLevel?: boolean;
    copyModifiable?: boolean;
    copyCategories?: boolean;
    copyIsBreak?: boolean;
    timeBlocking?: BufferTimeNumberType;
    userModifiedAvailability?: boolean;
    userModifiedTimeBlocking?: boolean;
    userModifiedTimePreference?: boolean;
    userModifiedReminders?: boolean;
    userModifiedPriorityLevel?: boolean;
    userModifiedCategories?: boolean;
    userModifiedModifiable?: boolean;
    userModifiedIsBreak?: boolean;
    hardDeadline?: string;
    softDeadline?: string;
    copyIsMeeting?: boolean;
    copyIsExternalMeeting?: boolean;
    userModifiedIsMeeting?: boolean;
    userModifiedIsExternalMeeting?: boolean;
    duration?: number;
    copyDuration?: boolean;
    userModifiedDuration?: boolean;
    method?: 'create' | 'update';
    unlink?: boolean;
    copyColor?: boolean;
    userModifiedColor?: boolean;
    byWeekDay?: string[];
    localSynced?: boolean;
    meetingId?: string;
    eventId: string;
};
export type MeetingAssistEventType = {
    id: string;
    attendeeId: string;
    startDate: string;
    endDate: string;
    allDay?: boolean;
    recurrenceRule?: RecurrenceRuleType;
    location?: LocationType;
    notes?: string;
    attachments?: AttachmentType[];
    links?: LinkType[];
    timezone?: string;
    createdDate: string;
    summary?: string;
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    recurringEventId?: string;
    updatedAt: string;
    iCalUID?: string;
    htmlLink?: string;
    colorId?: string;
    creator?: CreatorType;
    organizer?: OrganizerType;
    endTimeUnspecified?: boolean;
    recurrence?: string[];
    attendeesOmitted?: boolean;
    extendedProperties?: ExtendedPropertiesType;
    hangoutLink?: string;
    guestsCanModify?: boolean;
    locked?: boolean;
    source?: SourceType;
    eventType?: string;
    privateCopy?: boolean;
    calendarId: string;
    backgroundColor?: string;
    foregroundColor?: string;
    useDefaultAlarms?: boolean;
    externalUser: boolean;
    meetingId?: string;
};
export type EventPlusType = EventType & {
    preferredTimeRanges?: PreferredTimeRangeType[];
};
export type EventMeetingPlusType = EventType & {
    preferredTimeRanges?: MeetingAssistPreferredTimeRangeType[];
};
export type PreferredTimeRangeType = {
    id: string;
    eventId: string;
    dayOfWeek?: number;
    startTime: Time;
    endTime: Time;
    updatedAt: string;
    createdDate: string;
    userId: string;
};
export type RemindersForEventType = {
    eventId: string;
    reminders: ReminderType[];
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
export type BufferTimeObjectType = {
    beforeEvent?: EventPlusType;
    afterEvent?: EventPlusType;
};
export type ValuesToReturnForBufferEventsType = {
    beforeEvent?: EventPlusType;
    afterEvent?: EventPlusType;
    newEvent: EventMeetingPlusType;
};
type DayOfWeekIntType = 1 | 2 | 3 | 4 | 5 | 6 | 7;
type StartTimeType = {
    day: DayOfWeekIntType;
    hour: number;
    minutes: number;
};
type EndTimeType = {
    day: DayOfWeekIntType;
    hour: number;
    minutes: number;
};
export type UserPreferenceType = {
    id: string;
    userId: string;
    reminders?: number[];
    followUp?: number[];
    isPublicCalendar?: boolean;
    publicCalendarCategories?: string[];
    startTimes?: StartTimeType[];
    endTimes?: EndTimeType[];
    copyAvailability?: boolean;
    copyTimeBlocking?: boolean;
    copyTimePreference?: boolean;
    copyReminders?: boolean;
    copyPriorityLevel?: boolean;
    copyModifiable?: boolean;
    copyCategories?: boolean;
    copyIsBreak?: boolean;
    maxWorkLoadPercent: number;
    minNumberOfBreaks: number;
    breakLength: number;
    breakColor?: string;
    backToBackMeetings: boolean;
    maxNumberOfMeetings: number;
    copyIsMeeting?: boolean;
    copyIsExternalMeeting?: boolean;
    copyColor?: boolean;
    updatedAt?: string;
    createdDate?: string;
    deleted: boolean;
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
export type UserPlannerRequestBodyType = {
    id: string;
    hostId: string;
    maxWorkLoadPercent: number;
    backToBackMeetings: boolean;
    maxNumberOfMeetings: number;
    minNumberOfBreaks: number;
    workTimes: WorkTimeType[];
};
export type PreferredTimeRangePlannerRequestBodyType = {
    dayOfWeek?: DayOfWeekType;
    startTime: Time;
    endTime: Time;
    eventId: string;
    userId: string;
    hostId: string;
};
export type EventParentPlannerRequestBodyType = {
    id: string;
    userId: string;
    hostId: string;
    preferredTimeRanges?: PreferredTimeRangePlannerRequestBodyType[];
};
export type EventPartPlannerRequestBodyType = {
    groupId: string;
    part: number;
    lastPart: number;
    eventId: string;
    startDate: string;
    endDate: string;
    taskId?: string;
    softDeadline?: string;
    hardDeadline?: string;
    userId: string;
    hostId: string;
    meetingId?: string;
    user: UserPlannerRequestBodyType;
    priority: number;
    isPreEvent?: boolean;
    isPostEvent?: boolean;
    forEventId?: string;
    positiveImpactScore?: number;
    negativeImpactScore?: number;
    positiveImpactDayOfWeek?: DayOfWeekType;
    positiveImpactTime?: Time;
    negativeImpactDayOfWeek?: DayOfWeekType;
    negativeImpactTime?: Time;
    modifiable?: boolean;
    preferredDayOfWeek?: DayOfWeekType;
    preferredTime?: Time;
    isMeeting?: boolean;
    isExternalMeeting?: boolean;
    isExternalMeetingModifiable?: boolean;
    isMeetingModifiable?: boolean;
    dailyTaskList: boolean;
    weeklyTaskList: boolean;
    gap: boolean;
    preferredStartTimeRange?: Time;
    preferredEndTimeRange?: Time;
    totalWorkingHours?: number;
    recurringEventId?: string;
    event: EventParentPlannerRequestBodyType;
};
export type InitialEventPartType = {
    id: string;
    groupId: string;
    eventId: string;
    userId: string;
    title?: string;
    startDate: string;
    endDate: string;
    allDay?: boolean;
    recurrenceRule?: RecurrenceRuleType;
    location?: LocationType;
    notes?: string;
    attachments?: AttachmentType[];
    links?: LinkType[];
    timezone?: string;
    createdDate: string;
    deleted: boolean;
    taskId?: string;
    taskType?: string;
    priority: number;
    followUpEventId?: string;
    isFollowUp: boolean;
    isPreEvent: boolean;
    isPostEvent: boolean;
    preEventId?: string;
    postEventId?: string;
    modifiable: boolean;
    forEventId?: string;
    conferenceId?: string;
    maxAttendees?: number;
    sendUpdates?: SendUpdatesType;
    anyoneCanAddSelf: boolean;
    guestsCanInviteOthers: boolean;
    guestsCanSeeOtherGuests: boolean;
    originalStartDate: string;
    originalAllDay: boolean;
    status?: string;
    summary?: string;
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    recurringEventId?: string;
    updatedAt: string;
    iCalUID?: string;
    htmlLink?: string;
    colorId?: string;
    creator?: CreatorType;
    organizer?: OrganizerType;
    endTimeUnspecified?: boolean;
    recurrence?: string[];
    originalTimezone?: string;
    attendeesOmitted?: boolean;
    extendedProperties?: ExtendedPropertiesType;
    hangoutLink?: string;
    guestsCanModify?: boolean;
    locked?: boolean;
    source?: SourceType;
    eventType?: string;
    privateCopy?: boolean;
    calendarId: string;
    backgroundColor?: string;
    foregroundColor?: string;
    useDefaultAlarms?: boolean;
    positiveImpactScore?: number;
    negativeImpactScore?: number;
    positiveImpactDayOfWeek?: number;
    positiveImpactTime?: Time;
    negativeImpactDayOfWeek?: number;
    negativeImpactTime?: Time;
    preferredDayOfWeek?: number;
    preferredTime?: Time;
    isExternalMeeting?: boolean;
    isExternalMeetingModifiable?: boolean;
    isMeetingModifiable?: boolean;
    isMeeting?: boolean;
    dailyTaskList?: boolean;
    weeklyTaskList?: boolean;
    isBreak?: boolean;
    preferredStartTimeRange?: Time;
    preferredEndTimeRange?: Time;
    copyAvailability?: boolean;
    copyTimeBlocking?: boolean;
    copyTimePreference?: boolean;
    copyReminders?: boolean;
    copyPriorityLevel?: boolean;
    copyModifiable?: boolean;
    copyCategories?: boolean;
    copyIsBreak?: boolean;
    timeBlocking?: BufferTimeNumberType;
    userModifiedAvailability?: boolean;
    userModifiedTimeBlocking?: boolean;
    userModifiedTimePreference?: boolean;
    userModifiedReminders?: boolean;
    userModifiedPriorityLevel?: boolean;
    userModifiedCategories?: boolean;
    userModifiedModifiable?: boolean;
    userModifiedIsBreak?: boolean;
    hardDeadline?: string;
    softDeadline?: string;
    copyIsMeeting?: boolean;
    copyIsExternalMeeting?: boolean;
    userModifiedIsMeeting?: boolean;
    userModifiedIsExternalMeeting?: boolean;
    duration?: number;
    copyDuration?: boolean;
    userModifiedDuration?: boolean;
    method?: 'create' | 'update';
    unlink?: boolean;
    copyColor?: boolean;
    userModifiedColor?: boolean;
    byWeekDay?: string[];
    localSynced?: boolean;
    part: number;
    lastPart: number;
    hostId: string;
    meetingId?: string;
};
export type InitialEventPartTypePlus = InitialEventPartType & {
    preferredTimeRanges?: PreferredTimeRangeType[];
};
export type ReturnBodyForHostForOptaplannerPrepType = {
    userIds: string[];
    hostId: string;
    eventParts: EventPartPlannerRequestBodyType[];
    allEvents: EventPlusType[];
    newBufferTime?: BufferTimeObjectType;
    newReminder?: RemindersForEventType;
    breaks: EventPlusType[];
    oldEvents: EventPlusType[];
    timeslots: TimeSlotType[];
    userList: UserPlannerRequestBodyType[];
};
export type ReturnBodyForAttendeeForOptaplannerPrepType = {
    userId: string;
    hostId: string;
    eventParts: EventPartPlannerRequestBodyType[];
    allEvents: EventPlusType[];
    oldEvents: EventPlusType[];
    timeslots: TimeSlotType[];
    userPlannerRequestBody: UserPlannerRequestBodyType;
};
export type ReturnBodyForExternalAttendeeForOptaplannerPrepType = {
    userIds: string[];
    hostId: string;
    eventParts: EventPartPlannerRequestBodyType[];
    allEvents: EventPlusType[];
    oldAttendeeEvents: MeetingAssistEventType[];
    timeslots: TimeSlotType[];
    userList: UserPlannerRequestBodyType[];
};
export type PlannerRequestBodyType = {
    singletonId: string;
    hostId: string;
    timeslots: TimeSlotType[];
    userList: UserPlannerRequestBodyType[];
    eventParts: EventPartPlannerRequestBodyType[];
    fileKey: string;
    delay: number;
    callBackUrl: string;
};
export type FreemiumType = {
    id: string;
    userId: string;
    usage: number;
    period: 'MONTH' | 'YEAR' | 'DAY';
    updatedAt: string;
    createdDate: string;
};
export type ReturnValueForEachMeetingAssistType = {
    events: EventType[];
    meetingAssistEvents: MeetingAssistEventType[];
    meetingEventsPlus: EventMeetingPlusType[];
    internalAttendees: MeetingAssistAttendeeType[];
    externalAttendees?: MeetingAssistAttendeeType[];
};
type EtagType = string;
type DatetimeType = string;
type DateType = string;
export type EventResourceType = {
    kind: 'calendar#event';
    etag: EtagType;
    id: string;
    status: string;
    htmlLink: string;
    created: DatetimeType;
    updated: DatetimeType;
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
        date: DateType;
        dateTime: DatetimeType;
        timeZone: string;
    };
    end: {
        date: DateType;
        dateTime: DatetimeType;
        timeZone: string;
    };
    endTimeUnspecified: boolean;
    recurrence: string[];
    recurringEventId: string;
    originalStartTime: {
        date: DateType;
        dateTime: DatetimeType;
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
         * - needsAction - The attendee has not responded to the invitation.
         * - declined - The attendee has declined the invitation.
         * - tentative - The attendee has tentatively accepted the invitation.
         * - accepted - The attendee has accepted the invitation.
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
type OverrideType = {
    method?: 'email' | 'popup';
    minutes?: number;
};
export type OverrideTypes = OverrideType[];
export type GoogleReminderType = {
    overrides: OverrideTypes;
    useDefault: boolean;
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
export type GoogleExtendedPropertiesType = {
    private?: object;
    shared?: object;
};
export type GoogleTransparencyType = 'opaque' | 'transparent';
export type GoogleVisibilityType = 'default' | 'public' | 'private' | 'confidential';
export type GoogleSourceType = {
    title?: string;
    url?: string;
};
export type GoogleAttachmentType = {
    title: string;
    fileUrl: string;
    mimeType: string;
    iconLink: string;
    fileId: string;
};
export type GoogleEventType1 = 'default' | 'outOfOffice' | 'focusTime';
export type CalendarWebhookType = {
    calendarId: string;
    createdDate: string;
    expiration?: string;
    id: string;
    resourceId: string;
    resourceUri: string;
    token: string;
    updatedAt: string;
    userId: string;
    calendarIntegrationId: string;
};
type EventSourceType = {
    userId: string;
};
export type EmailKnwSourceType = {
    base_url: string;
    userId: string;
    text: string;
};
export type AgentKnwSourceType = {
    base_url: string;
    agent_id: string;
    userId: string;
    text: string;
};
export type OpenSearchResponseBodyType = {
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
                _source: EventSourceType | EmailKnwSourceType | AgentKnwSourceType;
            }
        ];
    };
};
export type EventTriggerType = {
    id: string;
    userId: string;
    name: string;
    resource: string;
    resourceId: string;
    updatedAt?: string;
    createdAt?: string;
};
export type OpenAllEventSourceType = {
    userId: string;
    start_date: string;
    end_date: string;
    title: string;
};
export type OpenSearchGetResponseBodyType = {
    _index: string;
    _type: string;
    _id: string;
    _score: number;
    _source: OpenAllEventSourceType;
};
export {};
