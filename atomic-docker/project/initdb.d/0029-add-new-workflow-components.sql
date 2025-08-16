DO $$
DECLARE
    component_id uuid;
BEGIN
    -- Google Calendar - New Event
    component_id := 'e8a9b0c1-d2e3-4f5a-6b7c-8d9e0f1a2b3c';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'New Event', 'trigger', 'google_calendar', 'Triggers when a new event is created in Google Calendar.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "calendarId": { "type": "string", "title": "Calendar ID", "default": "primary" },
            "schedule": { "type": "string", "title": "Schedule (Cron)" }
        },
        "required": ["schedule"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "eventId": { "type": "string", "title": "Event ID" },
            "summary": { "type": "string", "title": "Summary" },
            "description": { "type": "string", "title": "Description" },
            "startTime": { "type": "string", "title": "Start Time" },
            "endTime": { "type": "string", "title": "End Time" },
            "attendees": { "type": "array", "items": { "type": "string" }, "title": "Attendees" }
        }
    }');

    -- Dropbox - Save File
    component_id := 'f9b0c1d2-e3f4-5a6b-7c8d-9e0f1a2b3c4d';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Save File', 'action', 'dropbox', 'Saves a file to a Dropbox folder.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "folderPath": { "type": "string", "title": "Folder Path" },
            "fileName": { "type": "string", "title": "File Name" },
            "fileContent": { "type": "string", "title": "File Content" }
        },
        "required": ["folderPath", "fileName", "fileContent"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "fileId": { "type": "string", "title": "File ID" },
            "filePath": { "type": "string", "title": "File Path" }
        }
    }');

    -- Microsoft Teams - Send Channel Message
    component_id := 'a0c1d2e3-f4a5-6b7c-8d9e-0f1a2b3c4d5e';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Send Channel Message', 'action', 'msteams', 'Sends a message to a Microsoft Teams channel.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "teamId": { "type": "string", "title": "Team ID" },
            "channelId": { "type": "string", "title": "Channel ID" },
            "message": { "type": "string", "title": "Message" }
        },
        "required": ["teamId", "channelId", "message"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "messageId": { "type": "string", "title": "Message ID" }
        }
    }');

END $$;
