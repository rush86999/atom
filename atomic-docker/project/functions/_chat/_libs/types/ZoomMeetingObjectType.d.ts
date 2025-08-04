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
