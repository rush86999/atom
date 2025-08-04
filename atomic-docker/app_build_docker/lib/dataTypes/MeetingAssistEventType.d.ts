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
    eventId: string;
};
