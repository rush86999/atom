

export type EmailType = {
    primary: boolean,
    value: string,
    type: string,
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
export type MonthType = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11
// 1 - 31
export type DayType = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | '18' | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31

export type DD = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23' | '24' | '25' | '26' | '27' | '28' | '29' | '30' | '31'

export type MM = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12';

export type SS = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23' | '24' | '25' | '26' | '27' | '28' | '29' | '30' | '31' | '32' | '33' | '34' | '35' | '36' | '37' | '38' | '39' | '40' | '41' | '42' | '43' | '44' | '45' | '46' | '47' | '48' | '49' | '50' | '51' | '52' | '53' | '54' | '55' | '56' | '57' | '58' | '59';

export type MonthDayType = `--${MM}-${DD}`

export type DayOfWeekType = 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY'

export type TimeSlotType = {
    dayOfWeek: DayOfWeekType,
    startTime: Time,
    endTime: Time,
    hostId: string,
    monthDay: MonthDayType,
    date: string // Added: "YYYY-MM-DD"
}

export type WorkTimeType = { dayOfWeek: DayOfWeekType, startTime: Time, endTime: Time, userId: string, hostId: string }


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

export type appType = 'zoom' | 'google'

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
    cancelIfAnyRefuse?: boolean,
    enableHostPreferences?: boolean,
    enableAttendeePreferences?: boolean,
    attendeeCanModify?: boolean,
    startDate?: string,
    endDate?: string,
    attendeeCount?: number,
    expireDate?: string,
    attendeeRespondedCount: number,
    cancelled: boolean,
    duration: number,
    calendarId: string,
    bufferTime: BufferTimeNumberType,
    anyoneCanAddSelf: boolean,
    guestsCanSeeOtherGuests: boolean,
    minThresholdCount?: number,
    allowAttendeeUpdatePreferences?: boolean,
    guaranteeAvailability?: boolean,
    frequency?: 'weekly' | 'monthly',
    interval?: number,
    until?: string, // no timezone
    originalMeetingId?: string,
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

export type HH = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23'

export type Time = `${HH}:${MM}:${SS}`

export type BufferTimeNumberType = {
    beforeEvent: number
    afterEvent: number
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

export type EventPlusType = EventType & {
    preferredTimeRanges?: PreferredTimeRangeType[],
}

export type EventMeetingPlusType = EventType & {
    preferredTimeRanges?: MeetingAssistPreferredTimeRangeType[],
}

export type PreferredTimeRangeType = {
    id: string,
    eventId: string,
    dayOfWeek?: number,
    startTime: Time,
    endTime: Time,
    updatedAt: string,
    createdDate: string,
    userId: string,
}

export type RemindersForEventType = {
    eventId: string,
    reminders: ReminderType[],
}

export type ReminderType = {
    id: string,
    userId: string,
    eventId: string,
    reminderDate?: string,
    timezone?: string,
    minutes?: number,
    useDefault?: boolean,
    updatedAt: string,
    createdDate: string,
    deleted: boolean
}

export type BufferTimeObjectType = {
    beforeEvent?: EventPlusType;
    afterEvent?: EventPlusType;
}

export type ValuesToReturnForBufferEventsType = {
    beforeEvent?: EventPlusType,
    afterEvent?: EventPlusType,
    newEvent: EventMeetingPlusType,
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

type DefaultReminder = {
    method: string,
    minutes: number,
}

export type CalendarType = {
    id: string,
    title?: string,
    backgroundColor?: string,
    foregroundColor?: string,
    colorId?: string,
    account?: object,
    accessLevel?: string,
    resource?: string,
    modifiable?: boolean,
    defaultReminders?: DefaultReminder[],
    // weird behavior by enabling primary here commented out for now
    // primary?: boolean,
    globalPrimary?: boolean,
    pageToken?: string,
    syncToken?: string,
    deleted: boolean,
    createdDate: string,
    updatedAt: string,
    userId: string,
}



export type UserPlannerRequestBodyType = {
    id: string, // UUID
    hostId: string,
    maxWorkLoadPercent: number,
    backToBackMeetings: boolean,
    maxNumberOfMeetings: number,
    minNumberOfBreaks: number,
    workTimes: WorkTimeType[],
}

export type PreferredTimeRangePlannerRequestBodyType = {
    dayOfWeek?: DayOfWeekType,
    startTime: Time,
    endTime: Time,
    eventId: string,
    userId: string,
    hostId: string,
}

export type EventParentPlannerRequestBodyType = {
    id: string,
    userId: string,
    hostId: string,
    preferredTimeRanges?: PreferredTimeRangePlannerRequestBodyType[],
    eventType: string // Added
}


export type EventPartPlannerRequestBodyType = {
    groupId: string,
    part: number,
    lastPart: number,
    meetingPart: number,
    meetingLastPart: number,
    eventId: string,
    startDate: string,
    endDate: string,
    taskId?: string,
    softDeadline?: string,
    hardDeadline?: string,
    userId: string,
    hostId: string,
    meetingId?: string,
    user: UserPlannerRequestBodyType,
    priority: number,
    isPreEvent?: boolean,
    isPostEvent?: boolean,
    forEventId?: string,
    positiveImpactScore?: number,
    negativeImpactScore?: number,
    positiveImpactDayOfWeek?: DayOfWeekType,
    positiveImpactTime?: Time,
    negativeImpactDayOfWeek?: DayOfWeekType,
    negativeImpactTime?: Time,
    modifiable?: boolean,
    preferredDayOfWeek?: DayOfWeekType,
    preferredTime?: Time,
    isMeeting?: boolean,
    isExternalMeeting?: boolean,
    isExternalMeetingModifiable?: boolean,
    isMeetingModifiable?: boolean,
    dailyTaskList: boolean,
    weeklyTaskList: boolean,
    gap: boolean,
    preferredStartTimeRange?: Time,
    preferredEndTimeRange?: Time,
    totalWorkingHours?: number,
    recurringEventId?: string,
    event: EventParentPlannerRequestBodyType,
}

export type InitialEventPartType = {
    id: string,
    groupId: string,
    eventId: string,
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
    part: number,
    lastPart: number,
    hostId: string,
    meetingId?: string,
    meetingPart: number, 
    meetingLastPart: number,
}

export type InitialEventPartTypePlus = InitialEventPartType & { preferredTimeRanges?: PreferredTimeRangeType[] }


export type ReturnBodyForHostForOptaplannerPrepType = {
    userId: string,
    hostId: string,
    eventParts: EventPartPlannerRequestBodyType[],
    allEvents: EventPlusType[],
    breaks: EventPlusType[],
    oldEvents: EventPlusType[],
    timeslots: TimeSlotType[],
    userPlannerRequestBody: UserPlannerRequestBodyType,
}

export type ReturnBodyForAttendeeForOptaplannerPrepType = {
    userIds: string[],
    hostId: string,
    eventParts: EventPartPlannerRequestBodyType[],
    allEvents: EventPlusType[],
    breaks: EventPlusType[],
    oldEvents: EventPlusType[],
    timeslots: TimeSlotType[],
    userList: UserPlannerRequestBodyType[],
}

export type ReturnBodyForExternalAttendeeForOptaplannerPrepType = {
    userIds: string[],
    hostId: string,
    eventParts: EventPartPlannerRequestBodyType[],
    allEvents: EventPlusType[],
    oldAttendeeEvents: MeetingAssistEventType[],
    timeslots: TimeSlotType[],
    userList: UserPlannerRequestBodyType[],
}

export type PlannerRequestBodyType = {
    singletonId: string,
    hostId: string,
    timeslots: TimeSlotType[],
    userList: UserPlannerRequestBodyType[],
    eventParts: EventPartPlannerRequestBodyType[],
    fileKey: string,
    delay: number,
    callBackUrl: string,
}

export type FreemiumType = {
    id: string,
    userId: string,
    usage: number,
    period: 'MONTH' | 'YEAR' | 'DAY',
    updatedAt: string,
    createdDate: string,
}

export type ReturnValueForEachMeetingAssistType = {
    events: EventType[],
    meetingAssistEvents: MeetingAssistEventType[],
    meetingEventsPlus: EventMeetingPlusType[],
    internalAttendees: MeetingAssistAttendeeType[],
    externalAttendees?: MeetingAssistAttendeeType[],
}

export type ReturnValueForEachFutureMeetingAssistType = {
    events: EventType[],
    meetingAssistEvents: MeetingAssistEventType[],
    newMeetingEventPlus: EventMeetingPlusType[],
    internalAttendees: MeetingAssistAttendeeType[],
    externalAttendees?: MeetingAssistAttendeeType[],
}
