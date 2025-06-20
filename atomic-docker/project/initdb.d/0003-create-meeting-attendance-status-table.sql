-- Create the meeting_attendance_status table
CREATE TABLE IF NOT EXISTS meeting_attendance_status (
    task_id TEXT PRIMARY KEY,
    user_id TEXT,
    platform TEXT,
    meeting_identifier TEXT,
    status_timestamp TIMESTAMPTZ NOT NULL,
    current_status_message TEXT NOT NULL,
    final_notion_page_url TEXT,
    error_details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Optional: Add an index on user_id for faster lookups if needed
CREATE INDEX IF NOT EXISTS idx_meeting_attendance_status_user_id ON meeting_attendance_status(user_id);

-- Optional: Add an index on status_timestamp for time-based queries
CREATE INDEX IF NOT EXISTS idx_meeting_attendance_status_timestamp ON meeting_attendance_status(status_timestamp);

-- Optional: Add an index on platform
CREATE INDEX IF NOT EXISTS idx_meeting_attendance_status_platform ON meeting_attendance_status(platform);

COMMENT ON TABLE meeting_attendance_status IS 'Tracks the status and outcome of live meeting attendance tasks processed by the live_meeting_worker.';
COMMENT ON COLUMN meeting_attendance_status.task_id IS 'Unique identifier for the task, matches the Kafka message taskId.';
COMMENT ON COLUMN meeting_attendance_status.user_id IS 'Identifier of the user who initiated the meeting attendance request.';
COMMENT ON COLUMN meeting_attendance_status.platform IS 'The meeting platform, e.g., "zoom", "googlemeet", "msteams".';
COMMENT ON COLUMN meeting_attendance_status.meeting_identifier IS 'The URL or ID of the meeting to be attended.';
COMMENT ON COLUMN meeting_attendance_status.status_timestamp IS 'Timestamp of the last status update for this task.';
COMMENT ON COLUMN meeting_attendance_status.current_status_message IS 'Human-readable description of the current status of the task.';
COMMENT ON COLUMN meeting_attendance_status.final_notion_page_url IS 'URL of the Notion page created, if the task was successful.';
COMMENT ON COLUMN meeting_attendance_status.error_details IS 'Detailed error message if the task failed at any stage.';
COMMENT ON COLUMN meeting_attendance_status.created_at IS 'Timestamp of when this task record was first created.';
