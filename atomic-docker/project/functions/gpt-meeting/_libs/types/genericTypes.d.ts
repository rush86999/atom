export type SNSMessageHeaderType = {
    name: string;
    value: string;
};
export type SNSMessageRecordType = {
    notificationType: 'Received';
    mail: {
        timestamp: string;
        source: string;
        messageId: string;
        destination: string[];
        headersTruncated: boolean;
        headers: SNSMessageHeaderType[];
        commonHeaders: {
            returnPath: string;
            from: string[];
            date: string;
            to: string[];
            messageId: string;
            subject: string;
        };
    };
    receipt: {
        timestamp: string;
        processingTimeMillis: number;
        recipients: string[];
        spamVerdict: {
            status: string;
        };
        virusVerdict: {
            status: string;
        };
        spfVerdict: {
            status: string;
        };
        dkimVerdict: {
            status: string;
        };
        dmarcVerdict: {
            status: string;
        };
        action: {
            type: 'SNS';
            topicArn: string;
            encoding: string;
        };
    };
    content: string;
};
export type SNSRecordType = {
    EventSource: 'aws:sns';
    EventVersion: '1.0';
    Sns: {
        Type: 'Notification';
        MessageId: string;
        TopicArn: string;
        Subject: string;
        Message: string;
        Timestamp: string;
    };
};
export type SNSRecordsType = {
    Records: SNSRecordType[];
};
export type AppType = 'zoom' | 'google';
export type MeetingUrlQueryParamsAttachmentType = {
    title: string;
    fileUrl: string;
};
export type MeetingUrlQueryParamsType = {
    userId: string;
    timezone: string;
    enableConference: 'true' | 'false';
    conferenceApp?: AppType;
    useDefaultAlarms?: 'true' | 'false';
    reminders?: string[];
    attendeeEmails: string[];
    duration: string;
    calendarId: string;
    startTime: string;
    name: string;
    primaryEmail: string;
    sendUpdates?: SendUpdatesType;
    anyoneCanAddSelf: 'true' | 'false';
    guestsCanInviteOthers: 'true' | 'false';
    guestsCanModify?: 'true' | 'false';
    guestsCanSeeOtherGuests: 'true' | 'false';
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    attachments?: MeetingUrlQueryParamsAttachmentType[];
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
export type GoogleResType = {
    id: string;
    googleEventId: string;
    generatedId: string;
    calendarId: string;
    generatedEventId: string;
};
export type UserOpenAIType = {
    userId: string;
    key: string;
    id: string;
};
export type isMeetingScheduledObjectType = {
    time_provided: boolean;
};
export type ExtractDateTimeObjectType = {
    meeting_time: string;
};
export type SummaryAndNotesObjectType = {
    summary: string;
    notes: string;
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
export type GoogleAttachmentType = {
    title?: string;
    fileUrl: string;
    mimeType?: string;
    iconLink?: string;
    fileId?: string;
};
export type LinkType = {
    title: string;
    link: string;
};
export type GoogleEventType1 = 'default' | 'outOfOffice' | 'focusTime';
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
export type GoogleSourceType = {
    title?: string;
    url?: string;
};
export type MM = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12';
export type HH = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23';
export type Time = `${HH}:${MM}`;
export type BufferTimeNumberType = {
    beforeEvent: number;
    afterEvent: number;
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
    attachments?: GoogleAttachmentType[];
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
    source?: GoogleSourceType;
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
export type ConferenceNameType = 'Zoom Meeting' | 'Google Meet';
export type ParameterType = {
    keys: string[];
    values: string[];
};
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
export type ConferenceType = {
    id: string;
    userId: string;
    calendarId: string;
    app: AppType;
    requestId?: string;
    type?: string;
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
    isHost: boolean;
};
export type CreateGoogleEventResponseType = {
    id: string;
    googleEventId: string;
    generatedId: string;
    calendarId: string;
    generatedEventId: string;
};
export type CreateZoomMeetingRequestBodyType = {
    agenda?: string;
    default_password?: boolean;
    duration?: number;
    password?: string;
    pre_schedule?: boolean;
    recurrence?: {
        end_date_time: string;
        end_times: number;
        monthly_day: number;
        monthly_week: number;
        monthly_week_day: number;
        repeat_interval: number;
        type: number;
        weekly_days: number;
    };
    schedule_for?: string;
    settings?: {
        additional_data_center_regions?: string[];
        allow_multiple_devices?: boolean;
        alternative_hosts?: string;
        alternative_hosts_email_notification?: boolean;
        approval_type?: number;
        approved_or_denied_countries_or_regions?: {
            approved_list?: string[];
            denied_list?: string[];
            enable?: boolean;
            method?: string;
        };
        audio?: string;
        authentication_domains?: string;
        authentication_exception?: {
            email: string;
            name: string;
        }[];
        authentication_option?: string;
        auto_recording?: string;
        breakout_room?: {
            enable: boolean;
            rooms: [
                {
                    name: string;
                    participants: string[];
                }
            ];
        };
        calendar_type?: 1 | 2;
        close_registration?: boolean;
        contact_email?: string;
        contact_name: string;
        email_notification?: boolean;
        encryption_type?: string;
        focus_mode?: boolean;
        global_dial_in_countries?: string[];
        host_video?: boolean;
        jbh_time?: 0 | 5 | 10;
        join_before_host?: boolean;
        language_interpretation?: {
            enable: boolean;
            interpreters: {
                email: string;
                languages: string;
            }[];
        };
        meeting_authentication?: boolean;
        meeting_invitees?: {
            email: string;
        }[];
        mute_upon_entry?: boolean;
        participant_video?: boolean;
        private_meeting?: boolean;
        registrants_confirmation_email?: boolean;
        registrants_email_notification?: boolean;
        registration_type?: 1 | 2 | 3;
        show_share_button?: boolean;
        use_pmi?: boolean;
        waiting_room?: boolean;
        watermark?: boolean;
        host_save_video_order?: boolean;
        alternative_host_update_polls?: boolean;
    };
    start_time?: string;
    template_id?: string;
    timezone?: string;
    topic?: string;
    tracking_fields?: {
        field: string;
        value: string;
    }[];
    type?: 1 | 2 | 3 | 8;
};
export type ZoomOccurrenceObjectType = {
    duration: number;
    occurrence_id: number;
    start_time: string;
    status: string;
};
export type ZoomRecurrenceObjectType = {
    end_date_time: string;
    end_times: number;
    monthly_day: number;
    monthly_week: number;
    monthly_week_day: number;
    repeat_interval: number;
    type: number;
    weekly_days: number;
};
export type ZoomMeetingObjectType = {
    assistant_id: string;
    host_email: string;
    id: number;
    registration_url?: string;
    agenda: string;
    created_at: string;
    duration: number;
    h323_password?: number;
    join_url: string;
    occurrences?: ZoomOccurrenceObjectType[];
    password?: string;
    pmi: number;
    pre_schedule: boolean;
    recurrence: ZoomRecurrenceObjectType;
    settings: object;
    start_time: string;
    start_url: string;
    timezone: string;
    topic: string;
    tracking_fields: object[];
    type: number;
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
export type AttendeeEmailType = {
    primary: boolean;
    value: string;
    type?: string;
    displayName?: string;
};
export type AttendeePhoneNumberType = {
    primary: boolean;
    value: string;
    type?: string;
};
export type AttendeeImAddressType = {
    primary: boolean;
    username: string;
    service: string;
    type?: string;
};
export type AttendeeType = {
    id: string;
    userId: string;
    name?: string;
    contactId?: string;
    emails: AttendeeEmailType[];
    phoneNumbers?: AttendeePhoneNumberType[];
    imAddresses?: AttendeeImAddressType[];
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
export {};
