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
  clientType?: 'ios' | 'android' | 'web';
  expiresAt?: string;
  updatedAt: string;
  createdDate: string;
  pageToken?: string;
  syncToken?: string;
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
      calendar_type: 1 | 2; // 1 - outlook 2 - google
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

export type GetZoomMeetObjectType = {
  meetingId: number;
  userId: string;
};

export type DeleteZoomMeetObjectType = {
  meetingId: number;
  userId: string;
  scheduleForReminder?: boolean;
  cancelMeetingReminder?: boolean;
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

export type CreateZoomMeetingRequestBodyType = {
  agenda?: string;
  default_password?: boolean;
  duration?: number;
  password?: string;
  pre_schedule?: boolean;
  recurrence?: {
    end_date_time: string; // utc format date
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
        },
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
  start_time?: string; // date utc format
  template_id?: string;
  timezone?: string;
  topic?: string;
  tracking_fields?: {
    field: string;
    value: string;
  }[];
  type?: 1 | 2 | 3 | 8;
};
