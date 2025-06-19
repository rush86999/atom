CREATE TABLE Meeting_Assist_External_Attendee_Preference (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_assist_id UUID NOT NULL,
    meeting_assist_attendee_id UUID NOT NULL,
    preference_token TEXT UNIQUE NOT NULL,
    token_expires_at TIMESTAMPTZ NOT NULL,
    preferred_start_datetime TIMESTAMPTZ NOT NULL,
    preferred_end_datetime TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT fk_meeting_assist
        FOREIGN KEY(meeting_assist_id)
        REFERENCES Meeting_Assist(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_meeting_assist_attendee
        FOREIGN KEY(meeting_assist_attendee_id)
        REFERENCES Meeting_Assist_Attendee(id)
        ON DELETE CASCADE,

    CONSTRAINT check_preferred_time_order
        CHECK (preferred_end_datetime > preferred_start_datetime)
);

CREATE INDEX idx_ma_ext_pref_meeting_assist_id ON Meeting_Assist_External_Attendee_Preference(meeting_assist_id);
CREATE INDEX idx_ma_ext_pref_attendee_id ON Meeting_Assist_External_Attendee_Preference(meeting_assist_attendee_id);
CREATE INDEX idx_ma_ext_pref_preference_token ON Meeting_Assist_External_Attendee_Preference(preference_token);
