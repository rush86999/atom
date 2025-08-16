DO $$
DECLARE
    component_id uuid;
BEGIN
    -- Gmail Trigger
    component_id := 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'New Email', 'trigger', 'gmail', 'Triggers when a new email is received.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "userId": { "type": "string", "title": "User ID" },
            "query": { "type": "string", "title": "Query", "default": "is:unread" },
            "maxResults": { "type": "number", "title": "Max Results", "default": 10 },
            "schedule": { "type": "string", "title": "Schedule (Cron)" }
        },
        "required": ["userId", "query", "maxResults", "schedule"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "email_body": { "type": "string", "title": "Email Body" },
            "subject": { "type": "string", "title": "Subject" },
            "sender": { "type": "string", "title": "Sender" }
        }
    }');

    -- AI Task
    component_id := 'b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'AI Task', 'action', 'ai', 'Performs a task using an AI model.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "prompt": { "type": "string", "title": "Prompt" },
            "text_to_process": { "type": "string", "title": "Text to Process" }
        },
        "required": ["prompt"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "result": { "type": "string", "title": "Result" }
        }
    }');

    -- Notion Create Task
    component_id := 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Create Task', 'action', 'notion', 'Creates a new task in Notion.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "databaseId": { "type": "string", "title": "Database ID" },
            "task_name": { "type": "string", "title": "Task Name" }
        },
        "required": ["databaseId", "task_name"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- Asana Create Task
    component_id := 'd4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f80';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Create Task', 'action', 'asana', 'Creates a new task in Asana.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "projectId": { "type": "string", "title": "Project ID" },
            "taskName": { "type": "string", "title": "Task Name" }
        },
        "required": ["projectId", "taskName"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- Trello Create Card
    component_id := 'e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8081';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Create Card', 'action', 'trello', 'Creates a new card in Trello.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "listId": { "type": "string", "title": "List ID" },
            "cardName": { "type": "string", "title": "Card Name" }
        },
        "required": ["listId", "cardName"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- Slack Send Message
    component_id := 'f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f808182';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Send Message', 'action', 'slack', 'Sends a message to a Slack channel.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "channelId": { "type": "string", "title": "Channel ID" },
            "text": { "type": "string", "title": "Message Text" }
        },
        "required": ["channelId", "text"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- Send Email
    component_id := 'a7b8c9d0-e1f2-4a3b-4c5d-6e7f80818283';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Send Email', 'action', 'email', 'Sends an email.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "to": { "type": "string", "title": "To" },
            "subject": { "type": "string", "title": "Subject" },
            "body": { "type": "string", "title": "Body" }
        },
        "required": ["to", "subject", "body"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- Reminder
    component_id := 'b8c9d0e1-f2a3-4b4c-5d6e-7f8081828384';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Create Reminder', 'action', 'reminder', 'Creates a reminder.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "summary": { "type": "string", "title": "Summary" },
            "dateTime": { "type": "string", "title": "Date & Time (ISO 8601)" },
            "minutesBefore": { "type": "number", "title": "Minutes Before", "default": 10 }
        },
        "required": ["summary", "dateTime"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "reminder_id": { "type": "string", "title": "Reminder ID" }
        }
    }');

    -- Google Calendar Create Event
    component_id := 'c9d0e1f2-a3b4-4c5d-6e7f-808182838485';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Create Event', 'action', 'google_calendar', 'Creates a new event in Google Calendar.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "calendarId": { "type": "string", "title": "Calendar ID", "default": "primary" },
            "summary": { "type": "string", "title": "Summary" },
            "startTime": { "type": "string", "title": "Start Time (ISO 8601)" },
            "endTime": { "type": "string", "title": "End Time (ISO 8601)" },
            "timezone": { "type": "string", "title": "Timezone", "default": "UTC" }
        },
        "required": ["summary", "startTime", "endTime"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "event_id": { "type": "string", "title": "Event ID" },
            "html_link": { "type": "string", "title": "HTML Link" }
        }
    }');

    -- Flatten
    component_id := 'd0e1f2a3-b4c5-4d6e-7f80-818283848586';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Flatten List', 'action', 'utils', 'Flattens a list of lists into a single list.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "list_to_flatten": { "type": "array", "title": "List to Flatten" }
        },
        "required": ["list_to_flatten"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "flattened_list": { "type": "array", "title": "Flattened List" }
        }
    }');

    -- Delay
    component_id := 'e1f2a3b4-c5d6-4e7f-8081-828384858687';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Delay', 'action', 'utils', 'Delays the workflow for a specified duration.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "duration": { "type": "number", "title": "Duration (seconds)", "default": 60 }
        },
        "required": ["duration"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

    -- LLM Filter
    component_id := 'f2a3b4c5-d6e7-4f80-8182-838485868788';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'LLM Filter', 'action', 'utils', 'Filters text using a natural language condition.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "condition": { "type": "string", "title": "Condition (Natural Language)" }
        },
        "required": ["condition"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{}');

END $$;
