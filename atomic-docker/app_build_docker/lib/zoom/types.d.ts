export type Internals = any;
export type InstanceCreationOptions = any;
export type MeetingTypeNumberType = 1 | 2 | 3 | 8;
export type MeetingTypeStringType = 'instant' | 'scheduled' | 'recurring_no_fixed' | 'recurring_fixed';
type DialInNumberType = {
    city: string;
    country: string;
    country_name: string;
    number: string;
    type: string;
};
type RoomType = {
    name: string;
    participants: string[];
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
type CustomKeyType = {
    key: string;
    value: string;
};
type GlobalDialInType = {
    city: string;
    country: string;
    country_name: string;
    number: string;
    type: string;
};
type InterpreterType = {
    email: string;
    languages: string[];
};
type TrackingFieldType = {
    field: string;
    value: string;
    visible: boolean;
};
export type CreateMeetingResponseType = {
    assistant_id: string;
    host_email: string;
    registration_url?: string;
    agenda: string;
    h323_password?: number;
    occurrences?: ZoomOccurrenceObjectType[];
    password?: string;
    pmi: number;
    pre_schedule: boolean;
    recurrence: ZoomRecurrenceObjectType;
    created_at: string;
    duration: number;
    host_id: string;
    id: number;
    join_url: string;
    settings: {
        alternative_hosts: string;
        approval_type: number;
        audio: string;
        auto_recording: string;
        close_registration: boolean;
        cn_meeting: boolean;
        enforce_login: boolean;
        enforce_login_domains: string;
        global_dial_in_countries: string[];
        global_dial_in_numbers: DialInNumberType[];
        breakout_room: {
            enable: boolean;
            rooms: RoomType[];
            calendar_type: 1 | 2;
            close_registration: boolean;
            contact_email: string;
            contact_name: string;
            custom_keys: CustomKeyType[];
            email_notification: boolean;
            encryption_type: string;
            focus_mode: boolean;
            global_dial_in_countries: string[];
            global_dial_in_numbers: GlobalDialInType[];
            host_video: boolean;
            jbh_time: number;
            join_before_host: boolean;
            language_interpretation: {
                enable: boolean;
                interpreters: InterpreterType[];
            };
            meeting_authentication: boolean;
            mute_upon_entry: boolean;
            participant_video: boolean;
            private_meeting: boolean;
            registrants_confirmation_email: boolean;
            registrants_email_notification: boolean;
            registration_type: number;
            show_share_button: boolean;
            use_pmi: boolean;
            waiting_room: boolean;
            watermark: boolean;
            host_save_video_order: boolean;
        };
    };
    start_time: string;
    start_url: string;
    status: string;
    timezone: string;
    topic: string;
    type: number;
    uuid: string;
    tracking_fields: TrackingFieldType[];
};
export type CreateZoomMeetObjectType = {
    startDate: string;
    timezone: string;
    agenda: string;
    duration: number;
    userId: string;
    contactName?: string;
    contactEmail?: string;
    meetingInvitees?: string[];
    privateMeeting?: boolean;
};
export type UpdateZoomMeetObjectType = {
    meetingId: number;
    startDate?: string;
    timezone?: string;
    agenda?: string;
    duration?: number;
    userId: string;
    contactName?: string;
    contactEmail?: string;
    meetingInvitees?: string[];
    privateMeeting?: boolean;
};
export type DeleteZoomMeetObjectType = {
    meetingId: number;
    userId: string;
    scheduleForReminder?: boolean;
    cancelMeetingReminder?: string;
};
export {};
