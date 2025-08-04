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
export type MeetingAssistAttendeeType = {
    id: string;
    name?: string;
    hostId: string;
    userId: string;
    emails?: EmailType[];
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
