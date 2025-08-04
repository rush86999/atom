import { BufferTimeNumberType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';
import { AppType, MutatedCalendarExtractedJSONAttendeeType } from '@chat/_libs/types/UserInputToJSONType';
import TimePreferenceType from '@chat/_libs/types/TimePreferenceType';
import { TransparencyType } from '@chat/_libs/types/EventType';
import { VisibilityType } from 'aws-sdk/clients/appstream';
import ByMonthDayType from '@chat/_libs/types/ByMonthDayType';
type MethodType = 'create-event-forward';
export type ScheduleMeetingType = {
    userId: string;
    timezone: string;
    title: string;
    attendees: MutatedCalendarExtractedJSONAttendeeType[];
    method: MethodType;
    duration?: number;
    description?: string;
    conferenceApp?: AppType;
    startDate: string;
    bufferTime?: BufferTimeNumberType;
    reminders?: number[];
    priority?: number;
    timePreferences?: TimePreferenceType[];
    location?: string;
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    recur?: {
        frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
        endDate?: string;
        occurrence?: number;
        interval: number;
        byWeekDay?: DayOfWeekType[];
        ByMonthDay?: ByMonthDayType[];
    };
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
        weekly_days: string;
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
export {};
