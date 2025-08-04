import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
let openAIClient = null;
export function resetOpenAIClientCache() {
    openAIClient = null;
}
function getOpenAIClient() {
    if (openAIClient) {
        return openAIClient;
    }
    if (!ATOM_OPENAI_API_KEY) {
        console.error('OpenAI API Key not configured for NLU service.');
        return null;
    }
    openAIClient = new OpenAI({
        apiKey: ATOM_OPENAI_API_KEY,
    });
    return openAIClient;
}
const SYSTEM_PROMPT = `
You are an NLU (Natural Language Understanding) system for the Atomic Agent.
Your task is to identify the user's intent and extract relevant entities from their message.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object must have two top-level keys: "intent" (string or null) and "entities" (an object).

Available Intents and their Entities:

(Existing intents 1-27 are assumed to be listed here)
1.  Intent: "GetCalendarEvents"
    - Entities: {"date_range": "e.g., tomorrow, next week, specific date", "limit": "number of events", "event_type_filter": "e.g., Google Meet events", "time_query": "e.g., 2:30 PM, evening", "query_type": "e.g., check_availability, list_events"}
    - Example: User asks "What's on my calendar for tomorrow?" -> {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow"}}
    - Example: User asks "Am I free on Friday at 2:30 PM?" -> {"intent": "GetCalendarEvents", "entities": {"date_range": "Friday", "time_query": "2:30 PM", "query_type": "check_availability"}}
2.  Intent: "CreateCalendarEvent"
    - Entities: {"summary": "event title", "start_time": "ISO string or natural language", "end_time": "ISO string or natural language", "duration": "e.g., 30 minutes, 1 hour", "description": "event details", "location": "event location", "attendees": "array of email addresses"}
    - Example: User says "Schedule 'Team Sync' for next Monday at 10 AM for 45 minutes with alice@example.com" -> {"intent": "CreateCalendarEvent", "entities": {"summary": "Team Sync", "start_time": "next Monday 10:00 AM", "duration": "45 minutes", "attendees": ["alice@example.com"]}}
... (Assume other existing intents like ListEmails, SendEmail, SearchWeb, CreateHubSpotContact, etc., are here)
27. Intent: "ScheduleTeamMeeting"
    - Entities: {"attendees": "array of email addresses or names", "purpose": "meeting subject", "duration_preference": "e.g., 30 minutes, 1 hour", "time_preference_details": "e.g., next Monday morning, this week afternoon"}

New Autopilot Intents:
28. Intent: "EnableAutopilot"
    - Entities: {"raw_query": "The full or relevant part of the user query detailing the autopilot configuration.", "autopilot_config_details": "Specific configuration details if discernable, otherwise use raw_query.", "schedule_description": "e.g., daily, for project X"}
    - Example: User says "Enable autopilot for daily feature deployment" -> {"intent": "EnableAutopilot", "entities": {"raw_query": "Enable autopilot for daily feature deployment", "autopilot_config_details": "daily feature deployment", "schedule_description": "daily"}}
    - Example: User says "Turn on autopilot with query {...}" -> {"intent": "EnableAutopilot", "entities": {"raw_query": "Turn on autopilot with query {...}", "autopilot_config_details": "{...}"}}

29. Intent: "DisableAutopilot"
    - Entities: {"raw_query": "The full user query.", "autopilot_id": "The ID of the autopilot instance or event to disable, if specified.", "event_id": "Alternative key for the ID."}
    - Example: User says "Disable autopilot event 12345" -> {"intent": "DisableAutopilot", "entities": {"raw_query": "Disable autopilot event 12345", "autopilot_id": "12345", "event_id": "12345"}}
    - Example: User says "Turn off autopilot job abc-def" -> {"intent": "DisableAutopilot", "entities": {"raw_query": "Turn off autopilot job abc-def", "autopilot_id": "abc-def"}}

30. Intent: "GetAutopilotStatus"
    - Entities: {"raw_query": "The full user query.", "autopilot_id": "The ID of the autopilot instance to check, if specified."}
    - Example: User says "What's the status of autopilot task 67890?" -> {"intent": "GetAutopilotStatus", "entities": {"raw_query": "What's the status of autopilot task 67890?", "autopilot_id": "67890"}}
    - Example: User says "Show me my autopilot status" -> {"intent": "GetAutopilotStatus", "entities": {"raw_query": "Show me my autopilot status"}}

New Email Querying and Action Intent:
31. Intent: "QueryEmails"
    - Purpose: To find specific emails based on various criteria and potentially perform an action on them (like extracting information or summarizing).
    - Entities:
        - "from_sender": (string, optional) Email address or name of the sender. Example: "Jane Doe", "alerts@example.com"
        - "to_recipient": (string, optional) Email address or name of the recipient. Example: "me", "support team"
        - "subject_keywords": (string, optional) Keywords to search in the email subject. Example: "contract renewal", "important update"
        - "body_keywords": (string, optional) Keywords or phrases to search within the email body. Example: "action items", "summary attached"
        - "label": (string, optional) Gmail label to filter by. Example: "work", "starred", "important"
        - "date_query": (string, optional) Natural language description of the date or date range. Example: "last week", "yesterday", "in July", "since Monday", "between March 1st and April 15th 2023"
        - "has_attachment": (boolean, optional) True if emails must have attachments.
        - "is_unread": (boolean, optional) True if emails must be unread.
        - "exact_phrase_search": (string, optional) An exact phrase to search for in the email.
        - "action_on_email": (string, optional, defaults to just finding/listing if not specified) The action to perform on the found email(s). Values:
            - "FIND_SPECIFIC_INFO": Extract specific details. Requires "information_to_extract_keywords".
            - "GET_SENDER": Get the sender.
            - "GET_SUBJECT": Get the subject.
            - "GET_DATE": Get the date of the email.
            - "GET_FULL_CONTENT": Get the full body content.
            - "SUMMARIZE_EMAIL": Summarize the email content (future capability).
        - "information_to_extract_keywords": (array of strings, optional) Required if "action_on_email" is "FIND_SPECIFIC_INFO". Example: ["contract end date", "invoice amount"]
        - "target_email_id": (string, optional) If the user is referring to a specific email by its ID.
    - Examples:
        - User: "Find emails from XYZ about the contract sent a few months ago and tell me when the contract ends."
          Response: {"intent": "QueryEmails", "entities": {"from_sender": "XYZ", "subject_keywords": "contract", "body_keywords": "contract", "date_query": "a few months ago", "action_on_email": "FIND_SPECIFIC_INFO", "information_to_extract_keywords": ["contract end date"]}}
        - User: "Did I get any emails from support@company.com yesterday?"
          Response: {"intent": "QueryEmails", "entities": {"from_sender": "support@company.com", "date_query": "yesterday"}}
        - User: "Show me unread emails with attachments from 'Project Alpha'."
          Response: {"intent": "QueryEmails", "entities": {"is_unread": true, "has_attachment": true, "body_keywords": "Project Alpha"}}
        - User: "What was the subject of email ID 123abc456?"
          Response: {"intent": "QueryEmails", "entities": {"target_email_id": "123abc456", "action_on_email": "GET_SUBJECT"}}

New Task Management Intents:
32. Intent: "CreateTask"
    - Entities: {"task_description": "string, required - The full description of the task.", "due_date_time": "string, optional - e.g., tomorrow, next Friday 5pm, specific date/time", "priority": "string, optional - e.g., high, medium, low", "list_name": "string, optional - e.g., work, personal, shopping list"}
    - Example: User says "Atom, remind me to submit the TPS report by end of day Friday" -> {"intent": "CreateTask", "entities": {"task_description": "submit the TPS report", "due_date_time": "Friday end of day"}}
    - Example: User says "add a task to call the plumber" -> {"intent": "CreateTask", "entities": {"task_description": "call the plumber"}}
    - Example: User says "new task for my shopping list: buy milk and eggs" -> {"intent": "CreateTask", "entities": {"list_name": "shopping list", "task_description": "buy milk and eggs"}}
    - Example: User says "remind me to pick up laundry tomorrow morning with high priority" -> {"intent": "CreateTask", "entities": {"task_description": "pick up laundry", "due_date_time": "tomorrow morning", "priority": "high"}}

32. Intent: "QueryTasks"
    - Entities: {"date_range": "string, optional - e.g., today, tomorrow, this week, next month", "list_name": "string, optional - e.g., work, personal", "status": "string, optional - e.g., pending, completed, overdue"}
    - Example: User says "what are my tasks for today" -> {"intent": "QueryTasks", "entities": {"date_range": "today"}}
    - Example: User says "show me my work tasks" -> {"intent": "QueryTasks", "entities": {"list_name": "work"}}
    - Example: User says "list all completed tasks for this week" -> {"intent": "QueryTasks", "entities": {"status": "completed", "date_range": "this week"}}
    - Example: User says "do I have any overdue tasks on my personal list" -> {"intent": "QueryTasks", "entities": {"status": "overdue", "list_name": "personal"}}

33. Intent: "UpdateTask"
    - Entities: {"task_identifier": "string, required - Description or part of description of the task to update.", "update_action": "string, required - e.g., complete, set_due_date, change_description, set_priority", "new_due_date_time": "string, optional - New due date/time", "new_description": "string, optional - New task description", "new_priority": "string, optional - New priority level"}
    - Example: User says "mark task 'buy milk' as done" -> {"intent": "UpdateTask", "entities": {"task_identifier": "buy milk", "update_action": "complete"}}
    - Example: User says "change due date for 'review proposal' to tomorrow afternoon" -> {"intent": "UpdateTask", "entities": {"task_identifier": "review proposal", "update_action": "set_due_date", "new_due_date_time": "tomorrow afternoon"}}
    - Example: User says "update task 'call client' to 'call client about new quote'" -> {"intent": "UpdateTask", "entities": {"task_identifier": "call client", "update_action": "change_description", "new_description": "call client about new quote"}}
    - Example: User says "set priority for 'finish report' to high" -> {"intent": "UpdateTask", "entities": {"task_identifier": "finish report", "update_action": "set_priority", "new_priority": "high"}}

New Intent for Scheduling from Email Content:
34. Intent: "ScheduleMeetingFromEmail"
    - Purpose: To parse the content of an email (typically the body) to schedule a new meeting.
    - Entities:
        - "attendees": (array of strings, required) Names or email addresses of people to invite. Example: ["Sarah", "John Doe", "team@example.com"]
        - "duration": (string, optional) Duration of the meeting. Example: "30 minutes", "1 hour". If not specified, a default might be assumed by the scheduling skill (e.g., 30 or 60 minutes).
        - "timing_preferences": (string, optional) Natural language description of preferred timing. Example: "next week", "Wednesday afternoon", "tomorrow morning around 10 AM".
        - "meeting_summary": (string, required) A brief title or summary for the meeting. This should be derived from the email's subject or key phrases in the body.
        - "original_email_body": (string, optional but recommended) The full plain text body of the email.
        - "original_email_subject": (string, optional but recommended) The subject line of the email.
    - Context: This intent is used when the agent processes an email that is a request to schedule a meeting. The user's message to the NLU will be the content of that email.
    - Example: Input email body is "Can we find a time next week for a 30-minute meeting with Sarah and John? Let's prioritize Wednesday afternoon. Subject: Project Kickoff"
      Response: {
        "intent": "ScheduleMeetingFromEmail",
        "entities": {
          "attendees": ["Sarah", "John"],
          "duration": "30 minutes",
          "timing_preferences": "next week, prioritizing Wednesday afternoon",
          "meeting_summary": "Project Kickoff",
          "original_email_body": "Can we find a time next week for a 30-minute meeting with Sarah and John? Let's prioritize Wednesday afternoon. Subject: Project Kickoff",
          "original_email_subject": "Project Kickoff"
        }
      }
    - Example: Input email body is "Hi Atom, please schedule a 1-hour sync with the design team for Friday if possible. Title it 'Weekly Design Sync'. Original subject: Quick Question"
      Response: {
        "intent": "ScheduleMeetingFromEmail",
        "entities": {
          "attendees": ["design team"],
          "duration": "1 hour",
          "timing_preferences": "Friday if possible",
          "meeting_summary": "Weekly Design Sync",
          "original_email_body": "Hi Atom, please schedule a 1-hour sync with the design team for Friday if possible. Title it 'Weekly Design Sync'. Original subject: Quick Question",
          "original_email_subject": "Quick Question"
        }
      }

35. Intent: "RequestMeetingPreparation"
    - Purpose: To gather and compile relevant information from various sources in preparation for a specific meeting identified by the user.
    - Entities:
        - "meeting_reference": {
            "description": "Natural language phrase identifying the meeting. This could include title, attendees, relative time, or specific time.",
            "type": "string",
            "required": true,
            "example": "my meeting with Client X tomorrow about the Q3 proposal", "the 10 AM project sync", "next week's budget review with the finance team"
        },
        - "information_requests": {
            "description": "An array of specific information gathering tasks from different sources.",
            "type": "array",
            "required": true,
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "description": "The data source to query.",
                        "type": "string",
                        "enum": ["gmail", "slack", "notion", "calendar_events"],
                        "required": true
                    },
                    "search_parameters": {
                        "description": "Parameters specific to the data source to guide the search. Note to LLM: For search_parameters, only include keys relevant to the specified 'source'. Example for source: \"gmail\": { \"from_sender\": \"...\", \"subject_keywords\": \"...\" }",
                        "type": "object",
                        "required": true
                        /* Conceptual properties for each source type for LLM guidance:
                        "properties_gmail": {
                            "from_sender": "string (e.g., 'john.doe@example.com', 'Jane Doe')",
                            "subject_keywords": "string (e.g., 'Q3 report', 'contract details')",
                            "body_keywords": "string (e.g., 'action items', 'next steps', 'budget discussion')",
                            "date_query": "string (e.g., 'last 7 days', 'since last Monday', 'in July')",
                            "has_attachment_only": "boolean (true if only emails with attachments are desired)"
                        },
                        "properties_slack": {
                            "channel_name": "string (e.g., '#project-alpha', 'Direct message with Bob')",
                            "from_user": "string (e.g., 'Alice', '@bob')",
                            "text_keywords": "string (e.g., 'key decision', 'blocker', 'feedback received')",
                            "date_query": "string (e.g., 'yesterday', 'this week')",
                            "mentions_user": "string (e.g., 'me', '@current_user')"
                        },
                        "properties_notion": {
                            "database_name_or_id": "string (e.g., 'Meeting Notes DB', 'Project Wiki')",
                            "page_title_keywords": "string (e.g., 'Q3 Planning', 'Client X Onboarding')",
                            "content_keywords": "string (e.g., 'decision log', 'requirements list')",
                            "filter_by_meeting_reference_context": "boolean (true if Notion search should be contextually linked to the meeting_reference, e.g., search pages linked to this meeting or its attendees)"
                        },
                        "properties_calendar_events": {
                            "related_to_attendees_of_meeting_reference": "boolean (true to find past/future events with same attendees as the main meeting_reference)",
                            "keywords_in_summary_or_description": "string (e.g., 'follow-up', 'preparation for')\",
                            "date_query_lookback": "string (e.g., 'past month', 'last 3 meetings with X')\",
                            "type_filter": "string (e.g., 'past_events', 'future_events', 'all_related_events')"
                        }
                        */
                    }
                }
            }
        },
        "overall_lookback_period": {
            "description": "A general lookback period to apply if not specified per information_request. Can be overridden by a more specific date_query within an information_request.",
            "type": "string",
            "optional": true,
            "example": "last 7 days", "since our last major sync"
        }
    - Examples:
        - User: "Prep for my meeting with Sales Team about Q4 strategy. Check emails from sales_lead@example.com on this, Slack in #sales channel, and Notion docs titled 'Q4 Strategy'."
          Response: {
            "intent": "RequestMeetingPreparation",
            "entities": {
              "meeting_reference": "meeting with Sales Team about Q4 strategy",
              "information_requests": [
                {"source": "gmail", "search_parameters": {"from_sender": "sales_lead@example.com", "body_keywords": "Q4 strategy"}},
                {"source": "slack", "search_parameters": {"channel_name": "#sales", "text_keywords": "Q4 strategy"}},
                {"source": "notion", "search_parameters": {"page_title_keywords": "Q4 Strategy"}}
              ]
            }
          }
        - User: "Get me ready for the 10am client call with Acme Corp tomorrow. Find recent emails with 'Acme Corp' and any notes from our Notion project page for 'Acme Project'. Also, see what our last calendar event with them was about."
          Response: {
            "intent": "RequestMeetingPreparation",
            "entities": {
              "meeting_reference": "10am client call with Acme Corp tomorrow",
              "information_requests": [
                {"source": "gmail", "search_parameters": {"body_keywords": "Acme Corp", "date_query": "recent"}},
                {"source": "notion", "search_parameters": {"page_title_keywords": "Acme Project", "content_keywords": "Acme Corp"}},
                {"source": "calendar_events", "search_parameters": {"related_to_attendees_of_meeting_reference": true, "type_filter": "past_events"}}
              ],
              "overall_lookback_period": "recent"
            }
          }

36. Intent: "ProcessMeetingOutcomes"
    - Purpose: To process the outcomes of a specified meeting (e.g., from a transcript or notes) and perform actions like summarizing decisions, drafting follow-up emails, or creating tasks.
    - Entities:
        - "meeting_reference": {
            "description": "Identifier for the meeting whose outcomes are to be processed. Can be a meeting title, a reference to a transcript, a calendar event, or a recent meeting.",
            "type": "string",
            "required": true,
            "example": "the Project Phoenix Debrief transcript", "my last meeting with Acme Corp", "the strategy session from yesterday"
        },
        - "source_document_id": {
            "description": "Optional specific ID of the source document containing the meeting outcomes (e.g., a transcript ID, a Notion page ID, or a file ID if applicable). If not provided, the system may try to infer from meeting_reference.",
            "type": "string",
            "optional": true
        },
        - "outcome_source_type": {
            "description": "The type of source material for the outcomes.",
            "type": "string",
            "enum": ["transcript", "meeting_notes", "audio_recording_summary"],
            "optional": true, "default": "transcript"
        },
        - "requested_actions": {
            "description": "An array specifying the actions to be performed on the meeting outcomes.",
            "type": "array",
            "required": true,
            "items": {
                "type": "string",
                "enum": ["SUMMARIZE_KEY_DECISIONS", "EXTRACT_ACTION_ITEMS", "DRAFT_FOLLOW_UP_EMAIL", "CREATE_TASKS_IN_NOTION"]
            }
        },
        - "email_draft_details": {
            "description": "Details for drafting a follow-up email. Required if 'DRAFT_FOLLOW_UP_EMAIL' is in requested_actions.",
            "type": "object",
            "optional": true,
            "properties": {
                "recipients": "array of strings (e.g., ['attendees', 'john.doe@example.com', 'Sales Team']) or a string (e.g., 'all meeting attendees')",
                "additional_instructions": "string (e.g., 'Keep it concise', 'Focus on deliverables')"
            }
        },
        - "task_creation_details": {
            "description": "Details for creating tasks. Relevant if 'CREATE_TASKS_IN_NOTION' or 'EXTRACT_ACTION_ITEMS' (with intent to create tasks) is in requested_actions.",
            "type": "object",
            "optional": true,
            "properties": {
                "notion_database_id": "string (Optional ID of the Notion database for tasks; defaults to user's primary task DB if not specified)",
                "default_assignee": "string (Optional default assignee for new tasks, e.g., 'me', 'project_lead@example.com')"
            }
        }
    - Examples:
        - User: "For the 'Q1 Review meeting', summarize decisions, extract action items, and draft an email to attendees."
          Response: {
            "intent": "ProcessMeetingOutcomes",
            "entities": {
              "meeting_reference": "Q1 Review meeting",
              "requested_actions": ["SUMMARIZE_KEY_DECISIONS", "EXTRACT_ACTION_ITEMS", "DRAFT_FOLLOW_UP_EMAIL"],
              "email_draft_details": {"recipients": "attendees"}
            }
          }
        - User: "From the transcript ID 'xyz123', create tasks in Notion for any action items found."
          Response: {
            "intent": "ProcessMeetingOutcomes",
            "entities": {
              "meeting_reference": "transcript ID 'xyz123'",
              "source_document_id": "xyz123",
              "outcome_source_type": "transcript",
              "requested_actions": ["EXTRACT_ACTION_ITEMS", "CREATE_TASKS_IN_NOTION"]
            }
          }
        - User: "Process my last meeting: summarize decisions and extract action items."
          Response: {
            "intent": "ProcessMeetingOutcomes",
            "entities": {
              "meeting_reference": "my last meeting",
              "requested_actions": ["SUMMARIZE_KEY_DECISIONS", "EXTRACT_ACTION_ITEMS"]
            }
          }

37. Intent: "GetDailyPriorityBriefing"
    - Purpose: To provide the user with a consolidated overview of their important tasks, meetings, and potentially messages for a given day (defaulting to today).
    - Entities:
        - "date_context": {
            "description": "Specifies the day for which the briefing is requested. Defaults to 'today' if not mentioned.",
            "type": "string",
            "optional": true,
            "example": "today", "tomorrow", "for this Monday"
        },
        - "focus_areas": {
            "description": "Optional array to specify which areas to include in the briefing. If empty or not provided, all primary areas (tasks, meetings, urgent messages) are typically included.",
            "type": "array",
            "optional": true,
            "items": {
                "type": "string",
                "enum": ["tasks", "meetings", "urgent_emails", "urgent_slack_messages", "urgent_teams_messages"]
            },
            "example": "[\"tasks\", \"meetings\"]"
        },
        - "project_filter": {
            "description": "Optional filter to get priorities related to a specific project name or keyword.",
            "type": "string",
            "optional": true,
            "example": "Project Alpha", "the Q4 launch"
        },
        - "urgency_level": {
            "description": "Optional filter for urgency, e.g., only show high priority tasks or critical messages.",
            "type": "string",
            "enum": ["high", "critical", "all"],
            "optional": true,
            "default": "all",
            "example": "high priority only"
        }
    - Examples:
        - User: "What are my top priorities for today?"
          Response: {
            "intent": "GetDailyPriorityBriefing",
            "entities": {
              "date_context": "today"
            }
          }
        - User: "Show me my tasks and meetings for tomorrow for Project Phoenix."
          Response: {
            "intent": "GetDailyPriorityBriefing",
            "entities": {
              "date_context": "tomorrow",
              "focus_areas": ["tasks", "meetings"],
              "project_filter": "Project Phoenix"
            }
          }
        - User: "What urgent emails do I have today?"
          Response: {
            "intent": "GetDailyPriorityBriefing",
            "entities": {
              "date_context": "today",
              "focus_areas": ["urgent_emails"]
            }
          }
        - User: "Give me the high priority items for today."
          Response: {
            "intent": "GetDailyPriorityBriefing",
            "entities": {
                "date_context": "today",
                "urgency_level": "high"
            }
          }

38. Intent: "CreateTaskFromChatMessage"
    - Purpose: To create a task in a task management system (e.g., Notion) based on the content of a specific chat message from platforms like Slack or Teams.
    - Entities:
        - "chat_message_reference": {
            "description": "Information to identify the specific chat message. This could be a direct link to the message, or a descriptive reference like 'the message from John about the UI bug in #dev channel yesterday'.",
            "type": "string",
            "required": true
        },
        - "source_platform": {
            "description": "The platform where the chat message originated.",
            "type": "string",
            "enum": ["slack", "msteams", "gmail_thread_item"],
            "required": true,
            "example": "slack", "the message from Teams"
        },
        - "task_description_override": {
            "description": "Optional explicit description for the task. If not provided, the task description will be derived from the chat message content.",
            "type": "string",
            "optional": true
        },
        - "target_task_list_or_project": {
            "description": "The name or ID of the target list, project, or database where the task should be created (e.g., 'Engineering Bugs DB', 'Client Follow-ups'). Defaults to a general task list if not specified.",
            "type": "string",
            "optional": true
        },
        - "assignee": {
            "description": "Optional suggested assignee for the task (e.g., 'me', 'Alice', 'dev_team@example.com').",
            "type": "string",
            "optional": true
        },
        - "due_date": {
            "description": "Optional suggested due date for the task (e.g., 'tomorrow', 'next Friday', '2024-12-31').",
            "type": "string",
            "optional": true
        },
        - "priority": {
            "description": "Optional priority for the task.",
            "type": "string",
            "enum": ["high", "medium", "low"],
            "optional": true
        }
    - Examples:
        - User: "Create a task from that last Slack message in #support about the login error for the 'Support Tickets' list."
          Response: {
            "intent": "CreateTaskFromChatMessage",
            "entities": {
              "chat_message_reference": "last Slack message in #support about the login error",
              "source_platform": "slack",
              "target_task_list_or_project": "Support Tickets"
            }
          }

39. Intent: "ScheduleSkillActivation"
    - Purpose: To schedule a skill to be activated at a later time.
    - Entities:
        - "skill_to_schedule": {
            "description": "The name of the skill to schedule.",
            "type": "string",
            "required": true
        },
        - "activation_time": {
            "description": "The time at which to activate the skill.",
            "type": "string",
            "required": true
        },
        - "skill_entities": {
            "description": "The entities to pass to the skill when it is activated.",
            "type": "object",
            "optional": true
        }
    - Examples:
        - User: "Schedule the SendEmail skill to run tomorrow at 9am with entities {'to': 'test@example.com', 'subject': 'Test', 'body': 'This is a test'}."
          Response: {
            "intent": "ScheduleSkillActivation",
            "entities": {
              "skill_to_schedule": "SendEmail",
              "activation_time": "tomorrow at 9am",
              "skill_entities": {
                "to": "test@example.com",
                "subject": "Test",
                "body": "This is a test"
              }
            }
          }
        - User: "Make a task from Bob's Teams message: https://teams.microsoft.com/l/message/channel_id/message_id. Call it 'Review proposal' and assign it to me for tomorrow."
          Response: {
            "intent": "CreateTaskFromChatMessage",
            "entities": {
              "chat_message_reference": "https://teams.microsoft.com/l/message/channel_id/message_id",
              "source_platform": "msteams",
              "task_description_override": "Review proposal",
              "assignee": "me",
              "due_date": "tomorrow"
            }
          }
        - User: "Add this email item from Jane as a high priority task: [link_or_id_to_email_item]"
          Response: {
            "intent": "CreateTaskFromChatMessage",
            "entities": {
              "chat_message_reference": "[link_or_id_to_email_item]",
              "source_platform": "gmail_thread_item",
              "priority": "high"
            }
          }

40. Intent: "CreateEmailReminder"
    - Purpose: To create a reminder for an email.
    - Entities:
        - "email_id": {
            "description": "The ID of the email to set a reminder for.",
            "type": "string",
            "required": true
        },
        - "service": {
            "description": "The email service (e.g., 'gmail', 'outlook').",
            "type": "string",
            "required": true
        },
        - "remind_at": {
            "description": "The date and time to be reminded (e.g., 'tomorrow at 9am', 'in 2 hours').",
            "type": "string",
            "required": true
        }
    - Examples:
        - User: "Remind me about this email tomorrow at 9am."
          Response: {
            "intent": "CreateEmailReminder",
            "entities": {
              "remind_at": "tomorrow at 9am"
            }
          }

41. Intent: "Browser"
    - Purpose: To perform a task in a web browser.
    - Entities:
        - "task": {
            "description": "The task to perform in the browser.",
            "type": "string",
            "required": true
        }
    - Examples:
        - User: "Go to github.com and search for 'tauri'."
          Response: {
            "intent": "Browser",
            "entities": {
              "task": "Go to github.com and search for 'tauri'."
            }
          }

If the user's intent is unclear or does not match any of the above single intents, set "intent" to null and "entities" to an empty object.

If the user's intent is ambiguous or critical information is missing for a recognized single intent, set "intent" to "NeedsClarification",
set "entities" to include what was understood (e.g., {"partially_understood_intent": "CreateCalendarEvent", "summary": "Meeting"}),
and formulate a "clarification_question" to ask the user.
Example for NeedsClarification: {"intent": "NeedsClarification", "entities": {"partially_understood_intent": "CreateCalendarEvent", "summary": "Team Meeting with Marketing"}, "clarification_question": "What date and time would you like to schedule the meeting for, and who should be invited?"}

If a user's request involves multiple distinct actions or a sequence of steps that correspond to known simple intents, identify it as a "ComplexTask".
The "entities" for a "ComplexTask" should include an "original_query" key with the user's full request, and a "sub_tasks" key, which is an array of objects.
Each object in the "sub_tasks" array should itself be a standard NLU output structure for a simple intent: {"intent": "SubIntentName", "entities": {...}, "summary_for_sub_task": "User-friendly description of this step"}.
Example for ComplexTask: User says "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights."
Response (assuming BookFlight and FindHotel are defined simple intents):
{
  "intent": "ComplexTask",
  "entities": {
    "original_query": "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights.",
    "sub_tasks": [
      {
        "intent": "CreateCalendarEvent", "entities": {"summary": "Flight to London", "description": "Book flight for next Tuesday to London"},
        "summary_for_sub_task": "Book a flight to London for next Tuesday."
      },
      {
        "intent": "SearchWeb", "entities": {"query": "hotel near Hyde Park London 3 nights"},
        "summary_for_sub_task": "Find a hotel near Hyde Park in London for 3 nights."
      }
    ]
  }
}
If you identify a "ComplexTask", do not also try to process its parts as one of the simpler, single intents in the main response. Focus on the decomposition.
Ensure sub_task intents are chosen from the list of available simple intents.

Example for no matching intent: {"intent": null, "entities": {}}
Example for GetCalendarEvents: {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow", "limit": 3, "event_type_filter": "Google Meet events"}}`;
export async function understandMessage(message, conversationHistory, ltmContext // Added ltmContext parameter
) {
    const client = getOpenAIClient();
    if (!client) {
        return {
            originalMessage: message,
            intent: null,
            entities: {},
            error: 'NLU service not configured: OpenAI API Key is missing.',
        };
    }
    if (!message || message.trim() === '') {
        return {
            originalMessage: message,
            intent: null,
            entities: {},
            error: 'Input message is empty.',
        };
    }
    if (ltmContext && ltmContext.length > 0) {
        console.log(`[NLU Service] Received LTM context with ${ltmContext.length} items. First item (summary): ${JSON.stringify(ltmContext[0].text?.substring(0, 100))}... Potential use: Augment prompts to NLU provider.`);
        // console.log('[NLU Service] Full LTM Context:', JSON.stringify(ltmContext, null, 2)); // Optional: for more detail
    }
    // TODO: Future enhancement - incorporate ltmContext into the prompt for the NLU model.
    // This might involve creating a summarized version of ltmContext to fit token limits
    // or selecting the most relevant pieces of context.
    const messages = [
        { role: 'system', content: SYSTEM_PROMPT },
        ...(conversationHistory || []).map((h) => ({
            role: h.role,
            content: h.content || '',
        })),
        { role: 'user', content: message },
    ];
    try {
        const completion = await client.chat.completions.create({
            model: ATOM_NLU_MODEL_NAME,
            messages: messages,
            temperature: 0.1,
            response_format: { type: 'json_object' },
        });
        const llmResponse = completion.choices[0]?.message?.content;
        if (!llmResponse) {
            return {
                originalMessage: message,
                intent: null,
                entities: {},
                error: 'NLU service received an empty response from AI.',
            };
        }
        try {
            const parsedResponse = JSON.parse(llmResponse);
            if (typeof parsedResponse.intent === 'undefined' ||
                typeof parsedResponse.entities !== 'object') {
                return {
                    originalMessage: message,
                    intent: null,
                    entities: {},
                    error: `NLU service received malformed JSON from AI: ${llmResponse}`,
                };
            }
            const processed = {
                originalMessage: message,
                intent: parsedResponse.intent,
                entities: parsedResponse.entities || {},
                confidence: parsedResponse.confidence,
                recognized_phrase: parsedResponse.recognized_phrase,
            };
            if (parsedResponse.intent === 'NeedsClarification' &&
                parsedResponse.clarification_question) {
                processed.requires_clarification = true;
                processed.clarification_question =
                    parsedResponse.clarification_question;
                if (parsedResponse.partially_understood_intent) {
                    processed.entities.partially_understood_intent =
                        parsedResponse.partially_understood_intent;
                }
            }
            else if (parsedResponse.intent === 'ComplexTask' &&
                parsedResponse.entities &&
                parsedResponse.entities.sub_tasks) {
                processed.sub_tasks = parsedResponse.entities.sub_tasks.map((st) => ({
                    intent: st.intent || null,
                    entities: st.entities || {},
                    summary_for_sub_task: st.summary_for_sub_task || '',
                }));
                // Keep original_query if present in entities
                if (parsedResponse.entities.original_query) {
                    processed.entities.original_query =
                        parsedResponse.entities.original_query;
                }
            }
            // Conceptual Post-Processing for QueryEmails intent:
            if (processed.intent === 'QueryEmails' && processed.entities) {
                const { date_query, ...otherEntities } = processed.entities;
                const resolvedDates = {};
                if (date_query && typeof date_query === 'string') {
                    console.log(`[NLU Service] Raw date_query from LLM: "${date_query}"`);
                    const now = new Date();
                    const formatDate = (d) => `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;
                    const lcDateQuery = date_query.toLowerCase();
                    if (lcDateQuery === 'today') {
                        resolvedDates.after = formatDate(new Date(now.setHours(0, 0, 0, 0)));
                        resolvedDates.before = formatDate(new Date(now.setHours(23, 59, 59, 999)));
                    }
                    else if (lcDateQuery === 'yesterday') {
                        const yesterday = new Date(now);
                        yesterday.setDate(now.getDate() - 1);
                        resolvedDates.after = formatDate(new Date(yesterday.setHours(0, 0, 0, 0)));
                        resolvedDates.before = formatDate(new Date(yesterday.setHours(23, 59, 59, 999)));
                    }
                    else if (lcDateQuery.includes('last week')) {
                        const dayOfWeek = now.getDay();
                        const lastMonday = new Date(now);
                        lastMonday.setDate(now.getDate() - dayOfWeek - 6);
                        lastMonday.setHours(0, 0, 0, 0);
                        const lastSunday = new Date(lastMonday);
                        lastSunday.setDate(lastMonday.getDate() + 6);
                        lastSunday.setHours(23, 59, 59, 999);
                        resolvedDates.after = formatDate(lastMonday);
                        resolvedDates.before = formatDate(lastSunday);
                    }
                    else if (lcDateQuery.includes('this week')) {
                        const dayOfWeek = now.getDay();
                        const currentMonday = new Date(now);
                        currentMonday.setDate(now.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1));
                        currentMonday.setHours(0, 0, 0, 0);
                        const currentSunday = new Date(currentMonday);
                        currentSunday.setDate(currentMonday.getDate() + 6);
                        currentSunday.setHours(23, 59, 59, 999);
                        resolvedDates.after = formatDate(currentMonday);
                        resolvedDates.before = formatDate(currentSunday);
                    }
                    else if (lcDateQuery.includes('last month')) {
                        const firstDayLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
                        const lastDayLastMonth = new Date(now.getFullYear(), now.getMonth(), 0);
                        resolvedDates.after = formatDate(firstDayLastMonth);
                        resolvedDates.before = formatDate(lastDayLastMonth);
                    }
                    else if (lcDateQuery.includes('this month')) {
                        const firstDayThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
                        const lastDayThisMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
                        resolvedDates.after = formatDate(firstDayThisMonth);
                        resolvedDates.before = formatDate(lastDayThisMonth);
                    }
                    if (resolvedDates.after || resolvedDates.before) {
                        processed.entities.resolved_date_range = resolvedDates;
                        console.log(`[NLU Service] Resolved date_query "${date_query}" to:`, resolvedDates);
                    }
                    else {
                        console.log(`[NLU Service] Could not resolve date_query "${date_query}" with basic logic. Passing raw.`);
                    }
                }
                if (processed.intent === 'QueryEmails' && processed.entities) {
                    if (!processed.entities.raw_email_search_query && message) {
                        processed.entities.raw_email_search_query = message;
                        console.warn("[NLU Service] LLM did not explicitly return 'raw_email_search_query' for QueryEmails intent. Using original message as fallback.");
                    }
                    const actionTypeFromLLM = processed.entities.action_on_email;
                    processed.entities.structured_action_request = {
                        actionType: actionTypeFromLLM || 'GET_FULL_CONTENT',
                        infoKeywords: processed.entities.information_to_extract_keywords || undefined,
                        naturalLanguageQuestion: processed.entities.natural_language_question_about_email ||
                            undefined,
                    };
                }
            }
            return processed;
        }
        catch (jsonError) {
            console.error(`Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}`);
            return {
                originalMessage: message,
                intent: null,
                entities: {},
                error: `Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}`,
            };
        }
    }
    catch (error) {
        console.error('Error calling OpenAI for NLU service:', error.message);
        let errorMessage = 'Failed to understand message due to an NLU service error.';
        if (error.response?.data?.error?.message) {
            errorMessage += ` API Error: ${error.response.data.error.message}`;
        }
        else if (error.message) {
            errorMessage += ` Details: ${error.message}`;
        }
        return {
            originalMessage: message,
            intent: null,
            entities: {},
            error: errorMessage,
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1U2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5sdVNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxNQUFNLE1BQU0sUUFBUSxDQUFDO0FBRTVCLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLG9CQUFvQixDQUFDO0FBUTlFLElBQUksWUFBWSxHQUFrQixJQUFJLENBQUM7QUFFdkMsTUFBTSxVQUFVLHNCQUFzQjtJQUNwQyxZQUFZLEdBQUcsSUFBSSxDQUFDO0FBQ3RCLENBQUM7QUFFRCxTQUFTLGVBQWU7SUFDdEIsSUFBSSxZQUFZLEVBQUUsQ0FBQztRQUNqQixPQUFPLFlBQVksQ0FBQztJQUN0QixDQUFDO0lBRUQsSUFBSSxDQUFDLG1CQUFtQixFQUFFLENBQUM7UUFDekIsT0FBTyxDQUFDLEtBQUssQ0FBQyxnREFBZ0QsQ0FBQyxDQUFDO1FBQ2hFLE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztJQUVELFlBQVksR0FBRyxJQUFJLE1BQU0sQ0FBQztRQUN4QixNQUFNLEVBQUUsbUJBQW1CO0tBQzVCLENBQUMsQ0FBQztJQUVILE9BQU8sWUFBWSxDQUFDO0FBQ3RCLENBQUM7QUFFRCxNQUFNLGFBQWEsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7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YyxFQUFFLENBQUM7WUFDeEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxxREFBcUQsV0FBVyxZQUFZLFNBQVMsQ0FBQyxPQUFPLEVBQUUsQ0FDaEcsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsZUFBZSxFQUFFLE9BQU87Z0JBQ3hCLE1BQU0sRUFBRSxJQUFJO2dCQUNaLFFBQVEsRUFBRSxFQUFFO2dCQUNaLEtBQUssRUFBRSxxREFBcUQsV0FBVyxZQUFZLFNBQVMsQ0FBQyxPQUFPLEVBQUU7YUFDdkcsQ0FBQztRQUNKLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLENBQUMsS0FBSyxDQUFDLHVDQUF1QyxFQUFFLEtBQUssQ0FBQyxPQUFPLENBQUMsQ0FBQztRQUN0RSxJQUFJLFlBQVksR0FDZCwyREFBMkQsQ0FBQztRQUM5RCxJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQztZQUN6QyxZQUFZLElBQUksZUFBZSxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUM7UUFDckUsQ0FBQzthQUFNLElBQUksS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ3pCLFlBQVksSUFBSSxhQUFhLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUMvQyxDQUFDO1FBQ0QsT0FBTztZQUNMLGVBQWUsRUFBRSxPQUFPO1lBQ3hCLE1BQU0sRUFBRSxJQUFJO1lBQ1osUUFBUSxFQUFFLEVBQUU7WUFDWixLQUFLLEVBQUUsWUFBWTtTQUNwQixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbSB9IGZyb20gJ29wZW5haS9yZXNvdXJjZXMvY2hhdC9jb21wbGV0aW9ucyc7XG5pbXBvcnQgeyBBVE9NX09QRU5BSV9BUElfS0VZLCBBVE9NX05MVV9NT0RFTF9OQU1FIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIE5MVVJlc3BvbnNlRGF0YSxcbiAgUHJvY2Vzc2VkTkxVUmVzcG9uc2UsXG4gIEx0bVF1ZXJ5UmVzdWx0LCAvLyBJbXBvcnQgTHRtUXVlcnlSZXN1bHRcbiAgRW1haWxBY3Rpb25UeXBlLCAvLyBBc3N1bWluZyBFbWFpbEFjdGlvblR5cGUgaXMgZGVmaW5lZCBpbiB0eXBlcy50c1xufSBmcm9tICcuLi8uLi90eXBlcyc7IC8vIEFkanVzdGVkIHBhdGggYXNzdW1pbmcgdHlwZXMudHMgaXMgaW4gZnVuY3Rpb25zL3R5cGVzLnRzXG5cbmxldCBvcGVuQUlDbGllbnQ6IE9wZW5BSSB8IG51bGwgPSBudWxsO1xuXG5leHBvcnQgZnVuY3Rpb24gcmVzZXRPcGVuQUlDbGllbnRDYWNoZSgpIHtcbiAgb3BlbkFJQ2xpZW50ID0gbnVsbDtcbn1cblxuZnVuY3Rpb24gZ2V0T3BlbkFJQ2xpZW50KCk6IE9wZW5BSSB8IG51bGwge1xuICBpZiAob3BlbkFJQ2xpZW50KSB7XG4gICAgcmV0dXJuIG9wZW5BSUNsaWVudDtcbiAgfVxuXG4gIGlmICghQVRPTV9PUEVOQUlfQVBJX0tFWSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ09wZW5BSSBBUEkgS2V5IG5vdCBjb25maWd1cmVkIGZvciBOTFUgc2VydmljZS4nKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIG9wZW5BSUNsaWVudCA9IG5ldyBPcGVuQUkoe1xuICAgIGFwaUtleTogQVRPTV9PUEVOQUlfQVBJX0tFWSxcbiAgfSk7XG5cbiAgcmV0dXJuIG9wZW5BSUNsaWVudDtcbn1cblxuY29uc3QgU1lTVEVNX1BST01QVCA9IGBcbllvdSBhcmUgYW4gTkxVIChOYXR1cmFsIExhbmd1YWdlIFVuZGVyc3RhbmRpbmcpIHN5c3RlbSBmb3IgdGhlIEF0b21pYyBBZ2VudC5cbllvdXIgdGFzayBpcyB0byBpZGVudGlmeSB0aGUgdXNlcidzIGludGVudCBhbmQgZXh0cmFjdCByZWxldmFudCBlbnRpdGllcyBmcm9tIHRoZWlyIG1lc3NhZ2UuXG5SZXNwb25kIE9OTFkgd2l0aCBhIHNpbmdsZSwgdmFsaWQgSlNPTiBvYmplY3QuIERvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdG9yeSB0ZXh0IGJlZm9yZSBvciBhZnRlciB0aGUgSlNPTi5cblRoZSBKU09OIG9iamVjdCBtdXN0IGhhdmUgdHdvIHRvcC1sZXZlbCBrZXlzOiBcImludGVudFwiIChzdHJpbmcgb3IgbnVsbCkgYW5kIFwiZW50aXRpZXNcIiAoYW4gb2JqZWN0KS5cblxuQXZhaWxhYmxlIEludGVudHMgYW5kIHRoZWlyIEVudGl0aWVzOlxuXG4oRXhpc3RpbmcgaW50ZW50cyAxLTI3IGFyZSBhc3N1bWVkIHRvIGJlIGxpc3RlZCBoZXJlKVxuMS4gIEludGVudDogXCJHZXRDYWxlbmRhckV2ZW50c1wiXG4gICAgLSBFbnRpdGllczoge1wiZGF0ZV9yYW5nZVwiOiBcImUuZy4sIHRvbW9ycm93LCBuZXh0IHdlZWssIHNwZWNpZmljIGRhdGVcIiwgXCJsaW1pdFwiOiBcIm51bWJlciBvZiBldmVudHNcIiwgXCJldmVudF90eXBlX2ZpbHRlclwiOiBcImUuZy4sIEdvb2dsZSBNZWV0IGV2ZW50c1wiLCBcInRpbWVfcXVlcnlcIjogXCJlLmcuLCAyOjMwIFBNLCBldmVuaW5nXCIsIFwicXVlcnlfdHlwZVwiOiBcImUuZy4sIGNoZWNrX2F2YWlsYWJpbGl0eSwgbGlzdF9ldmVudHNcIn1cbiAgICAtIEV4YW1wbGU6IFVzZXIgYXNrcyBcIldoYXQncyBvbiBteSBjYWxlbmRhciBmb3IgdG9tb3Jyb3c/XCIgLT4ge1wiaW50ZW50XCI6IFwiR2V0Q2FsZW5kYXJFdmVudHNcIiwgXCJlbnRpdGllc1wiOiB7XCJkYXRlX3JhbmdlXCI6IFwidG9tb3Jyb3dcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIGFza3MgXCJBbSBJIGZyZWUgb24gRnJpZGF5IGF0IDI6MzAgUE0/XCIgLT4ge1wiaW50ZW50XCI6IFwiR2V0Q2FsZW5kYXJFdmVudHNcIiwgXCJlbnRpdGllc1wiOiB7XCJkYXRlX3JhbmdlXCI6IFwiRnJpZGF5XCIsIFwidGltZV9xdWVyeVwiOiBcIjI6MzAgUE1cIiwgXCJxdWVyeV90eXBlXCI6IFwiY2hlY2tfYXZhaWxhYmlsaXR5XCJ9fVxuMi4gIEludGVudDogXCJDcmVhdGVDYWxlbmRhckV2ZW50XCJcbiAgICAtIEVudGl0aWVzOiB7XCJzdW1tYXJ5XCI6IFwiZXZlbnQgdGl0bGVcIiwgXCJzdGFydF90aW1lXCI6IFwiSVNPIHN0cmluZyBvciBuYXR1cmFsIGxhbmd1YWdlXCIsIFwiZW5kX3RpbWVcIjogXCJJU08gc3RyaW5nIG9yIG5hdHVyYWwgbGFuZ3VhZ2VcIiwgXCJkdXJhdGlvblwiOiBcImUuZy4sIDMwIG1pbnV0ZXMsIDEgaG91clwiLCBcImRlc2NyaXB0aW9uXCI6IFwiZXZlbnQgZGV0YWlsc1wiLCBcImxvY2F0aW9uXCI6IFwiZXZlbnQgbG9jYXRpb25cIiwgXCJhdHRlbmRlZXNcIjogXCJhcnJheSBvZiBlbWFpbCBhZGRyZXNzZXNcIn1cbiAgICAtIEV4YW1wbGU6IFVzZXIgc2F5cyBcIlNjaGVkdWxlICdUZWFtIFN5bmMnIGZvciBuZXh0IE1vbmRheSBhdCAxMCBBTSBmb3IgNDUgbWludXRlcyB3aXRoIGFsaWNlQGV4YW1wbGUuY29tXCIgLT4ge1wiaW50ZW50XCI6IFwiQ3JlYXRlQ2FsZW5kYXJFdmVudFwiLCBcImVudGl0aWVzXCI6IHtcInN1bW1hcnlcIjogXCJUZWFtIFN5bmNcIiwgXCJzdGFydF90aW1lXCI6IFwibmV4dCBNb25kYXkgMTA6MDAgQU1cIiwgXCJkdXJhdGlvblwiOiBcIjQ1IG1pbnV0ZXNcIiwgXCJhdHRlbmRlZXNcIjogW1wiYWxpY2VAZXhhbXBsZS5jb21cIl19fVxuLi4uIChBc3N1bWUgb3RoZXIgZXhpc3RpbmcgaW50ZW50cyBsaWtlIExpc3RFbWFpbHMsIFNlbmRFbWFpbCwgU2VhcmNoV2ViLCBDcmVhdGVIdWJTcG90Q29udGFjdCwgZXRjLiwgYXJlIGhlcmUpXG4yNy4gSW50ZW50OiBcIlNjaGVkdWxlVGVhbU1lZXRpbmdcIlxuICAgIC0gRW50aXRpZXM6IHtcImF0dGVuZGVlc1wiOiBcImFycmF5IG9mIGVtYWlsIGFkZHJlc3NlcyBvciBuYW1lc1wiLCBcInB1cnBvc2VcIjogXCJtZWV0aW5nIHN1YmplY3RcIiwgXCJkdXJhdGlvbl9wcmVmZXJlbmNlXCI6IFwiZS5nLiwgMzAgbWludXRlcywgMSBob3VyXCIsIFwidGltZV9wcmVmZXJlbmNlX2RldGFpbHNcIjogXCJlLmcuLCBuZXh0IE1vbmRheSBtb3JuaW5nLCB0aGlzIHdlZWsgYWZ0ZXJub29uXCJ9XG5cbk5ldyBBdXRvcGlsb3QgSW50ZW50czpcbjI4LiBJbnRlbnQ6IFwiRW5hYmxlQXV0b3BpbG90XCJcbiAgICAtIEVudGl0aWVzOiB7XCJyYXdfcXVlcnlcIjogXCJUaGUgZnVsbCBvciByZWxldmFudCBwYXJ0IG9mIHRoZSB1c2VyIHF1ZXJ5IGRldGFpbGluZyB0aGUgYXV0b3BpbG90IGNvbmZpZ3VyYXRpb24uXCIsIFwiYXV0b3BpbG90X2NvbmZpZ19kZXRhaWxzXCI6IFwiU3BlY2lmaWMgY29uZmlndXJhdGlvbiBkZXRhaWxzIGlmIGRpc2Nlcm5hYmxlLCBvdGhlcndpc2UgdXNlIHJhd19xdWVyeS5cIiwgXCJzY2hlZHVsZV9kZXNjcmlwdGlvblwiOiBcImUuZy4sIGRhaWx5LCBmb3IgcHJvamVjdCBYXCJ9XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJFbmFibGUgYXV0b3BpbG90IGZvciBkYWlseSBmZWF0dXJlIGRlcGxveW1lbnRcIiAtPiB7XCJpbnRlbnRcIjogXCJFbmFibGVBdXRvcGlsb3RcIiwgXCJlbnRpdGllc1wiOiB7XCJyYXdfcXVlcnlcIjogXCJFbmFibGUgYXV0b3BpbG90IGZvciBkYWlseSBmZWF0dXJlIGRlcGxveW1lbnRcIiwgXCJhdXRvcGlsb3RfY29uZmlnX2RldGFpbHNcIjogXCJkYWlseSBmZWF0dXJlIGRlcGxveW1lbnRcIiwgXCJzY2hlZHVsZV9kZXNjcmlwdGlvblwiOiBcImRhaWx5XCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwiVHVybiBvbiBhdXRvcGlsb3Qgd2l0aCBxdWVyeSB7Li4ufVwiIC0+IHtcImludGVudFwiOiBcIkVuYWJsZUF1dG9waWxvdFwiLCBcImVudGl0aWVzXCI6IHtcInJhd19xdWVyeVwiOiBcIlR1cm4gb24gYXV0b3BpbG90IHdpdGggcXVlcnkgey4uLn1cIiwgXCJhdXRvcGlsb3RfY29uZmlnX2RldGFpbHNcIjogXCJ7Li4ufVwifX1cblxuMjkuIEludGVudDogXCJEaXNhYmxlQXV0b3BpbG90XCJcbiAgICAtIEVudGl0aWVzOiB7XCJyYXdfcXVlcnlcIjogXCJUaGUgZnVsbCB1c2VyIHF1ZXJ5LlwiLCBcImF1dG9waWxvdF9pZFwiOiBcIlRoZSBJRCBvZiB0aGUgYXV0b3BpbG90IGluc3RhbmNlIG9yIGV2ZW50IHRvIGRpc2FibGUsIGlmIHNwZWNpZmllZC5cIiwgXCJldmVudF9pZFwiOiBcIkFsdGVybmF0aXZlIGtleSBmb3IgdGhlIElELlwifVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwiRGlzYWJsZSBhdXRvcGlsb3QgZXZlbnQgMTIzNDVcIiAtPiB7XCJpbnRlbnRcIjogXCJEaXNhYmxlQXV0b3BpbG90XCIsIFwiZW50aXRpZXNcIjoge1wicmF3X3F1ZXJ5XCI6IFwiRGlzYWJsZSBhdXRvcGlsb3QgZXZlbnQgMTIzNDVcIiwgXCJhdXRvcGlsb3RfaWRcIjogXCIxMjM0NVwiLCBcImV2ZW50X2lkXCI6IFwiMTIzNDVcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJUdXJuIG9mZiBhdXRvcGlsb3Qgam9iIGFiYy1kZWZcIiAtPiB7XCJpbnRlbnRcIjogXCJEaXNhYmxlQXV0b3BpbG90XCIsIFwiZW50aXRpZXNcIjoge1wicmF3X3F1ZXJ5XCI6IFwiVHVybiBvZmYgYXV0b3BpbG90IGpvYiBhYmMtZGVmXCIsIFwiYXV0b3BpbG90X2lkXCI6IFwiYWJjLWRlZlwifX1cblxuMzAuIEludGVudDogXCJHZXRBdXRvcGlsb3RTdGF0dXNcIlxuICAgIC0gRW50aXRpZXM6IHtcInJhd19xdWVyeVwiOiBcIlRoZSBmdWxsIHVzZXIgcXVlcnkuXCIsIFwiYXV0b3BpbG90X2lkXCI6IFwiVGhlIElEIG9mIHRoZSBhdXRvcGlsb3QgaW5zdGFuY2UgdG8gY2hlY2ssIGlmIHNwZWNpZmllZC5cIn1cbiAgICAtIEV4YW1wbGU6IFVzZXIgc2F5cyBcIldoYXQncyB0aGUgc3RhdHVzIG9mIGF1dG9waWxvdCB0YXNrIDY3ODkwP1wiIC0+IHtcImludGVudFwiOiBcIkdldEF1dG9waWxvdFN0YXR1c1wiLCBcImVudGl0aWVzXCI6IHtcInJhd19xdWVyeVwiOiBcIldoYXQncyB0aGUgc3RhdHVzIG9mIGF1dG9waWxvdCB0YXNrIDY3ODkwP1wiLCBcImF1dG9waWxvdF9pZFwiOiBcIjY3ODkwXCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwiU2hvdyBtZSBteSBhdXRvcGlsb3Qgc3RhdHVzXCIgLT4ge1wiaW50ZW50XCI6IFwiR2V0QXV0b3BpbG90U3RhdHVzXCIsIFwiZW50aXRpZXNcIjoge1wicmF3X3F1ZXJ5XCI6IFwiU2hvdyBtZSBteSBhdXRvcGlsb3Qgc3RhdHVzXCJ9fVxuXG5OZXcgRW1haWwgUXVlcnlpbmcgYW5kIEFjdGlvbiBJbnRlbnQ6XG4zMS4gSW50ZW50OiBcIlF1ZXJ5RW1haWxzXCJcbiAgICAtIFB1cnBvc2U6IFRvIGZpbmQgc3BlY2lmaWMgZW1haWxzIGJhc2VkIG9uIHZhcmlvdXMgY3JpdGVyaWEgYW5kIHBvdGVudGlhbGx5IHBlcmZvcm0gYW4gYWN0aW9uIG9uIHRoZW0gKGxpa2UgZXh0cmFjdGluZyBpbmZvcm1hdGlvbiBvciBzdW1tYXJpemluZykuXG4gICAgLSBFbnRpdGllczpcbiAgICAgICAgLSBcImZyb21fc2VuZGVyXCI6IChzdHJpbmcsIG9wdGlvbmFsKSBFbWFpbCBhZGRyZXNzIG9yIG5hbWUgb2YgdGhlIHNlbmRlci4gRXhhbXBsZTogXCJKYW5lIERvZVwiLCBcImFsZXJ0c0BleGFtcGxlLmNvbVwiXG4gICAgICAgIC0gXCJ0b19yZWNpcGllbnRcIjogKHN0cmluZywgb3B0aW9uYWwpIEVtYWlsIGFkZHJlc3Mgb3IgbmFtZSBvZiB0aGUgcmVjaXBpZW50LiBFeGFtcGxlOiBcIm1lXCIsIFwic3VwcG9ydCB0ZWFtXCJcbiAgICAgICAgLSBcInN1YmplY3Rfa2V5d29yZHNcIjogKHN0cmluZywgb3B0aW9uYWwpIEtleXdvcmRzIHRvIHNlYXJjaCBpbiB0aGUgZW1haWwgc3ViamVjdC4gRXhhbXBsZTogXCJjb250cmFjdCByZW5ld2FsXCIsIFwiaW1wb3J0YW50IHVwZGF0ZVwiXG4gICAgICAgIC0gXCJib2R5X2tleXdvcmRzXCI6IChzdHJpbmcsIG9wdGlvbmFsKSBLZXl3b3JkcyBvciBwaHJhc2VzIHRvIHNlYXJjaCB3aXRoaW4gdGhlIGVtYWlsIGJvZHkuIEV4YW1wbGU6IFwiYWN0aW9uIGl0ZW1zXCIsIFwic3VtbWFyeSBhdHRhY2hlZFwiXG4gICAgICAgIC0gXCJsYWJlbFwiOiAoc3RyaW5nLCBvcHRpb25hbCkgR21haWwgbGFiZWwgdG8gZmlsdGVyIGJ5LiBFeGFtcGxlOiBcIndvcmtcIiwgXCJzdGFycmVkXCIsIFwiaW1wb3J0YW50XCJcbiAgICAgICAgLSBcImRhdGVfcXVlcnlcIjogKHN0cmluZywgb3B0aW9uYWwpIE5hdHVyYWwgbGFuZ3VhZ2UgZGVzY3JpcHRpb24gb2YgdGhlIGRhdGUgb3IgZGF0ZSByYW5nZS4gRXhhbXBsZTogXCJsYXN0IHdlZWtcIiwgXCJ5ZXN0ZXJkYXlcIiwgXCJpbiBKdWx5XCIsIFwic2luY2UgTW9uZGF5XCIsIFwiYmV0d2VlbiBNYXJjaCAxc3QgYW5kIEFwcmlsIDE1dGggMjAyM1wiXG4gICAgICAgIC0gXCJoYXNfYXR0YWNobWVudFwiOiAoYm9vbGVhbiwgb3B0aW9uYWwpIFRydWUgaWYgZW1haWxzIG11c3QgaGF2ZSBhdHRhY2htZW50cy5cbiAgICAgICAgLSBcImlzX3VucmVhZFwiOiAoYm9vbGVhbiwgb3B0aW9uYWwpIFRydWUgaWYgZW1haWxzIG11c3QgYmUgdW5yZWFkLlxuICAgICAgICAtIFwiZXhhY3RfcGhyYXNlX3NlYXJjaFwiOiAoc3RyaW5nLCBvcHRpb25hbCkgQW4gZXhhY3QgcGhyYXNlIHRvIHNlYXJjaCBmb3IgaW4gdGhlIGVtYWlsLlxuICAgICAgICAtIFwiYWN0aW9uX29uX2VtYWlsXCI6IChzdHJpbmcsIG9wdGlvbmFsLCBkZWZhdWx0cyB0byBqdXN0IGZpbmRpbmcvbGlzdGluZyBpZiBub3Qgc3BlY2lmaWVkKSBUaGUgYWN0aW9uIHRvIHBlcmZvcm0gb24gdGhlIGZvdW5kIGVtYWlsKHMpLiBWYWx1ZXM6XG4gICAgICAgICAgICAtIFwiRklORF9TUEVDSUZJQ19JTkZPXCI6IEV4dHJhY3Qgc3BlY2lmaWMgZGV0YWlscy4gUmVxdWlyZXMgXCJpbmZvcm1hdGlvbl90b19leHRyYWN0X2tleXdvcmRzXCIuXG4gICAgICAgICAgICAtIFwiR0VUX1NFTkRFUlwiOiBHZXQgdGhlIHNlbmRlci5cbiAgICAgICAgICAgIC0gXCJHRVRfU1VCSkVDVFwiOiBHZXQgdGhlIHN1YmplY3QuXG4gICAgICAgICAgICAtIFwiR0VUX0RBVEVcIjogR2V0IHRoZSBkYXRlIG9mIHRoZSBlbWFpbC5cbiAgICAgICAgICAgIC0gXCJHRVRfRlVMTF9DT05URU5UXCI6IEdldCB0aGUgZnVsbCBib2R5IGNvbnRlbnQuXG4gICAgICAgICAgICAtIFwiU1VNTUFSSVpFX0VNQUlMXCI6IFN1bW1hcml6ZSB0aGUgZW1haWwgY29udGVudCAoZnV0dXJlIGNhcGFiaWxpdHkpLlxuICAgICAgICAtIFwiaW5mb3JtYXRpb25fdG9fZXh0cmFjdF9rZXl3b3Jkc1wiOiAoYXJyYXkgb2Ygc3RyaW5ncywgb3B0aW9uYWwpIFJlcXVpcmVkIGlmIFwiYWN0aW9uX29uX2VtYWlsXCIgaXMgXCJGSU5EX1NQRUNJRklDX0lORk9cIi4gRXhhbXBsZTogW1wiY29udHJhY3QgZW5kIGRhdGVcIiwgXCJpbnZvaWNlIGFtb3VudFwiXVxuICAgICAgICAtIFwidGFyZ2V0X2VtYWlsX2lkXCI6IChzdHJpbmcsIG9wdGlvbmFsKSBJZiB0aGUgdXNlciBpcyByZWZlcnJpbmcgdG8gYSBzcGVjaWZpYyBlbWFpbCBieSBpdHMgSUQuXG4gICAgLSBFeGFtcGxlczpcbiAgICAgICAgLSBVc2VyOiBcIkZpbmQgZW1haWxzIGZyb20gWFlaIGFib3V0IHRoZSBjb250cmFjdCBzZW50IGEgZmV3IG1vbnRocyBhZ28gYW5kIHRlbGwgbWUgd2hlbiB0aGUgY29udHJhY3QgZW5kcy5cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XCJpbnRlbnRcIjogXCJRdWVyeUVtYWlsc1wiLCBcImVudGl0aWVzXCI6IHtcImZyb21fc2VuZGVyXCI6IFwiWFlaXCIsIFwic3ViamVjdF9rZXl3b3Jkc1wiOiBcImNvbnRyYWN0XCIsIFwiYm9keV9rZXl3b3Jkc1wiOiBcImNvbnRyYWN0XCIsIFwiZGF0ZV9xdWVyeVwiOiBcImEgZmV3IG1vbnRocyBhZ29cIiwgXCJhY3Rpb25fb25fZW1haWxcIjogXCJGSU5EX1NQRUNJRklDX0lORk9cIiwgXCJpbmZvcm1hdGlvbl90b19leHRyYWN0X2tleXdvcmRzXCI6IFtcImNvbnRyYWN0IGVuZCBkYXRlXCJdfX1cbiAgICAgICAgLSBVc2VyOiBcIkRpZCBJIGdldCBhbnkgZW1haWxzIGZyb20gc3VwcG9ydEBjb21wYW55LmNvbSB5ZXN0ZXJkYXk/XCJcbiAgICAgICAgICBSZXNwb25zZToge1wiaW50ZW50XCI6IFwiUXVlcnlFbWFpbHNcIiwgXCJlbnRpdGllc1wiOiB7XCJmcm9tX3NlbmRlclwiOiBcInN1cHBvcnRAY29tcGFueS5jb21cIiwgXCJkYXRlX3F1ZXJ5XCI6IFwieWVzdGVyZGF5XCJ9fVxuICAgICAgICAtIFVzZXI6IFwiU2hvdyBtZSB1bnJlYWQgZW1haWxzIHdpdGggYXR0YWNobWVudHMgZnJvbSAnUHJvamVjdCBBbHBoYScuXCJcbiAgICAgICAgICBSZXNwb25zZToge1wiaW50ZW50XCI6IFwiUXVlcnlFbWFpbHNcIiwgXCJlbnRpdGllc1wiOiB7XCJpc191bnJlYWRcIjogdHJ1ZSwgXCJoYXNfYXR0YWNobWVudFwiOiB0cnVlLCBcImJvZHlfa2V5d29yZHNcIjogXCJQcm9qZWN0IEFscGhhXCJ9fVxuICAgICAgICAtIFVzZXI6IFwiV2hhdCB3YXMgdGhlIHN1YmplY3Qgb2YgZW1haWwgSUQgMTIzYWJjNDU2P1wiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcImludGVudFwiOiBcIlF1ZXJ5RW1haWxzXCIsIFwiZW50aXRpZXNcIjoge1widGFyZ2V0X2VtYWlsX2lkXCI6IFwiMTIzYWJjNDU2XCIsIFwiYWN0aW9uX29uX2VtYWlsXCI6IFwiR0VUX1NVQkpFQ1RcIn19XG5cbk5ldyBUYXNrIE1hbmFnZW1lbnQgSW50ZW50czpcbjMyLiBJbnRlbnQ6IFwiQ3JlYXRlVGFza1wiXG4gICAgLSBFbnRpdGllczoge1widGFza19kZXNjcmlwdGlvblwiOiBcInN0cmluZywgcmVxdWlyZWQgLSBUaGUgZnVsbCBkZXNjcmlwdGlvbiBvZiB0aGUgdGFzay5cIiwgXCJkdWVfZGF0ZV90aW1lXCI6IFwic3RyaW5nLCBvcHRpb25hbCAtIGUuZy4sIHRvbW9ycm93LCBuZXh0IEZyaWRheSA1cG0sIHNwZWNpZmljIGRhdGUvdGltZVwiLCBcInByaW9yaXR5XCI6IFwic3RyaW5nLCBvcHRpb25hbCAtIGUuZy4sIGhpZ2gsIG1lZGl1bSwgbG93XCIsIFwibGlzdF9uYW1lXCI6IFwic3RyaW5nLCBvcHRpb25hbCAtIGUuZy4sIHdvcmssIHBlcnNvbmFsLCBzaG9wcGluZyBsaXN0XCJ9XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJBdG9tLCByZW1pbmQgbWUgdG8gc3VibWl0IHRoZSBUUFMgcmVwb3J0IGJ5IGVuZCBvZiBkYXkgRnJpZGF5XCIgLT4ge1wiaW50ZW50XCI6IFwiQ3JlYXRlVGFza1wiLCBcImVudGl0aWVzXCI6IHtcInRhc2tfZGVzY3JpcHRpb25cIjogXCJzdWJtaXQgdGhlIFRQUyByZXBvcnRcIiwgXCJkdWVfZGF0ZV90aW1lXCI6IFwiRnJpZGF5IGVuZCBvZiBkYXlcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJhZGQgYSB0YXNrIHRvIGNhbGwgdGhlIHBsdW1iZXJcIiAtPiB7XCJpbnRlbnRcIjogXCJDcmVhdGVUYXNrXCIsIFwiZW50aXRpZXNcIjoge1widGFza19kZXNjcmlwdGlvblwiOiBcImNhbGwgdGhlIHBsdW1iZXJcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJuZXcgdGFzayBmb3IgbXkgc2hvcHBpbmcgbGlzdDogYnV5IG1pbGsgYW5kIGVnZ3NcIiAtPiB7XCJpbnRlbnRcIjogXCJDcmVhdGVUYXNrXCIsIFwiZW50aXRpZXNcIjoge1wibGlzdF9uYW1lXCI6IFwic2hvcHBpbmcgbGlzdFwiLCBcInRhc2tfZGVzY3JpcHRpb25cIjogXCJidXkgbWlsayBhbmQgZWdnc1wifX1cbiAgICAtIEV4YW1wbGU6IFVzZXIgc2F5cyBcInJlbWluZCBtZSB0byBwaWNrIHVwIGxhdW5kcnkgdG9tb3Jyb3cgbW9ybmluZyB3aXRoIGhpZ2ggcHJpb3JpdHlcIiAtPiB7XCJpbnRlbnRcIjogXCJDcmVhdGVUYXNrXCIsIFwiZW50aXRpZXNcIjoge1widGFza19kZXNjcmlwdGlvblwiOiBcInBpY2sgdXAgbGF1bmRyeVwiLCBcImR1ZV9kYXRlX3RpbWVcIjogXCJ0b21vcnJvdyBtb3JuaW5nXCIsIFwicHJpb3JpdHlcIjogXCJoaWdoXCJ9fVxuXG4zMi4gSW50ZW50OiBcIlF1ZXJ5VGFza3NcIlxuICAgIC0gRW50aXRpZXM6IHtcImRhdGVfcmFuZ2VcIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gZS5nLiwgdG9kYXksIHRvbW9ycm93LCB0aGlzIHdlZWssIG5leHQgbW9udGhcIiwgXCJsaXN0X25hbWVcIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gZS5nLiwgd29yaywgcGVyc29uYWxcIiwgXCJzdGF0dXNcIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gZS5nLiwgcGVuZGluZywgY29tcGxldGVkLCBvdmVyZHVlXCJ9XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJ3aGF0IGFyZSBteSB0YXNrcyBmb3IgdG9kYXlcIiAtPiB7XCJpbnRlbnRcIjogXCJRdWVyeVRhc2tzXCIsIFwiZW50aXRpZXNcIjoge1wiZGF0ZV9yYW5nZVwiOiBcInRvZGF5XCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwic2hvdyBtZSBteSB3b3JrIHRhc2tzXCIgLT4ge1wiaW50ZW50XCI6IFwiUXVlcnlUYXNrc1wiLCBcImVudGl0aWVzXCI6IHtcImxpc3RfbmFtZVwiOiBcIndvcmtcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJsaXN0IGFsbCBjb21wbGV0ZWQgdGFza3MgZm9yIHRoaXMgd2Vla1wiIC0+IHtcImludGVudFwiOiBcIlF1ZXJ5VGFza3NcIiwgXCJlbnRpdGllc1wiOiB7XCJzdGF0dXNcIjogXCJjb21wbGV0ZWRcIiwgXCJkYXRlX3JhbmdlXCI6IFwidGhpcyB3ZWVrXCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwiZG8gSSBoYXZlIGFueSBvdmVyZHVlIHRhc2tzIG9uIG15IHBlcnNvbmFsIGxpc3RcIiAtPiB7XCJpbnRlbnRcIjogXCJRdWVyeVRhc2tzXCIsIFwiZW50aXRpZXNcIjoge1wic3RhdHVzXCI6IFwib3ZlcmR1ZVwiLCBcImxpc3RfbmFtZVwiOiBcInBlcnNvbmFsXCJ9fVxuXG4zMy4gSW50ZW50OiBcIlVwZGF0ZVRhc2tcIlxuICAgIC0gRW50aXRpZXM6IHtcInRhc2tfaWRlbnRpZmllclwiOiBcInN0cmluZywgcmVxdWlyZWQgLSBEZXNjcmlwdGlvbiBvciBwYXJ0IG9mIGRlc2NyaXB0aW9uIG9mIHRoZSB0YXNrIHRvIHVwZGF0ZS5cIiwgXCJ1cGRhdGVfYWN0aW9uXCI6IFwic3RyaW5nLCByZXF1aXJlZCAtIGUuZy4sIGNvbXBsZXRlLCBzZXRfZHVlX2RhdGUsIGNoYW5nZV9kZXNjcmlwdGlvbiwgc2V0X3ByaW9yaXR5XCIsIFwibmV3X2R1ZV9kYXRlX3RpbWVcIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gTmV3IGR1ZSBkYXRlL3RpbWVcIiwgXCJuZXdfZGVzY3JpcHRpb25cIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gTmV3IHRhc2sgZGVzY3JpcHRpb25cIiwgXCJuZXdfcHJpb3JpdHlcIjogXCJzdHJpbmcsIG9wdGlvbmFsIC0gTmV3IHByaW9yaXR5IGxldmVsXCJ9XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJtYXJrIHRhc2sgJ2J1eSBtaWxrJyBhcyBkb25lXCIgLT4ge1wiaW50ZW50XCI6IFwiVXBkYXRlVGFza1wiLCBcImVudGl0aWVzXCI6IHtcInRhc2tfaWRlbnRpZmllclwiOiBcImJ1eSBtaWxrXCIsIFwidXBkYXRlX2FjdGlvblwiOiBcImNvbXBsZXRlXCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwiY2hhbmdlIGR1ZSBkYXRlIGZvciAncmV2aWV3IHByb3Bvc2FsJyB0byB0b21vcnJvdyBhZnRlcm5vb25cIiAtPiB7XCJpbnRlbnRcIjogXCJVcGRhdGVUYXNrXCIsIFwiZW50aXRpZXNcIjoge1widGFza19pZGVudGlmaWVyXCI6IFwicmV2aWV3IHByb3Bvc2FsXCIsIFwidXBkYXRlX2FjdGlvblwiOiBcInNldF9kdWVfZGF0ZVwiLCBcIm5ld19kdWVfZGF0ZV90aW1lXCI6IFwidG9tb3Jyb3cgYWZ0ZXJub29uXCJ9fVxuICAgIC0gRXhhbXBsZTogVXNlciBzYXlzIFwidXBkYXRlIHRhc2sgJ2NhbGwgY2xpZW50JyB0byAnY2FsbCBjbGllbnQgYWJvdXQgbmV3IHF1b3RlJ1wiIC0+IHtcImludGVudFwiOiBcIlVwZGF0ZVRhc2tcIiwgXCJlbnRpdGllc1wiOiB7XCJ0YXNrX2lkZW50aWZpZXJcIjogXCJjYWxsIGNsaWVudFwiLCBcInVwZGF0ZV9hY3Rpb25cIjogXCJjaGFuZ2VfZGVzY3JpcHRpb25cIiwgXCJuZXdfZGVzY3JpcHRpb25cIjogXCJjYWxsIGNsaWVudCBhYm91dCBuZXcgcXVvdGVcIn19XG4gICAgLSBFeGFtcGxlOiBVc2VyIHNheXMgXCJzZXQgcHJpb3JpdHkgZm9yICdmaW5pc2ggcmVwb3J0JyB0byBoaWdoXCIgLT4ge1wiaW50ZW50XCI6IFwiVXBkYXRlVGFza1wiLCBcImVudGl0aWVzXCI6IHtcInRhc2tfaWRlbnRpZmllclwiOiBcImZpbmlzaCByZXBvcnRcIiwgXCJ1cGRhdGVfYWN0aW9uXCI6IFwic2V0X3ByaW9yaXR5XCIsIFwibmV3X3ByaW9yaXR5XCI6IFwiaGlnaFwifX1cblxuTmV3IEludGVudCBmb3IgU2NoZWR1bGluZyBmcm9tIEVtYWlsIENvbnRlbnQ6XG4zNC4gSW50ZW50OiBcIlNjaGVkdWxlTWVldGluZ0Zyb21FbWFpbFwiXG4gICAgLSBQdXJwb3NlOiBUbyBwYXJzZSB0aGUgY29udGVudCBvZiBhbiBlbWFpbCAodHlwaWNhbGx5IHRoZSBib2R5KSB0byBzY2hlZHVsZSBhIG5ldyBtZWV0aW5nLlxuICAgIC0gRW50aXRpZXM6XG4gICAgICAgIC0gXCJhdHRlbmRlZXNcIjogKGFycmF5IG9mIHN0cmluZ3MsIHJlcXVpcmVkKSBOYW1lcyBvciBlbWFpbCBhZGRyZXNzZXMgb2YgcGVvcGxlIHRvIGludml0ZS4gRXhhbXBsZTogW1wiU2FyYWhcIiwgXCJKb2huIERvZVwiLCBcInRlYW1AZXhhbXBsZS5jb21cIl1cbiAgICAgICAgLSBcImR1cmF0aW9uXCI6IChzdHJpbmcsIG9wdGlvbmFsKSBEdXJhdGlvbiBvZiB0aGUgbWVldGluZy4gRXhhbXBsZTogXCIzMCBtaW51dGVzXCIsIFwiMSBob3VyXCIuIElmIG5vdCBzcGVjaWZpZWQsIGEgZGVmYXVsdCBtaWdodCBiZSBhc3N1bWVkIGJ5IHRoZSBzY2hlZHVsaW5nIHNraWxsIChlLmcuLCAzMCBvciA2MCBtaW51dGVzKS5cbiAgICAgICAgLSBcInRpbWluZ19wcmVmZXJlbmNlc1wiOiAoc3RyaW5nLCBvcHRpb25hbCkgTmF0dXJhbCBsYW5ndWFnZSBkZXNjcmlwdGlvbiBvZiBwcmVmZXJyZWQgdGltaW5nLiBFeGFtcGxlOiBcIm5leHQgd2Vla1wiLCBcIldlZG5lc2RheSBhZnRlcm5vb25cIiwgXCJ0b21vcnJvdyBtb3JuaW5nIGFyb3VuZCAxMCBBTVwiLlxuICAgICAgICAtIFwibWVldGluZ19zdW1tYXJ5XCI6IChzdHJpbmcsIHJlcXVpcmVkKSBBIGJyaWVmIHRpdGxlIG9yIHN1bW1hcnkgZm9yIHRoZSBtZWV0aW5nLiBUaGlzIHNob3VsZCBiZSBkZXJpdmVkIGZyb20gdGhlIGVtYWlsJ3Mgc3ViamVjdCBvciBrZXkgcGhyYXNlcyBpbiB0aGUgYm9keS5cbiAgICAgICAgLSBcIm9yaWdpbmFsX2VtYWlsX2JvZHlcIjogKHN0cmluZywgb3B0aW9uYWwgYnV0IHJlY29tbWVuZGVkKSBUaGUgZnVsbCBwbGFpbiB0ZXh0IGJvZHkgb2YgdGhlIGVtYWlsLlxuICAgICAgICAtIFwib3JpZ2luYWxfZW1haWxfc3ViamVjdFwiOiAoc3RyaW5nLCBvcHRpb25hbCBidXQgcmVjb21tZW5kZWQpIFRoZSBzdWJqZWN0IGxpbmUgb2YgdGhlIGVtYWlsLlxuICAgIC0gQ29udGV4dDogVGhpcyBpbnRlbnQgaXMgdXNlZCB3aGVuIHRoZSBhZ2VudCBwcm9jZXNzZXMgYW4gZW1haWwgdGhhdCBpcyBhIHJlcXVlc3QgdG8gc2NoZWR1bGUgYSBtZWV0aW5nLiBUaGUgdXNlcidzIG1lc3NhZ2UgdG8gdGhlIE5MVSB3aWxsIGJlIHRoZSBjb250ZW50IG9mIHRoYXQgZW1haWwuXG4gICAgLSBFeGFtcGxlOiBJbnB1dCBlbWFpbCBib2R5IGlzIFwiQ2FuIHdlIGZpbmQgYSB0aW1lIG5leHQgd2VlayBmb3IgYSAzMC1taW51dGUgbWVldGluZyB3aXRoIFNhcmFoIGFuZCBKb2huPyBMZXQncyBwcmlvcml0aXplIFdlZG5lc2RheSBhZnRlcm5vb24uIFN1YmplY3Q6IFByb2plY3QgS2lja29mZlwiXG4gICAgICBSZXNwb25zZToge1xuICAgICAgICBcImludGVudFwiOiBcIlNjaGVkdWxlTWVldGluZ0Zyb21FbWFpbFwiLFxuICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICBcImF0dGVuZGVlc1wiOiBbXCJTYXJhaFwiLCBcIkpvaG5cIl0sXG4gICAgICAgICAgXCJkdXJhdGlvblwiOiBcIjMwIG1pbnV0ZXNcIixcbiAgICAgICAgICBcInRpbWluZ19wcmVmZXJlbmNlc1wiOiBcIm5leHQgd2VlaywgcHJpb3JpdGl6aW5nIFdlZG5lc2RheSBhZnRlcm5vb25cIixcbiAgICAgICAgICBcIm1lZXRpbmdfc3VtbWFyeVwiOiBcIlByb2plY3QgS2lja29mZlwiLFxuICAgICAgICAgIFwib3JpZ2luYWxfZW1haWxfYm9keVwiOiBcIkNhbiB3ZSBmaW5kIGEgdGltZSBuZXh0IHdlZWsgZm9yIGEgMzAtbWludXRlIG1lZXRpbmcgd2l0aCBTYXJhaCBhbmQgSm9obj8gTGV0J3MgcHJpb3JpdGl6ZSBXZWRuZXNkYXkgYWZ0ZXJub29uLiBTdWJqZWN0OiBQcm9qZWN0IEtpY2tvZmZcIixcbiAgICAgICAgICBcIm9yaWdpbmFsX2VtYWlsX3N1YmplY3RcIjogXCJQcm9qZWN0IEtpY2tvZmZcIlxuICAgICAgICB9XG4gICAgICB9XG4gICAgLSBFeGFtcGxlOiBJbnB1dCBlbWFpbCBib2R5IGlzIFwiSGkgQXRvbSwgcGxlYXNlIHNjaGVkdWxlIGEgMS1ob3VyIHN5bmMgd2l0aCB0aGUgZGVzaWduIHRlYW0gZm9yIEZyaWRheSBpZiBwb3NzaWJsZS4gVGl0bGUgaXQgJ1dlZWtseSBEZXNpZ24gU3luYycuIE9yaWdpbmFsIHN1YmplY3Q6IFF1aWNrIFF1ZXN0aW9uXCJcbiAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgIFwiaW50ZW50XCI6IFwiU2NoZWR1bGVNZWV0aW5nRnJvbUVtYWlsXCIsXG4gICAgICAgIFwiZW50aXRpZXNcIjoge1xuICAgICAgICAgIFwiYXR0ZW5kZWVzXCI6IFtcImRlc2lnbiB0ZWFtXCJdLFxuICAgICAgICAgIFwiZHVyYXRpb25cIjogXCIxIGhvdXJcIixcbiAgICAgICAgICBcInRpbWluZ19wcmVmZXJlbmNlc1wiOiBcIkZyaWRheSBpZiBwb3NzaWJsZVwiLFxuICAgICAgICAgIFwibWVldGluZ19zdW1tYXJ5XCI6IFwiV2Vla2x5IERlc2lnbiBTeW5jXCIsXG4gICAgICAgICAgXCJvcmlnaW5hbF9lbWFpbF9ib2R5XCI6IFwiSGkgQXRvbSwgcGxlYXNlIHNjaGVkdWxlIGEgMS1ob3VyIHN5bmMgd2l0aCB0aGUgZGVzaWduIHRlYW0gZm9yIEZyaWRheSBpZiBwb3NzaWJsZS4gVGl0bGUgaXQgJ1dlZWtseSBEZXNpZ24gU3luYycuIE9yaWdpbmFsIHN1YmplY3Q6IFF1aWNrIFF1ZXN0aW9uXCIsXG4gICAgICAgICAgXCJvcmlnaW5hbF9lbWFpbF9zdWJqZWN0XCI6IFwiUXVpY2sgUXVlc3Rpb25cIlxuICAgICAgICB9XG4gICAgICB9XG5cbjM1LiBJbnRlbnQ6IFwiUmVxdWVzdE1lZXRpbmdQcmVwYXJhdGlvblwiXG4gICAgLSBQdXJwb3NlOiBUbyBnYXRoZXIgYW5kIGNvbXBpbGUgcmVsZXZhbnQgaW5mb3JtYXRpb24gZnJvbSB2YXJpb3VzIHNvdXJjZXMgaW4gcHJlcGFyYXRpb24gZm9yIGEgc3BlY2lmaWMgbWVldGluZyBpZGVudGlmaWVkIGJ5IHRoZSB1c2VyLlxuICAgIC0gRW50aXRpZXM6XG4gICAgICAgIC0gXCJtZWV0aW5nX3JlZmVyZW5jZVwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiTmF0dXJhbCBsYW5ndWFnZSBwaHJhc2UgaWRlbnRpZnlpbmcgdGhlIG1lZXRpbmcuIFRoaXMgY291bGQgaW5jbHVkZSB0aXRsZSwgYXR0ZW5kZWVzLCByZWxhdGl2ZSB0aW1lLCBvciBzcGVjaWZpYyB0aW1lLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcInJlcXVpcmVkXCI6IHRydWUsXG4gICAgICAgICAgICBcImV4YW1wbGVcIjogXCJteSBtZWV0aW5nIHdpdGggQ2xpZW50IFggdG9tb3Jyb3cgYWJvdXQgdGhlIFEzIHByb3Bvc2FsXCIsIFwidGhlIDEwIEFNIHByb2plY3Qgc3luY1wiLCBcIm5leHQgd2VlaydzIGJ1ZGdldCByZXZpZXcgd2l0aCB0aGUgZmluYW5jZSB0ZWFtXCJcbiAgICAgICAgfSxcbiAgICAgICAgLSBcImluZm9ybWF0aW9uX3JlcXVlc3RzXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJBbiBhcnJheSBvZiBzcGVjaWZpYyBpbmZvcm1hdGlvbiBnYXRoZXJpbmcgdGFza3MgZnJvbSBkaWZmZXJlbnQgc291cmNlcy5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcImFycmF5XCIsXG4gICAgICAgICAgICBcInJlcXVpcmVkXCI6IHRydWUsXG4gICAgICAgICAgICBcIml0ZW1zXCI6IHtcbiAgICAgICAgICAgICAgICBcInR5cGVcIjogXCJvYmplY3RcIixcbiAgICAgICAgICAgICAgICBcInByb3BlcnRpZXNcIjoge1xuICAgICAgICAgICAgICAgICAgICBcInNvdXJjZVwiOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIGRhdGEgc291cmNlIHRvIHF1ZXJ5LlwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICAgICAgICAgICAgICBcImVudW1cIjogW1wiZ21haWxcIiwgXCJzbGFja1wiLCBcIm5vdGlvblwiLCBcImNhbGVuZGFyX2V2ZW50c1wiXSxcbiAgICAgICAgICAgICAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZVxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICBcInNlYXJjaF9wYXJhbWV0ZXJzXCI6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJQYXJhbWV0ZXJzIHNwZWNpZmljIHRvIHRoZSBkYXRhIHNvdXJjZSB0byBndWlkZSB0aGUgc2VhcmNoLiBOb3RlIHRvIExMTTogRm9yIHNlYXJjaF9wYXJhbWV0ZXJzLCBvbmx5IGluY2x1ZGUga2V5cyByZWxldmFudCB0byB0aGUgc3BlY2lmaWVkICdzb3VyY2UnLiBFeGFtcGxlIGZvciBzb3VyY2U6IFxcXCJnbWFpbFxcXCI6IHsgXFxcImZyb21fc2VuZGVyXFxcIjogXFxcIi4uLlxcXCIsIFxcXCJzdWJqZWN0X2tleXdvcmRzXFxcIjogXFxcIi4uLlxcXCIgfVwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgXCJ0eXBlXCI6IFwib2JqZWN0XCIsXG4gICAgICAgICAgICAgICAgICAgICAgICBcInJlcXVpcmVkXCI6IHRydWVcbiAgICAgICAgICAgICAgICAgICAgICAgIC8qIENvbmNlcHR1YWwgcHJvcGVydGllcyBmb3IgZWFjaCBzb3VyY2UgdHlwZSBmb3IgTExNIGd1aWRhbmNlOlxuICAgICAgICAgICAgICAgICAgICAgICAgXCJwcm9wZXJ0aWVzX2dtYWlsXCI6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImZyb21fc2VuZGVyXCI6IFwic3RyaW5nIChlLmcuLCAnam9obi5kb2VAZXhhbXBsZS5jb20nLCAnSmFuZSBEb2UnKVwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwic3ViamVjdF9rZXl3b3Jkc1wiOiBcInN0cmluZyAoZS5nLiwgJ1EzIHJlcG9ydCcsICdjb250cmFjdCBkZXRhaWxzJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImJvZHlfa2V5d29yZHNcIjogXCJzdHJpbmcgKGUuZy4sICdhY3Rpb24gaXRlbXMnLCAnbmV4dCBzdGVwcycsICdidWRnZXQgZGlzY3Vzc2lvbicpXCIsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgXCJkYXRlX3F1ZXJ5XCI6IFwic3RyaW5nIChlLmcuLCAnbGFzdCA3IGRheXMnLCAnc2luY2UgbGFzdCBNb25kYXknLCAnaW4gSnVseScpXCIsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgXCJoYXNfYXR0YWNobWVudF9vbmx5XCI6IFwiYm9vbGVhbiAodHJ1ZSBpZiBvbmx5IGVtYWlscyB3aXRoIGF0dGFjaG1lbnRzIGFyZSBkZXNpcmVkKVwiXG4gICAgICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICAgICAgXCJwcm9wZXJ0aWVzX3NsYWNrXCI6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImNoYW5uZWxfbmFtZVwiOiBcInN0cmluZyAoZS5nLiwgJyNwcm9qZWN0LWFscGhhJywgJ0RpcmVjdCBtZXNzYWdlIHdpdGggQm9iJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImZyb21fdXNlclwiOiBcInN0cmluZyAoZS5nLiwgJ0FsaWNlJywgJ0Bib2InKVwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwidGV4dF9rZXl3b3Jkc1wiOiBcInN0cmluZyAoZS5nLiwgJ2tleSBkZWNpc2lvbicsICdibG9ja2VyJywgJ2ZlZWRiYWNrIHJlY2VpdmVkJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImRhdGVfcXVlcnlcIjogXCJzdHJpbmcgKGUuZy4sICd5ZXN0ZXJkYXknLCAndGhpcyB3ZWVrJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcIm1lbnRpb25zX3VzZXJcIjogXCJzdHJpbmcgKGUuZy4sICdtZScsICdAY3VycmVudF91c2VyJylcIlxuICAgICAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgICAgIFwicHJvcGVydGllc19ub3Rpb25cIjoge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwiZGF0YWJhc2VfbmFtZV9vcl9pZFwiOiBcInN0cmluZyAoZS5nLiwgJ01lZXRpbmcgTm90ZXMgREInLCAnUHJvamVjdCBXaWtpJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcInBhZ2VfdGl0bGVfa2V5d29yZHNcIjogXCJzdHJpbmcgKGUuZy4sICdRMyBQbGFubmluZycsICdDbGllbnQgWCBPbmJvYXJkaW5nJylcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImNvbnRlbnRfa2V5d29yZHNcIjogXCJzdHJpbmcgKGUuZy4sICdkZWNpc2lvbiBsb2cnLCAncmVxdWlyZW1lbnRzIGxpc3QnKVwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwiZmlsdGVyX2J5X21lZXRpbmdfcmVmZXJlbmNlX2NvbnRleHRcIjogXCJib29sZWFuICh0cnVlIGlmIE5vdGlvbiBzZWFyY2ggc2hvdWxkIGJlIGNvbnRleHR1YWxseSBsaW5rZWQgdG8gdGhlIG1lZXRpbmdfcmVmZXJlbmNlLCBlLmcuLCBzZWFyY2ggcGFnZXMgbGlua2VkIHRvIHRoaXMgbWVldGluZyBvciBpdHMgYXR0ZW5kZWVzKVwiXG4gICAgICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICAgICAgXCJwcm9wZXJ0aWVzX2NhbGVuZGFyX2V2ZW50c1wiOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgXCJyZWxhdGVkX3RvX2F0dGVuZGVlc19vZl9tZWV0aW5nX3JlZmVyZW5jZVwiOiBcImJvb2xlYW4gKHRydWUgdG8gZmluZCBwYXN0L2Z1dHVyZSBldmVudHMgd2l0aCBzYW1lIGF0dGVuZGVlcyBhcyB0aGUgbWFpbiBtZWV0aW5nX3JlZmVyZW5jZSlcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImtleXdvcmRzX2luX3N1bW1hcnlfb3JfZGVzY3JpcHRpb25cIjogXCJzdHJpbmcgKGUuZy4sICdmb2xsb3ctdXAnLCAncHJlcGFyYXRpb24gZm9yJylcXFwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwiZGF0ZV9xdWVyeV9sb29rYmFja1wiOiBcInN0cmluZyAoZS5nLiwgJ3Bhc3QgbW9udGgnLCAnbGFzdCAzIG1lZXRpbmdzIHdpdGggWCcpXFxcIixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBcInR5cGVfZmlsdGVyXCI6IFwic3RyaW5nIChlLmcuLCAncGFzdF9ldmVudHMnLCAnZnV0dXJlX2V2ZW50cycsICdhbGxfcmVsYXRlZF9ldmVudHMnKVwiXG4gICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAqL1xuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICB9LFxuICAgICAgICBcIm92ZXJhbGxfbG9va2JhY2tfcGVyaW9kXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJBIGdlbmVyYWwgbG9va2JhY2sgcGVyaW9kIHRvIGFwcGx5IGlmIG5vdCBzcGVjaWZpZWQgcGVyIGluZm9ybWF0aW9uX3JlcXVlc3QuIENhbiBiZSBvdmVycmlkZGVuIGJ5IGEgbW9yZSBzcGVjaWZpYyBkYXRlX3F1ZXJ5IHdpdGhpbiBhbiBpbmZvcm1hdGlvbl9yZXF1ZXN0LlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWUsXG4gICAgICAgICAgICBcImV4YW1wbGVcIjogXCJsYXN0IDcgZGF5c1wiLCBcInNpbmNlIG91ciBsYXN0IG1ham9yIHN5bmNcIlxuICAgICAgICB9XG4gICAgLSBFeGFtcGxlczpcbiAgICAgICAgLSBVc2VyOiBcIlByZXAgZm9yIG15IG1lZXRpbmcgd2l0aCBTYWxlcyBUZWFtIGFib3V0IFE0IHN0cmF0ZWd5LiBDaGVjayBlbWFpbHMgZnJvbSBzYWxlc19sZWFkQGV4YW1wbGUuY29tIG9uIHRoaXMsIFNsYWNrIGluICNzYWxlcyBjaGFubmVsLCBhbmQgTm90aW9uIGRvY3MgdGl0bGVkICdRNCBTdHJhdGVneScuXCJcbiAgICAgICAgICBSZXNwb25zZToge1xuICAgICAgICAgICAgXCJpbnRlbnRcIjogXCJSZXF1ZXN0TWVldGluZ1ByZXBhcmF0aW9uXCIsXG4gICAgICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgXCJtZWV0aW5nX3JlZmVyZW5jZVwiOiBcIm1lZXRpbmcgd2l0aCBTYWxlcyBUZWFtIGFib3V0IFE0IHN0cmF0ZWd5XCIsXG4gICAgICAgICAgICAgIFwiaW5mb3JtYXRpb25fcmVxdWVzdHNcIjogW1xuICAgICAgICAgICAgICAgIHtcInNvdXJjZVwiOiBcImdtYWlsXCIsIFwic2VhcmNoX3BhcmFtZXRlcnNcIjoge1wiZnJvbV9zZW5kZXJcIjogXCJzYWxlc19sZWFkQGV4YW1wbGUuY29tXCIsIFwiYm9keV9rZXl3b3Jkc1wiOiBcIlE0IHN0cmF0ZWd5XCJ9fSxcbiAgICAgICAgICAgICAgICB7XCJzb3VyY2VcIjogXCJzbGFja1wiLCBcInNlYXJjaF9wYXJhbWV0ZXJzXCI6IHtcImNoYW5uZWxfbmFtZVwiOiBcIiNzYWxlc1wiLCBcInRleHRfa2V5d29yZHNcIjogXCJRNCBzdHJhdGVneVwifX0sXG4gICAgICAgICAgICAgICAge1wic291cmNlXCI6IFwibm90aW9uXCIsIFwic2VhcmNoX3BhcmFtZXRlcnNcIjoge1wicGFnZV90aXRsZV9rZXl3b3Jkc1wiOiBcIlE0IFN0cmF0ZWd5XCJ9fVxuICAgICAgICAgICAgICBdXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAtIFVzZXI6IFwiR2V0IG1lIHJlYWR5IGZvciB0aGUgMTBhbSBjbGllbnQgY2FsbCB3aXRoIEFjbWUgQ29ycCB0b21vcnJvdy4gRmluZCByZWNlbnQgZW1haWxzIHdpdGggJ0FjbWUgQ29ycCcgYW5kIGFueSBub3RlcyBmcm9tIG91ciBOb3Rpb24gcHJvamVjdCBwYWdlIGZvciAnQWNtZSBQcm9qZWN0Jy4gQWxzbywgc2VlIHdoYXQgb3VyIGxhc3QgY2FsZW5kYXIgZXZlbnQgd2l0aCB0aGVtIHdhcyBhYm91dC5cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgICAgICBcImludGVudFwiOiBcIlJlcXVlc3RNZWV0aW5nUHJlcGFyYXRpb25cIixcbiAgICAgICAgICAgIFwiZW50aXRpZXNcIjoge1xuICAgICAgICAgICAgICBcIm1lZXRpbmdfcmVmZXJlbmNlXCI6IFwiMTBhbSBjbGllbnQgY2FsbCB3aXRoIEFjbWUgQ29ycCB0b21vcnJvd1wiLFxuICAgICAgICAgICAgICBcImluZm9ybWF0aW9uX3JlcXVlc3RzXCI6IFtcbiAgICAgICAgICAgICAgICB7XCJzb3VyY2VcIjogXCJnbWFpbFwiLCBcInNlYXJjaF9wYXJhbWV0ZXJzXCI6IHtcImJvZHlfa2V5d29yZHNcIjogXCJBY21lIENvcnBcIiwgXCJkYXRlX3F1ZXJ5XCI6IFwicmVjZW50XCJ9fSxcbiAgICAgICAgICAgICAgICB7XCJzb3VyY2VcIjogXCJub3Rpb25cIiwgXCJzZWFyY2hfcGFyYW1ldGVyc1wiOiB7XCJwYWdlX3RpdGxlX2tleXdvcmRzXCI6IFwiQWNtZSBQcm9qZWN0XCIsIFwiY29udGVudF9rZXl3b3Jkc1wiOiBcIkFjbWUgQ29ycFwifX0sXG4gICAgICAgICAgICAgICAge1wic291cmNlXCI6IFwiY2FsZW5kYXJfZXZlbnRzXCIsIFwic2VhcmNoX3BhcmFtZXRlcnNcIjoge1wicmVsYXRlZF90b19hdHRlbmRlZXNfb2ZfbWVldGluZ19yZWZlcmVuY2VcIjogdHJ1ZSwgXCJ0eXBlX2ZpbHRlclwiOiBcInBhc3RfZXZlbnRzXCJ9fVxuICAgICAgICAgICAgICBdLFxuICAgICAgICAgICAgICBcIm92ZXJhbGxfbG9va2JhY2tfcGVyaW9kXCI6IFwicmVjZW50XCJcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG5cbjM2LiBJbnRlbnQ6IFwiUHJvY2Vzc01lZXRpbmdPdXRjb21lc1wiXG4gICAgLSBQdXJwb3NlOiBUbyBwcm9jZXNzIHRoZSBvdXRjb21lcyBvZiBhIHNwZWNpZmllZCBtZWV0aW5nIChlLmcuLCBmcm9tIGEgdHJhbnNjcmlwdCBvciBub3RlcykgYW5kIHBlcmZvcm0gYWN0aW9ucyBsaWtlIHN1bW1hcml6aW5nIGRlY2lzaW9ucywgZHJhZnRpbmcgZm9sbG93LXVwIGVtYWlscywgb3IgY3JlYXRpbmcgdGFza3MuXG4gICAgLSBFbnRpdGllczpcbiAgICAgICAgLSBcIm1lZXRpbmdfcmVmZXJlbmNlXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJJZGVudGlmaWVyIGZvciB0aGUgbWVldGluZyB3aG9zZSBvdXRjb21lcyBhcmUgdG8gYmUgcHJvY2Vzc2VkLiBDYW4gYmUgYSBtZWV0aW5nIHRpdGxlLCBhIHJlZmVyZW5jZSB0byBhIHRyYW5zY3JpcHQsIGEgY2FsZW5kYXIgZXZlbnQsIG9yIGEgcmVjZW50IG1lZXRpbmcuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJzdHJpbmdcIixcbiAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZSxcbiAgICAgICAgICAgIFwiZXhhbXBsZVwiOiBcInRoZSBQcm9qZWN0IFBob2VuaXggRGVicmllZiB0cmFuc2NyaXB0XCIsIFwibXkgbGFzdCBtZWV0aW5nIHdpdGggQWNtZSBDb3JwXCIsIFwidGhlIHN0cmF0ZWd5IHNlc3Npb24gZnJvbSB5ZXN0ZXJkYXlcIlxuICAgICAgICB9LFxuICAgICAgICAtIFwic291cmNlX2RvY3VtZW50X2lkXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJPcHRpb25hbCBzcGVjaWZpYyBJRCBvZiB0aGUgc291cmNlIGRvY3VtZW50IGNvbnRhaW5pbmcgdGhlIG1lZXRpbmcgb3V0Y29tZXMgKGUuZy4sIGEgdHJhbnNjcmlwdCBJRCwgYSBOb3Rpb24gcGFnZSBJRCwgb3IgYSBmaWxlIElEIGlmIGFwcGxpY2FibGUpLiBJZiBub3QgcHJvdmlkZWQsIHRoZSBzeXN0ZW0gbWF5IHRyeSB0byBpbmZlciBmcm9tIG1lZXRpbmdfcmVmZXJlbmNlLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWVcbiAgICAgICAgfSxcbiAgICAgICAgLSBcIm91dGNvbWVfc291cmNlX3R5cGVcIjoge1xuICAgICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIlRoZSB0eXBlIG9mIHNvdXJjZSBtYXRlcmlhbCBmb3IgdGhlIG91dGNvbWVzLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcImVudW1cIjogW1widHJhbnNjcmlwdFwiLCBcIm1lZXRpbmdfbm90ZXNcIiwgXCJhdWRpb19yZWNvcmRpbmdfc3VtbWFyeVwiXSxcbiAgICAgICAgICAgIFwib3B0aW9uYWxcIjogdHJ1ZSwgXCJkZWZhdWx0XCI6IFwidHJhbnNjcmlwdFwiXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJyZXF1ZXN0ZWRfYWN0aW9uc1wiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiQW4gYXJyYXkgc3BlY2lmeWluZyB0aGUgYWN0aW9ucyB0byBiZSBwZXJmb3JtZWQgb24gdGhlIG1lZXRpbmcgb3V0Y29tZXMuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJhcnJheVwiLFxuICAgICAgICAgICAgXCJyZXF1aXJlZFwiOiB0cnVlLFxuICAgICAgICAgICAgXCJpdGVtc1wiOiB7XG4gICAgICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICAgICAgXCJlbnVtXCI6IFtcIlNVTU1BUklaRV9LRVlfREVDSVNJT05TXCIsIFwiRVhUUkFDVF9BQ1RJT05fSVRFTVNcIiwgXCJEUkFGVF9GT0xMT1dfVVBfRU1BSUxcIiwgXCJDUkVBVEVfVEFTS1NfSU5fTk9USU9OXCJdXG4gICAgICAgICAgICB9XG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJlbWFpbF9kcmFmdF9kZXRhaWxzXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJEZXRhaWxzIGZvciBkcmFmdGluZyBhIGZvbGxvdy11cCBlbWFpbC4gUmVxdWlyZWQgaWYgJ0RSQUZUX0ZPTExPV19VUF9FTUFJTCcgaXMgaW4gcmVxdWVzdGVkX2FjdGlvbnMuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJvYmplY3RcIixcbiAgICAgICAgICAgIFwib3B0aW9uYWxcIjogdHJ1ZSxcbiAgICAgICAgICAgIFwicHJvcGVydGllc1wiOiB7XG4gICAgICAgICAgICAgICAgXCJyZWNpcGllbnRzXCI6IFwiYXJyYXkgb2Ygc3RyaW5ncyAoZS5nLiwgWydhdHRlbmRlZXMnLCAnam9obi5kb2VAZXhhbXBsZS5jb20nLCAnU2FsZXMgVGVhbSddKSBvciBhIHN0cmluZyAoZS5nLiwgJ2FsbCBtZWV0aW5nIGF0dGVuZGVlcycpXCIsXG4gICAgICAgICAgICAgICAgXCJhZGRpdGlvbmFsX2luc3RydWN0aW9uc1wiOiBcInN0cmluZyAoZS5nLiwgJ0tlZXAgaXQgY29uY2lzZScsICdGb2N1cyBvbiBkZWxpdmVyYWJsZXMnKVwiXG4gICAgICAgICAgICB9XG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJ0YXNrX2NyZWF0aW9uX2RldGFpbHNcIjoge1xuICAgICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIkRldGFpbHMgZm9yIGNyZWF0aW5nIHRhc2tzLiBSZWxldmFudCBpZiAnQ1JFQVRFX1RBU0tTX0lOX05PVElPTicgb3IgJ0VYVFJBQ1RfQUNUSU9OX0lURU1TJyAod2l0aCBpbnRlbnQgdG8gY3JlYXRlIHRhc2tzKSBpcyBpbiByZXF1ZXN0ZWRfYWN0aW9ucy5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcIm9iamVjdFwiLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlLFxuICAgICAgICAgICAgXCJwcm9wZXJ0aWVzXCI6IHtcbiAgICAgICAgICAgICAgICBcIm5vdGlvbl9kYXRhYmFzZV9pZFwiOiBcInN0cmluZyAoT3B0aW9uYWwgSUQgb2YgdGhlIE5vdGlvbiBkYXRhYmFzZSBmb3IgdGFza3M7IGRlZmF1bHRzIHRvIHVzZXIncyBwcmltYXJ5IHRhc2sgREIgaWYgbm90IHNwZWNpZmllZClcIixcbiAgICAgICAgICAgICAgICBcImRlZmF1bHRfYXNzaWduZWVcIjogXCJzdHJpbmcgKE9wdGlvbmFsIGRlZmF1bHQgYXNzaWduZWUgZm9yIG5ldyB0YXNrcywgZS5nLiwgJ21lJywgJ3Byb2plY3RfbGVhZEBleGFtcGxlLmNvbScpXCJcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIC0gRXhhbXBsZXM6XG4gICAgICAgIC0gVXNlcjogXCJGb3IgdGhlICdRMSBSZXZpZXcgbWVldGluZycsIHN1bW1hcml6ZSBkZWNpc2lvbnMsIGV4dHJhY3QgYWN0aW9uIGl0ZW1zLCBhbmQgZHJhZnQgYW4gZW1haWwgdG8gYXR0ZW5kZWVzLlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiUHJvY2Vzc01lZXRpbmdPdXRjb21lc1wiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwibWVldGluZ19yZWZlcmVuY2VcIjogXCJRMSBSZXZpZXcgbWVldGluZ1wiLFxuICAgICAgICAgICAgICBcInJlcXVlc3RlZF9hY3Rpb25zXCI6IFtcIlNVTU1BUklaRV9LRVlfREVDSVNJT05TXCIsIFwiRVhUUkFDVF9BQ1RJT05fSVRFTVNcIiwgXCJEUkFGVF9GT0xMT1dfVVBfRU1BSUxcIl0sXG4gICAgICAgICAgICAgIFwiZW1haWxfZHJhZnRfZGV0YWlsc1wiOiB7XCJyZWNpcGllbnRzXCI6IFwiYXR0ZW5kZWVzXCJ9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAtIFVzZXI6IFwiRnJvbSB0aGUgdHJhbnNjcmlwdCBJRCAneHl6MTIzJywgY3JlYXRlIHRhc2tzIGluIE5vdGlvbiBmb3IgYW55IGFjdGlvbiBpdGVtcyBmb3VuZC5cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgICAgICBcImludGVudFwiOiBcIlByb2Nlc3NNZWV0aW5nT3V0Y29tZXNcIixcbiAgICAgICAgICAgIFwiZW50aXRpZXNcIjoge1xuICAgICAgICAgICAgICBcIm1lZXRpbmdfcmVmZXJlbmNlXCI6IFwidHJhbnNjcmlwdCBJRCAneHl6MTIzJ1wiLFxuICAgICAgICAgICAgICBcInNvdXJjZV9kb2N1bWVudF9pZFwiOiBcInh5ejEyM1wiLFxuICAgICAgICAgICAgICBcIm91dGNvbWVfc291cmNlX3R5cGVcIjogXCJ0cmFuc2NyaXB0XCIsXG4gICAgICAgICAgICAgIFwicmVxdWVzdGVkX2FjdGlvbnNcIjogW1wiRVhUUkFDVF9BQ1RJT05fSVRFTVNcIiwgXCJDUkVBVEVfVEFTS1NfSU5fTk9USU9OXCJdXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAtIFVzZXI6IFwiUHJvY2VzcyBteSBsYXN0IG1lZXRpbmc6IHN1bW1hcml6ZSBkZWNpc2lvbnMgYW5kIGV4dHJhY3QgYWN0aW9uIGl0ZW1zLlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiUHJvY2Vzc01lZXRpbmdPdXRjb21lc1wiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwibWVldGluZ19yZWZlcmVuY2VcIjogXCJteSBsYXN0IG1lZXRpbmdcIixcbiAgICAgICAgICAgICAgXCJyZXF1ZXN0ZWRfYWN0aW9uc1wiOiBbXCJTVU1NQVJJWkVfS0VZX0RFQ0lTSU9OU1wiLCBcIkVYVFJBQ1RfQUNUSU9OX0lURU1TXCJdXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG4zNy4gSW50ZW50OiBcIkdldERhaWx5UHJpb3JpdHlCcmllZmluZ1wiXG4gICAgLSBQdXJwb3NlOiBUbyBwcm92aWRlIHRoZSB1c2VyIHdpdGggYSBjb25zb2xpZGF0ZWQgb3ZlcnZpZXcgb2YgdGhlaXIgaW1wb3J0YW50IHRhc2tzLCBtZWV0aW5ncywgYW5kIHBvdGVudGlhbGx5IG1lc3NhZ2VzIGZvciBhIGdpdmVuIGRheSAoZGVmYXVsdGluZyB0byB0b2RheSkuXG4gICAgLSBFbnRpdGllczpcbiAgICAgICAgLSBcImRhdGVfY29udGV4dFwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiU3BlY2lmaWVzIHRoZSBkYXkgZm9yIHdoaWNoIHRoZSBicmllZmluZyBpcyByZXF1ZXN0ZWQuIERlZmF1bHRzIHRvICd0b2RheScgaWYgbm90IG1lbnRpb25lZC5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlLFxuICAgICAgICAgICAgXCJleGFtcGxlXCI6IFwidG9kYXlcIiwgXCJ0b21vcnJvd1wiLCBcImZvciB0aGlzIE1vbmRheVwiXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJmb2N1c19hcmVhc1wiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiT3B0aW9uYWwgYXJyYXkgdG8gc3BlY2lmeSB3aGljaCBhcmVhcyB0byBpbmNsdWRlIGluIHRoZSBicmllZmluZy4gSWYgZW1wdHkgb3Igbm90IHByb3ZpZGVkLCBhbGwgcHJpbWFyeSBhcmVhcyAodGFza3MsIG1lZXRpbmdzLCB1cmdlbnQgbWVzc2FnZXMpIGFyZSB0eXBpY2FsbHkgaW5jbHVkZWQuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJhcnJheVwiLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlLFxuICAgICAgICAgICAgXCJpdGVtc1wiOiB7XG4gICAgICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICAgICAgXCJlbnVtXCI6IFtcInRhc2tzXCIsIFwibWVldGluZ3NcIiwgXCJ1cmdlbnRfZW1haWxzXCIsIFwidXJnZW50X3NsYWNrX21lc3NhZ2VzXCIsIFwidXJnZW50X3RlYW1zX21lc3NhZ2VzXCJdXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgXCJleGFtcGxlXCI6IFwiW1xcXCJ0YXNrc1xcXCIsIFxcXCJtZWV0aW5nc1xcXCJdXCJcbiAgICAgICAgfSxcbiAgICAgICAgLSBcInByb2plY3RfZmlsdGVyXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJPcHRpb25hbCBmaWx0ZXIgdG8gZ2V0IHByaW9yaXRpZXMgcmVsYXRlZCB0byBhIHNwZWNpZmljIHByb2plY3QgbmFtZSBvciBrZXl3b3JkLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWUsXG4gICAgICAgICAgICBcImV4YW1wbGVcIjogXCJQcm9qZWN0IEFscGhhXCIsIFwidGhlIFE0IGxhdW5jaFwiXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJ1cmdlbmN5X2xldmVsXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJPcHRpb25hbCBmaWx0ZXIgZm9yIHVyZ2VuY3ksIGUuZy4sIG9ubHkgc2hvdyBoaWdoIHByaW9yaXR5IHRhc2tzIG9yIGNyaXRpY2FsIG1lc3NhZ2VzLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcImVudW1cIjogW1wiaGlnaFwiLCBcImNyaXRpY2FsXCIsIFwiYWxsXCJdLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlLFxuICAgICAgICAgICAgXCJkZWZhdWx0XCI6IFwiYWxsXCIsXG4gICAgICAgICAgICBcImV4YW1wbGVcIjogXCJoaWdoIHByaW9yaXR5IG9ubHlcIlxuICAgICAgICB9XG4gICAgLSBFeGFtcGxlczpcbiAgICAgICAgLSBVc2VyOiBcIldoYXQgYXJlIG15IHRvcCBwcmlvcml0aWVzIGZvciB0b2RheT9cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgICAgICBcImludGVudFwiOiBcIkdldERhaWx5UHJpb3JpdHlCcmllZmluZ1wiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwiZGF0ZV9jb250ZXh0XCI6IFwidG9kYXlcIlxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgLSBVc2VyOiBcIlNob3cgbWUgbXkgdGFza3MgYW5kIG1lZXRpbmdzIGZvciB0b21vcnJvdyBmb3IgUHJvamVjdCBQaG9lbml4LlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiR2V0RGFpbHlQcmlvcml0eUJyaWVmaW5nXCIsXG4gICAgICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgXCJkYXRlX2NvbnRleHRcIjogXCJ0b21vcnJvd1wiLFxuICAgICAgICAgICAgICBcImZvY3VzX2FyZWFzXCI6IFtcInRhc2tzXCIsIFwibWVldGluZ3NcIl0sXG4gICAgICAgICAgICAgIFwicHJvamVjdF9maWx0ZXJcIjogXCJQcm9qZWN0IFBob2VuaXhcIlxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgLSBVc2VyOiBcIldoYXQgdXJnZW50IGVtYWlscyBkbyBJIGhhdmUgdG9kYXk/XCJcbiAgICAgICAgICBSZXNwb25zZToge1xuICAgICAgICAgICAgXCJpbnRlbnRcIjogXCJHZXREYWlseVByaW9yaXR5QnJpZWZpbmdcIixcbiAgICAgICAgICAgIFwiZW50aXRpZXNcIjoge1xuICAgICAgICAgICAgICBcImRhdGVfY29udGV4dFwiOiBcInRvZGF5XCIsXG4gICAgICAgICAgICAgIFwiZm9jdXNfYXJlYXNcIjogW1widXJnZW50X2VtYWlsc1wiXVxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgLSBVc2VyOiBcIkdpdmUgbWUgdGhlIGhpZ2ggcHJpb3JpdHkgaXRlbXMgZm9yIHRvZGF5LlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiR2V0RGFpbHlQcmlvcml0eUJyaWVmaW5nXCIsXG4gICAgICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgICBcImRhdGVfY29udGV4dFwiOiBcInRvZGF5XCIsXG4gICAgICAgICAgICAgICAgXCJ1cmdlbmN5X2xldmVsXCI6IFwiaGlnaFwiXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG4zOC4gSW50ZW50OiBcIkNyZWF0ZVRhc2tGcm9tQ2hhdE1lc3NhZ2VcIlxuICAgIC0gUHVycG9zZTogVG8gY3JlYXRlIGEgdGFzayBpbiBhIHRhc2sgbWFuYWdlbWVudCBzeXN0ZW0gKGUuZy4sIE5vdGlvbikgYmFzZWQgb24gdGhlIGNvbnRlbnQgb2YgYSBzcGVjaWZpYyBjaGF0IG1lc3NhZ2UgZnJvbSBwbGF0Zm9ybXMgbGlrZSBTbGFjayBvciBUZWFtcy5cbiAgICAtIEVudGl0aWVzOlxuICAgICAgICAtIFwiY2hhdF9tZXNzYWdlX3JlZmVyZW5jZVwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiSW5mb3JtYXRpb24gdG8gaWRlbnRpZnkgdGhlIHNwZWNpZmljIGNoYXQgbWVzc2FnZS4gVGhpcyBjb3VsZCBiZSBhIGRpcmVjdCBsaW5rIHRvIHRoZSBtZXNzYWdlLCBvciBhIGRlc2NyaXB0aXZlIHJlZmVyZW5jZSBsaWtlICd0aGUgbWVzc2FnZSBmcm9tIEpvaG4gYWJvdXQgdGhlIFVJIGJ1ZyBpbiAjZGV2IGNoYW5uZWwgeWVzdGVyZGF5Jy5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJyZXF1aXJlZFwiOiB0cnVlXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJzb3VyY2VfcGxhdGZvcm1cIjoge1xuICAgICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIlRoZSBwbGF0Zm9ybSB3aGVyZSB0aGUgY2hhdCBtZXNzYWdlIG9yaWdpbmF0ZWQuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJzdHJpbmdcIixcbiAgICAgICAgICAgIFwiZW51bVwiOiBbXCJzbGFja1wiLCBcIm1zdGVhbXNcIiwgXCJnbWFpbF90aHJlYWRfaXRlbVwiXSxcbiAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZSxcbiAgICAgICAgICAgIFwiZXhhbXBsZVwiOiBcInNsYWNrXCIsIFwidGhlIG1lc3NhZ2UgZnJvbSBUZWFtc1wiXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJ0YXNrX2Rlc2NyaXB0aW9uX292ZXJyaWRlXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJPcHRpb25hbCBleHBsaWNpdCBkZXNjcmlwdGlvbiBmb3IgdGhlIHRhc2suIElmIG5vdCBwcm92aWRlZCwgdGhlIHRhc2sgZGVzY3JpcHRpb24gd2lsbCBiZSBkZXJpdmVkIGZyb20gdGhlIGNoYXQgbWVzc2FnZSBjb250ZW50LlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWVcbiAgICAgICAgfSxcbiAgICAgICAgLSBcInRhcmdldF90YXNrX2xpc3Rfb3JfcHJvamVjdFwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIG5hbWUgb3IgSUQgb2YgdGhlIHRhcmdldCBsaXN0LCBwcm9qZWN0LCBvciBkYXRhYmFzZSB3aGVyZSB0aGUgdGFzayBzaG91bGQgYmUgY3JlYXRlZCAoZS5nLiwgJ0VuZ2luZWVyaW5nIEJ1Z3MgREInLCAnQ2xpZW50IEZvbGxvdy11cHMnKS4gRGVmYXVsdHMgdG8gYSBnZW5lcmFsIHRhc2sgbGlzdCBpZiBub3Qgc3BlY2lmaWVkLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWVcbiAgICAgICAgfSxcbiAgICAgICAgLSBcImFzc2lnbmVlXCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJPcHRpb25hbCBzdWdnZXN0ZWQgYXNzaWduZWUgZm9yIHRoZSB0YXNrIChlLmcuLCAnbWUnLCAnQWxpY2UnLCAnZGV2X3RlYW1AZXhhbXBsZS5jb20nKS5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJkdWVfZGF0ZVwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiT3B0aW9uYWwgc3VnZ2VzdGVkIGR1ZSBkYXRlIGZvciB0aGUgdGFzayAoZS5nLiwgJ3RvbW9ycm93JywgJ25leHQgRnJpZGF5JywgJzIwMjQtMTItMzEnKS5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJvcHRpb25hbFwiOiB0cnVlXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJwcmlvcml0eVwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiT3B0aW9uYWwgcHJpb3JpdHkgZm9yIHRoZSB0YXNrLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwic3RyaW5nXCIsXG4gICAgICAgICAgICBcImVudW1cIjogW1wiaGlnaFwiLCBcIm1lZGl1bVwiLCBcImxvd1wiXSxcbiAgICAgICAgICAgIFwib3B0aW9uYWxcIjogdHJ1ZVxuICAgICAgICB9XG4gICAgLSBFeGFtcGxlczpcbiAgICAgICAgLSBVc2VyOiBcIkNyZWF0ZSBhIHRhc2sgZnJvbSB0aGF0IGxhc3QgU2xhY2sgbWVzc2FnZSBpbiAjc3VwcG9ydCBhYm91dCB0aGUgbG9naW4gZXJyb3IgZm9yIHRoZSAnU3VwcG9ydCBUaWNrZXRzJyBsaXN0LlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiQ3JlYXRlVGFza0Zyb21DaGF0TWVzc2FnZVwiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwiY2hhdF9tZXNzYWdlX3JlZmVyZW5jZVwiOiBcImxhc3QgU2xhY2sgbWVzc2FnZSBpbiAjc3VwcG9ydCBhYm91dCB0aGUgbG9naW4gZXJyb3JcIixcbiAgICAgICAgICAgICAgXCJzb3VyY2VfcGxhdGZvcm1cIjogXCJzbGFja1wiLFxuICAgICAgICAgICAgICBcInRhcmdldF90YXNrX2xpc3Rfb3JfcHJvamVjdFwiOiBcIlN1cHBvcnQgVGlja2V0c1wiXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG4zOS4gSW50ZW50OiBcIlNjaGVkdWxlU2tpbGxBY3RpdmF0aW9uXCJcbiAgICAtIFB1cnBvc2U6IFRvIHNjaGVkdWxlIGEgc2tpbGwgdG8gYmUgYWN0aXZhdGVkIGF0IGEgbGF0ZXIgdGltZS5cbiAgICAtIEVudGl0aWVzOlxuICAgICAgICAtIFwic2tpbGxfdG9fc2NoZWR1bGVcIjoge1xuICAgICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIlRoZSBuYW1lIG9mIHRoZSBza2lsbCB0byBzY2hlZHVsZS5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJyZXF1aXJlZFwiOiB0cnVlXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJhY3RpdmF0aW9uX3RpbWVcIjoge1xuICAgICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIlRoZSB0aW1lIGF0IHdoaWNoIHRvIGFjdGl2YXRlIHRoZSBza2lsbC5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJyZXF1aXJlZFwiOiB0cnVlXG4gICAgICAgIH0sXG4gICAgICAgIC0gXCJza2lsbF9lbnRpdGllc1wiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIGVudGl0aWVzIHRvIHBhc3MgdG8gdGhlIHNraWxsIHdoZW4gaXQgaXMgYWN0aXZhdGVkLlwiLFxuICAgICAgICAgICAgXCJ0eXBlXCI6IFwib2JqZWN0XCIsXG4gICAgICAgICAgICBcIm9wdGlvbmFsXCI6IHRydWVcbiAgICAgICAgfVxuICAgIC0gRXhhbXBsZXM6XG4gICAgICAgIC0gVXNlcjogXCJTY2hlZHVsZSB0aGUgU2VuZEVtYWlsIHNraWxsIHRvIHJ1biB0b21vcnJvdyBhdCA5YW0gd2l0aCBlbnRpdGllcyB7J3RvJzogJ3Rlc3RAZXhhbXBsZS5jb20nLCAnc3ViamVjdCc6ICdUZXN0JywgJ2JvZHknOiAnVGhpcyBpcyBhIHRlc3QnfS5cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgICAgICBcImludGVudFwiOiBcIlNjaGVkdWxlU2tpbGxBY3RpdmF0aW9uXCIsXG4gICAgICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgXCJza2lsbF90b19zY2hlZHVsZVwiOiBcIlNlbmRFbWFpbFwiLFxuICAgICAgICAgICAgICBcImFjdGl2YXRpb25fdGltZVwiOiBcInRvbW9ycm93IGF0IDlhbVwiLFxuICAgICAgICAgICAgICBcInNraWxsX2VudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgICBcInRvXCI6IFwidGVzdEBleGFtcGxlLmNvbVwiLFxuICAgICAgICAgICAgICAgIFwic3ViamVjdFwiOiBcIlRlc3RcIixcbiAgICAgICAgICAgICAgICBcImJvZHlcIjogXCJUaGlzIGlzIGEgdGVzdFwiXG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIC0gVXNlcjogXCJNYWtlIGEgdGFzayBmcm9tIEJvYidzIFRlYW1zIG1lc3NhZ2U6IGh0dHBzOi8vdGVhbXMubWljcm9zb2Z0LmNvbS9sL21lc3NhZ2UvY2hhbm5lbF9pZC9tZXNzYWdlX2lkLiBDYWxsIGl0ICdSZXZpZXcgcHJvcG9zYWwnIGFuZCBhc3NpZ24gaXQgdG8gbWUgZm9yIHRvbW9ycm93LlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiQ3JlYXRlVGFza0Zyb21DaGF0TWVzc2FnZVwiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwiY2hhdF9tZXNzYWdlX3JlZmVyZW5jZVwiOiBcImh0dHBzOi8vdGVhbXMubWljcm9zb2Z0LmNvbS9sL21lc3NhZ2UvY2hhbm5lbF9pZC9tZXNzYWdlX2lkXCIsXG4gICAgICAgICAgICAgIFwic291cmNlX3BsYXRmb3JtXCI6IFwibXN0ZWFtc1wiLFxuICAgICAgICAgICAgICBcInRhc2tfZGVzY3JpcHRpb25fb3ZlcnJpZGVcIjogXCJSZXZpZXcgcHJvcG9zYWxcIixcbiAgICAgICAgICAgICAgXCJhc3NpZ25lZVwiOiBcIm1lXCIsXG4gICAgICAgICAgICAgIFwiZHVlX2RhdGVcIjogXCJ0b21vcnJvd1wiXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAtIFVzZXI6IFwiQWRkIHRoaXMgZW1haWwgaXRlbSBmcm9tIEphbmUgYXMgYSBoaWdoIHByaW9yaXR5IHRhc2s6IFtsaW5rX29yX2lkX3RvX2VtYWlsX2l0ZW1dXCJcbiAgICAgICAgICBSZXNwb25zZToge1xuICAgICAgICAgICAgXCJpbnRlbnRcIjogXCJDcmVhdGVUYXNrRnJvbUNoYXRNZXNzYWdlXCIsXG4gICAgICAgICAgICBcImVudGl0aWVzXCI6IHtcbiAgICAgICAgICAgICAgXCJjaGF0X21lc3NhZ2VfcmVmZXJlbmNlXCI6IFwiW2xpbmtfb3JfaWRfdG9fZW1haWxfaXRlbV1cIixcbiAgICAgICAgICAgICAgXCJzb3VyY2VfcGxhdGZvcm1cIjogXCJnbWFpbF90aHJlYWRfaXRlbVwiLFxuICAgICAgICAgICAgICBcInByaW9yaXR5XCI6IFwiaGlnaFwiXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG40MC4gSW50ZW50OiBcIkNyZWF0ZUVtYWlsUmVtaW5kZXJcIlxuICAgIC0gUHVycG9zZTogVG8gY3JlYXRlIGEgcmVtaW5kZXIgZm9yIGFuIGVtYWlsLlxuICAgIC0gRW50aXRpZXM6XG4gICAgICAgIC0gXCJlbWFpbF9pZFwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIElEIG9mIHRoZSBlbWFpbCB0byBzZXQgYSByZW1pbmRlciBmb3IuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJzdHJpbmdcIixcbiAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZVxuICAgICAgICB9LFxuICAgICAgICAtIFwic2VydmljZVwiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIGVtYWlsIHNlcnZpY2UgKGUuZy4sICdnbWFpbCcsICdvdXRsb29rJykuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJzdHJpbmdcIixcbiAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZVxuICAgICAgICB9LFxuICAgICAgICAtIFwicmVtaW5kX2F0XCI6IHtcbiAgICAgICAgICAgIFwiZGVzY3JpcHRpb25cIjogXCJUaGUgZGF0ZSBhbmQgdGltZSB0byBiZSByZW1pbmRlZCAoZS5nLiwgJ3RvbW9ycm93IGF0IDlhbScsICdpbiAyIGhvdXJzJykuXCIsXG4gICAgICAgICAgICBcInR5cGVcIjogXCJzdHJpbmdcIixcbiAgICAgICAgICAgIFwicmVxdWlyZWRcIjogdHJ1ZVxuICAgICAgICB9XG4gICAgLSBFeGFtcGxlczpcbiAgICAgICAgLSBVc2VyOiBcIlJlbWluZCBtZSBhYm91dCB0aGlzIGVtYWlsIHRvbW9ycm93IGF0IDlhbS5cIlxuICAgICAgICAgIFJlc3BvbnNlOiB7XG4gICAgICAgICAgICBcImludGVudFwiOiBcIkNyZWF0ZUVtYWlsUmVtaW5kZXJcIixcbiAgICAgICAgICAgIFwiZW50aXRpZXNcIjoge1xuICAgICAgICAgICAgICBcInJlbWluZF9hdFwiOiBcInRvbW9ycm93IGF0IDlhbVwiXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG40MS4gSW50ZW50OiBcIkJyb3dzZXJcIlxuICAgIC0gUHVycG9zZTogVG8gcGVyZm9ybSBhIHRhc2sgaW4gYSB3ZWIgYnJvd3Nlci5cbiAgICAtIEVudGl0aWVzOlxuICAgICAgICAtIFwidGFza1wiOiB7XG4gICAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiVGhlIHRhc2sgdG8gcGVyZm9ybSBpbiB0aGUgYnJvd3Nlci5cIixcbiAgICAgICAgICAgIFwidHlwZVwiOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgXCJyZXF1aXJlZFwiOiB0cnVlXG4gICAgICAgIH1cbiAgICAtIEV4YW1wbGVzOlxuICAgICAgICAtIFVzZXI6IFwiR28gdG8gZ2l0aHViLmNvbSBhbmQgc2VhcmNoIGZvciAndGF1cmknLlwiXG4gICAgICAgICAgUmVzcG9uc2U6IHtcbiAgICAgICAgICAgIFwiaW50ZW50XCI6IFwiQnJvd3NlclwiLFxuICAgICAgICAgICAgXCJlbnRpdGllc1wiOiB7XG4gICAgICAgICAgICAgIFwidGFza1wiOiBcIkdvIHRvIGdpdGh1Yi5jb20gYW5kIHNlYXJjaCBmb3IgJ3RhdXJpJy5cIlxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cblxuSWYgdGhlIHVzZXIncyBpbnRlbnQgaXMgdW5jbGVhciBvciBkb2VzIG5vdCBtYXRjaCBhbnkgb2YgdGhlIGFib3ZlIHNpbmdsZSBpbnRlbnRzLCBzZXQgXCJpbnRlbnRcIiB0byBudWxsIGFuZCBcImVudGl0aWVzXCIgdG8gYW4gZW1wdHkgb2JqZWN0LlxuXG5JZiB0aGUgdXNlcidzIGludGVudCBpcyBhbWJpZ3VvdXMgb3IgY3JpdGljYWwgaW5mb3JtYXRpb24gaXMgbWlzc2luZyBmb3IgYSByZWNvZ25pemVkIHNpbmdsZSBpbnRlbnQsIHNldCBcImludGVudFwiIHRvIFwiTmVlZHNDbGFyaWZpY2F0aW9uXCIsXG5zZXQgXCJlbnRpdGllc1wiIHRvIGluY2x1ZGUgd2hhdCB3YXMgdW5kZXJzdG9vZCAoZS5nLiwge1wicGFydGlhbGx5X3VuZGVyc3Rvb2RfaW50ZW50XCI6IFwiQ3JlYXRlQ2FsZW5kYXJFdmVudFwiLCBcInN1bW1hcnlcIjogXCJNZWV0aW5nXCJ9KSxcbmFuZCBmb3JtdWxhdGUgYSBcImNsYXJpZmljYXRpb25fcXVlc3Rpb25cIiB0byBhc2sgdGhlIHVzZXIuXG5FeGFtcGxlIGZvciBOZWVkc0NsYXJpZmljYXRpb246IHtcImludGVudFwiOiBcIk5lZWRzQ2xhcmlmaWNhdGlvblwiLCBcImVudGl0aWVzXCI6IHtcInBhcnRpYWxseV91bmRlcnN0b29kX2ludGVudFwiOiBcIkNyZWF0ZUNhbGVuZGFyRXZlbnRcIiwgXCJzdW1tYXJ5XCI6IFwiVGVhbSBNZWV0aW5nIHdpdGggTWFya2V0aW5nXCJ9LCBcImNsYXJpZmljYXRpb25fcXVlc3Rpb25cIjogXCJXaGF0IGRhdGUgYW5kIHRpbWUgd291bGQgeW91IGxpa2UgdG8gc2NoZWR1bGUgdGhlIG1lZXRpbmcgZm9yLCBhbmQgd2hvIHNob3VsZCBiZSBpbnZpdGVkP1wifVxuXG5JZiBhIHVzZXIncyByZXF1ZXN0IGludm9sdmVzIG11bHRpcGxlIGRpc3RpbmN0IGFjdGlvbnMgb3IgYSBzZXF1ZW5jZSBvZiBzdGVwcyB0aGF0IGNvcnJlc3BvbmQgdG8ga25vd24gc2ltcGxlIGludGVudHMsIGlkZW50aWZ5IGl0IGFzIGEgXCJDb21wbGV4VGFza1wiLlxuVGhlIFwiZW50aXRpZXNcIiBmb3IgYSBcIkNvbXBsZXhUYXNrXCIgc2hvdWxkIGluY2x1ZGUgYW4gXCJvcmlnaW5hbF9xdWVyeVwiIGtleSB3aXRoIHRoZSB1c2VyJ3MgZnVsbCByZXF1ZXN0LCBhbmQgYSBcInN1Yl90YXNrc1wiIGtleSwgd2hpY2ggaXMgYW4gYXJyYXkgb2Ygb2JqZWN0cy5cbkVhY2ggb2JqZWN0IGluIHRoZSBcInN1Yl90YXNrc1wiIGFycmF5IHNob3VsZCBpdHNlbGYgYmUgYSBzdGFuZGFyZCBOTFUgb3V0cHV0IHN0cnVjdHVyZSBmb3IgYSBzaW1wbGUgaW50ZW50OiB7XCJpbnRlbnRcIjogXCJTdWJJbnRlbnROYW1lXCIsIFwiZW50aXRpZXNcIjogey4uLn0sIFwic3VtbWFyeV9mb3Jfc3ViX3Rhc2tcIjogXCJVc2VyLWZyaWVuZGx5IGRlc2NyaXB0aW9uIG9mIHRoaXMgc3RlcFwifS5cbkV4YW1wbGUgZm9yIENvbXBsZXhUYXNrOiBVc2VyIHNheXMgXCJCb29rIGEgZmxpZ2h0IHRvIExvbmRvbiBmb3IgbmV4dCBUdWVzZGF5IGFuZCBmaW5kIG1lIGEgaG90ZWwgbmVhciBIeWRlIFBhcmsgZm9yIDMgbmlnaHRzLlwiXG5SZXNwb25zZSAoYXNzdW1pbmcgQm9va0ZsaWdodCBhbmQgRmluZEhvdGVsIGFyZSBkZWZpbmVkIHNpbXBsZSBpbnRlbnRzKTpcbntcbiAgXCJpbnRlbnRcIjogXCJDb21wbGV4VGFza1wiLFxuICBcImVudGl0aWVzXCI6IHtcbiAgICBcIm9yaWdpbmFsX3F1ZXJ5XCI6IFwiQm9vayBhIGZsaWdodCB0byBMb25kb24gZm9yIG5leHQgVHVlc2RheSBhbmQgZmluZCBtZSBhIGhvdGVsIG5lYXIgSHlkZSBQYXJrIGZvciAzIG5pZ2h0cy5cIixcbiAgICBcInN1Yl90YXNrc1wiOiBbXG4gICAgICB7XG4gICAgICAgIFwiaW50ZW50XCI6IFwiQ3JlYXRlQ2FsZW5kYXJFdmVudFwiLCBcImVudGl0aWVzXCI6IHtcInN1bW1hcnlcIjogXCJGbGlnaHQgdG8gTG9uZG9uXCIsIFwiZGVzY3JpcHRpb25cIjogXCJCb29rIGZsaWdodCBmb3IgbmV4dCBUdWVzZGF5IHRvIExvbmRvblwifSxcbiAgICAgICAgXCJzdW1tYXJ5X2Zvcl9zdWJfdGFza1wiOiBcIkJvb2sgYSBmbGlnaHQgdG8gTG9uZG9uIGZvciBuZXh0IFR1ZXNkYXkuXCJcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIFwiaW50ZW50XCI6IFwiU2VhcmNoV2ViXCIsIFwiZW50aXRpZXNcIjoge1wicXVlcnlcIjogXCJob3RlbCBuZWFyIEh5ZGUgUGFyayBMb25kb24gMyBuaWdodHNcIn0sXG4gICAgICAgIFwic3VtbWFyeV9mb3Jfc3ViX3Rhc2tcIjogXCJGaW5kIGEgaG90ZWwgbmVhciBIeWRlIFBhcmsgaW4gTG9uZG9uIGZvciAzIG5pZ2h0cy5cIlxuICAgICAgfVxuICAgIF1cbiAgfVxufVxuSWYgeW91IGlkZW50aWZ5IGEgXCJDb21wbGV4VGFza1wiLCBkbyBub3QgYWxzbyB0cnkgdG8gcHJvY2VzcyBpdHMgcGFydHMgYXMgb25lIG9mIHRoZSBzaW1wbGVyLCBzaW5nbGUgaW50ZW50cyBpbiB0aGUgbWFpbiByZXNwb25zZS4gRm9jdXMgb24gdGhlIGRlY29tcG9zaXRpb24uXG5FbnN1cmUgc3ViX3Rhc2sgaW50ZW50cyBhcmUgY2hvc2VuIGZyb20gdGhlIGxpc3Qgb2YgYXZhaWxhYmxlIHNpbXBsZSBpbnRlbnRzLlxuXG5FeGFtcGxlIGZvciBubyBtYXRjaGluZyBpbnRlbnQ6IHtcImludGVudFwiOiBudWxsLCBcImVudGl0aWVzXCI6IHt9fVxuRXhhbXBsZSBmb3IgR2V0Q2FsZW5kYXJFdmVudHM6IHtcImludGVudFwiOiBcIkdldENhbGVuZGFyRXZlbnRzXCIsIFwiZW50aXRpZXNcIjoge1wiZGF0ZV9yYW5nZVwiOiBcInRvbW9ycm93XCIsIFwibGltaXRcIjogMywgXCJldmVudF90eXBlX2ZpbHRlclwiOiBcIkdvb2dsZSBNZWV0IGV2ZW50c1wifX1gO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdW5kZXJzdGFuZE1lc3NhZ2UoXG4gIG1lc3NhZ2U6IHN0cmluZyxcbiAgY29udmVyc2F0aW9uSGlzdG9yeT86IENoYXRDb21wbGV0aW9uTWVzc2FnZVBhcmFtW10sXG4gIGx0bUNvbnRleHQ/OiBMdG1RdWVyeVJlc3VsdFtdIHwgbnVsbCAvLyBBZGRlZCBsdG1Db250ZXh0IHBhcmFtZXRlclxuKTogUHJvbWlzZTxQcm9jZXNzZWROTFVSZXNwb25zZT4ge1xuICBjb25zdCBjbGllbnQgPSBnZXRPcGVuQUlDbGllbnQoKTtcbiAgaWYgKCFjbGllbnQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb3JpZ2luYWxNZXNzYWdlOiBtZXNzYWdlLFxuICAgICAgaW50ZW50OiBudWxsLFxuICAgICAgZW50aXRpZXM6IHt9LFxuICAgICAgZXJyb3I6ICdOTFUgc2VydmljZSBub3QgY29uZmlndXJlZDogT3BlbkFJIEFQSSBLZXkgaXMgbWlzc2luZy4nLFxuICAgIH07XG4gIH1cbiAgaWYgKCFtZXNzYWdlIHx8IG1lc3NhZ2UudHJpbSgpID09PSAnJykge1xuICAgIHJldHVybiB7XG4gICAgICBvcmlnaW5hbE1lc3NhZ2U6IG1lc3NhZ2UsXG4gICAgICBpbnRlbnQ6IG51bGwsXG4gICAgICBlbnRpdGllczoge30sXG4gICAgICBlcnJvcjogJ0lucHV0IG1lc3NhZ2UgaXMgZW1wdHkuJyxcbiAgICB9O1xuICB9XG5cbiAgaWYgKGx0bUNvbnRleHQgJiYgbHRtQ29udGV4dC5sZW5ndGggPiAwKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW05MVSBTZXJ2aWNlXSBSZWNlaXZlZCBMVE0gY29udGV4dCB3aXRoICR7bHRtQ29udGV4dC5sZW5ndGh9IGl0ZW1zLiBGaXJzdCBpdGVtIChzdW1tYXJ5KTogJHtKU09OLnN0cmluZ2lmeShsdG1Db250ZXh0WzBdLnRleHQ/LnN1YnN0cmluZygwLCAxMDApKX0uLi4gUG90ZW50aWFsIHVzZTogQXVnbWVudCBwcm9tcHRzIHRvIE5MVSBwcm92aWRlci5gXG4gICAgKTtcbiAgICAvLyBjb25zb2xlLmxvZygnW05MVSBTZXJ2aWNlXSBGdWxsIExUTSBDb250ZXh0OicsIEpTT04uc3RyaW5naWZ5KGx0bUNvbnRleHQsIG51bGwsIDIpKTsgLy8gT3B0aW9uYWw6IGZvciBtb3JlIGRldGFpbFxuICB9XG4gIC8vIFRPRE86IEZ1dHVyZSBlbmhhbmNlbWVudCAtIGluY29ycG9yYXRlIGx0bUNvbnRleHQgaW50byB0aGUgcHJvbXB0IGZvciB0aGUgTkxVIG1vZGVsLlxuICAvLyBUaGlzIG1pZ2h0IGludm9sdmUgY3JlYXRpbmcgYSBzdW1tYXJpemVkIHZlcnNpb24gb2YgbHRtQ29udGV4dCB0byBmaXQgdG9rZW4gbGltaXRzXG4gIC8vIG9yIHNlbGVjdGluZyB0aGUgbW9zdCByZWxldmFudCBwaWVjZXMgb2YgY29udGV4dC5cblxuICBjb25zdCBtZXNzYWdlczogQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW1bXSA9IFtcbiAgICB7IHJvbGU6ICdzeXN0ZW0nLCBjb250ZW50OiBTWVNURU1fUFJPTVBUIH0sXG4gICAgLi4uKGNvbnZlcnNhdGlvbkhpc3RvcnkgfHwgW10pLm1hcCgoaCkgPT4gKHtcbiAgICAgIHJvbGU6IGgucm9sZSBhcyAndXNlcicgfCAnYXNzaXN0YW50JyxcbiAgICAgIGNvbnRlbnQ6IGguY29udGVudCB8fCAnJyxcbiAgICB9KSksXG4gICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IG1lc3NhZ2UgfSxcbiAgXTtcblxuICB0cnkge1xuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBjbGllbnQuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWw6IEFUT01fTkxVX01PREVMX05BTUUsXG4gICAgICBtZXNzYWdlczogbWVzc2FnZXMsXG4gICAgICB0ZW1wZXJhdHVyZTogMC4xLFxuICAgICAgcmVzcG9uc2VfZm9ybWF0OiB7IHR5cGU6ICdqc29uX29iamVjdCcgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgIGlmICghbGxtUmVzcG9uc2UpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9yaWdpbmFsTWVzc2FnZTogbWVzc2FnZSxcbiAgICAgICAgaW50ZW50OiBudWxsLFxuICAgICAgICBlbnRpdGllczoge30sXG4gICAgICAgIGVycm9yOiAnTkxVIHNlcnZpY2UgcmVjZWl2ZWQgYW4gZW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICB0cnkge1xuICAgICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlKSBhcyBOTFVSZXNwb25zZURhdGE7XG4gICAgICBpZiAoXG4gICAgICAgIHR5cGVvZiBwYXJzZWRSZXNwb25zZS5pbnRlbnQgPT09ICd1bmRlZmluZWQnIHx8XG4gICAgICAgIHR5cGVvZiBwYXJzZWRSZXNwb25zZS5lbnRpdGllcyAhPT0gJ29iamVjdCdcbiAgICAgICkge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIG9yaWdpbmFsTWVzc2FnZTogbWVzc2FnZSxcbiAgICAgICAgICBpbnRlbnQ6IG51bGwsXG4gICAgICAgICAgZW50aXRpZXM6IHt9LFxuICAgICAgICAgIGVycm9yOiBgTkxVIHNlcnZpY2UgcmVjZWl2ZWQgbWFsZm9ybWVkIEpTT04gZnJvbSBBSTogJHtsbG1SZXNwb25zZX1gLFxuICAgICAgICB9O1xuICAgICAgfVxuXG4gICAgICBjb25zdCBwcm9jZXNzZWQ6IFByb2Nlc3NlZE5MVVJlc3BvbnNlID0ge1xuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6IG1lc3NhZ2UsXG4gICAgICAgIGludGVudDogcGFyc2VkUmVzcG9uc2UuaW50ZW50LFxuICAgICAgICBlbnRpdGllczogcGFyc2VkUmVzcG9uc2UuZW50aXRpZXMgfHwge30sXG4gICAgICAgIGNvbmZpZGVuY2U6IHBhcnNlZFJlc3BvbnNlLmNvbmZpZGVuY2UsXG4gICAgICAgIHJlY29nbml6ZWRfcGhyYXNlOiBwYXJzZWRSZXNwb25zZS5yZWNvZ25pemVkX3BocmFzZSxcbiAgICAgIH07XG5cbiAgICAgIGlmIChcbiAgICAgICAgcGFyc2VkUmVzcG9uc2UuaW50ZW50ID09PSAnTmVlZHNDbGFyaWZpY2F0aW9uJyAmJlxuICAgICAgICBwYXJzZWRSZXNwb25zZS5jbGFyaWZpY2F0aW9uX3F1ZXN0aW9uXG4gICAgICApIHtcbiAgICAgICAgcHJvY2Vzc2VkLnJlcXVpcmVzX2NsYXJpZmljYXRpb24gPSB0cnVlO1xuICAgICAgICBwcm9jZXNzZWQuY2xhcmlmaWNhdGlvbl9xdWVzdGlvbiA9XG4gICAgICAgICAgcGFyc2VkUmVzcG9uc2UuY2xhcmlmaWNhdGlvbl9xdWVzdGlvbjtcbiAgICAgICAgaWYgKHBhcnNlZFJlc3BvbnNlLnBhcnRpYWxseV91bmRlcnN0b29kX2ludGVudCkge1xuICAgICAgICAgIHByb2Nlc3NlZC5lbnRpdGllcy5wYXJ0aWFsbHlfdW5kZXJzdG9vZF9pbnRlbnQgPVxuICAgICAgICAgICAgcGFyc2VkUmVzcG9uc2UucGFydGlhbGx5X3VuZGVyc3Rvb2RfaW50ZW50O1xuICAgICAgICB9XG4gICAgICB9IGVsc2UgaWYgKFxuICAgICAgICBwYXJzZWRSZXNwb25zZS5pbnRlbnQgPT09ICdDb21wbGV4VGFzaycgJiZcbiAgICAgICAgcGFyc2VkUmVzcG9uc2UuZW50aXRpZXMgJiZcbiAgICAgICAgcGFyc2VkUmVzcG9uc2UuZW50aXRpZXMuc3ViX3Rhc2tzXG4gICAgICApIHtcbiAgICAgICAgcHJvY2Vzc2VkLnN1Yl90YXNrcyA9IHBhcnNlZFJlc3BvbnNlLmVudGl0aWVzLnN1Yl90YXNrcy5tYXAoKHN0KSA9PiAoe1xuICAgICAgICAgIGludGVudDogc3QuaW50ZW50IHx8IG51bGwsXG4gICAgICAgICAgZW50aXRpZXM6IHN0LmVudGl0aWVzIHx8IHt9LFxuICAgICAgICAgIHN1bW1hcnlfZm9yX3N1Yl90YXNrOiBzdC5zdW1tYXJ5X2Zvcl9zdWJfdGFzayB8fCAnJyxcbiAgICAgICAgfSkpO1xuICAgICAgICAvLyBLZWVwIG9yaWdpbmFsX3F1ZXJ5IGlmIHByZXNlbnQgaW4gZW50aXRpZXNcbiAgICAgICAgaWYgKHBhcnNlZFJlc3BvbnNlLmVudGl0aWVzLm9yaWdpbmFsX3F1ZXJ5KSB7XG4gICAgICAgICAgcHJvY2Vzc2VkLmVudGl0aWVzLm9yaWdpbmFsX3F1ZXJ5ID1cbiAgICAgICAgICAgIHBhcnNlZFJlc3BvbnNlLmVudGl0aWVzLm9yaWdpbmFsX3F1ZXJ5O1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIC8vIENvbmNlcHR1YWwgUG9zdC1Qcm9jZXNzaW5nIGZvciBRdWVyeUVtYWlscyBpbnRlbnQ6XG4gICAgICBpZiAocHJvY2Vzc2VkLmludGVudCA9PT0gJ1F1ZXJ5RW1haWxzJyAmJiBwcm9jZXNzZWQuZW50aXRpZXMpIHtcbiAgICAgICAgY29uc3QgeyBkYXRlX3F1ZXJ5LCAuLi5vdGhlckVudGl0aWVzIH0gPSBwcm9jZXNzZWQuZW50aXRpZXM7XG4gICAgICAgIGNvbnN0IHJlc29sdmVkRGF0ZXM6IHsgYWZ0ZXI/OiBzdHJpbmc7IGJlZm9yZT86IHN0cmluZyB9ID0ge307XG5cbiAgICAgICAgaWYgKGRhdGVfcXVlcnkgJiYgdHlwZW9mIGRhdGVfcXVlcnkgPT09ICdzdHJpbmcnKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coYFtOTFUgU2VydmljZV0gUmF3IGRhdGVfcXVlcnkgZnJvbSBMTE06IFwiJHtkYXRlX3F1ZXJ5fVwiYCk7XG4gICAgICAgICAgY29uc3Qgbm93ID0gbmV3IERhdGUoKTtcbiAgICAgICAgICBjb25zdCBmb3JtYXREYXRlID0gKGQ6IERhdGUpID0+XG4gICAgICAgICAgICBgJHtkLmdldEZ1bGxZZWFyKCl9LyR7KGQuZ2V0TW9udGgoKSArIDEpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKX0vJHtkLmdldERhdGUoKS50b1N0cmluZygpLnBhZFN0YXJ0KDIsICcwJyl9YDtcbiAgICAgICAgICBjb25zdCBsY0RhdGVRdWVyeSA9IGRhdGVfcXVlcnkudG9Mb3dlckNhc2UoKTtcblxuICAgICAgICAgIGlmIChsY0RhdGVRdWVyeSA9PT0gJ3RvZGF5Jykge1xuICAgICAgICAgICAgcmVzb2x2ZWREYXRlcy5hZnRlciA9IGZvcm1hdERhdGUoXG4gICAgICAgICAgICAgIG5ldyBEYXRlKG5vdy5zZXRIb3VycygwLCAwLCAwLCAwKSlcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmJlZm9yZSA9IGZvcm1hdERhdGUoXG4gICAgICAgICAgICAgIG5ldyBEYXRlKG5vdy5zZXRIb3VycygyMywgNTksIDU5LCA5OTkpKVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9IGVsc2UgaWYgKGxjRGF0ZVF1ZXJ5ID09PSAneWVzdGVyZGF5Jykge1xuICAgICAgICAgICAgY29uc3QgeWVzdGVyZGF5ID0gbmV3IERhdGUobm93KTtcbiAgICAgICAgICAgIHllc3RlcmRheS5zZXREYXRlKG5vdy5nZXREYXRlKCkgLSAxKTtcbiAgICAgICAgICAgIHJlc29sdmVkRGF0ZXMuYWZ0ZXIgPSBmb3JtYXREYXRlKFxuICAgICAgICAgICAgICBuZXcgRGF0ZSh5ZXN0ZXJkYXkuc2V0SG91cnMoMCwgMCwgMCwgMCkpXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgcmVzb2x2ZWREYXRlcy5iZWZvcmUgPSBmb3JtYXREYXRlKFxuICAgICAgICAgICAgICBuZXcgRGF0ZSh5ZXN0ZXJkYXkuc2V0SG91cnMoMjMsIDU5LCA1OSwgOTk5KSlcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIGlmIChsY0RhdGVRdWVyeS5pbmNsdWRlcygnbGFzdCB3ZWVrJykpIHtcbiAgICAgICAgICAgIGNvbnN0IGRheU9mV2VlayA9IG5vdy5nZXREYXkoKTtcbiAgICAgICAgICAgIGNvbnN0IGxhc3RNb25kYXkgPSBuZXcgRGF0ZShub3cpO1xuICAgICAgICAgICAgbGFzdE1vbmRheS5zZXREYXRlKG5vdy5nZXREYXRlKCkgLSBkYXlPZldlZWsgLSA2KTtcbiAgICAgICAgICAgIGxhc3RNb25kYXkuc2V0SG91cnMoMCwgMCwgMCwgMCk7XG4gICAgICAgICAgICBjb25zdCBsYXN0U3VuZGF5ID0gbmV3IERhdGUobGFzdE1vbmRheSk7XG4gICAgICAgICAgICBsYXN0U3VuZGF5LnNldERhdGUobGFzdE1vbmRheS5nZXREYXRlKCkgKyA2KTtcbiAgICAgICAgICAgIGxhc3RTdW5kYXkuc2V0SG91cnMoMjMsIDU5LCA1OSwgOTk5KTtcbiAgICAgICAgICAgIHJlc29sdmVkRGF0ZXMuYWZ0ZXIgPSBmb3JtYXREYXRlKGxhc3RNb25kYXkpO1xuICAgICAgICAgICAgcmVzb2x2ZWREYXRlcy5iZWZvcmUgPSBmb3JtYXREYXRlKGxhc3RTdW5kYXkpO1xuICAgICAgICAgIH0gZWxzZSBpZiAobGNEYXRlUXVlcnkuaW5jbHVkZXMoJ3RoaXMgd2VlaycpKSB7XG4gICAgICAgICAgICBjb25zdCBkYXlPZldlZWsgPSBub3cuZ2V0RGF5KCk7XG4gICAgICAgICAgICBjb25zdCBjdXJyZW50TW9uZGF5ID0gbmV3IERhdGUobm93KTtcbiAgICAgICAgICAgIGN1cnJlbnRNb25kYXkuc2V0RGF0ZShcbiAgICAgICAgICAgICAgbm93LmdldERhdGUoKSAtIGRheU9mV2VlayArIChkYXlPZldlZWsgPT09IDAgPyAtNiA6IDEpXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgY3VycmVudE1vbmRheS5zZXRIb3VycygwLCAwLCAwLCAwKTtcbiAgICAgICAgICAgIGNvbnN0IGN1cnJlbnRTdW5kYXkgPSBuZXcgRGF0ZShjdXJyZW50TW9uZGF5KTtcbiAgICAgICAgICAgIGN1cnJlbnRTdW5kYXkuc2V0RGF0ZShjdXJyZW50TW9uZGF5LmdldERhdGUoKSArIDYpO1xuICAgICAgICAgICAgY3VycmVudFN1bmRheS5zZXRIb3VycygyMywgNTksIDU5LCA5OTkpO1xuICAgICAgICAgICAgcmVzb2x2ZWREYXRlcy5hZnRlciA9IGZvcm1hdERhdGUoY3VycmVudE1vbmRheSk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmJlZm9yZSA9IGZvcm1hdERhdGUoY3VycmVudFN1bmRheSk7XG4gICAgICAgICAgfSBlbHNlIGlmIChsY0RhdGVRdWVyeS5pbmNsdWRlcygnbGFzdCBtb250aCcpKSB7XG4gICAgICAgICAgICBjb25zdCBmaXJzdERheUxhc3RNb250aCA9IG5ldyBEYXRlKFxuICAgICAgICAgICAgICBub3cuZ2V0RnVsbFllYXIoKSxcbiAgICAgICAgICAgICAgbm93LmdldE1vbnRoKCkgLSAxLFxuICAgICAgICAgICAgICAxXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgY29uc3QgbGFzdERheUxhc3RNb250aCA9IG5ldyBEYXRlKFxuICAgICAgICAgICAgICBub3cuZ2V0RnVsbFllYXIoKSxcbiAgICAgICAgICAgICAgbm93LmdldE1vbnRoKCksXG4gICAgICAgICAgICAgIDBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmFmdGVyID0gZm9ybWF0RGF0ZShmaXJzdERheUxhc3RNb250aCk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmJlZm9yZSA9IGZvcm1hdERhdGUobGFzdERheUxhc3RNb250aCk7XG4gICAgICAgICAgfSBlbHNlIGlmIChsY0RhdGVRdWVyeS5pbmNsdWRlcygndGhpcyBtb250aCcpKSB7XG4gICAgICAgICAgICBjb25zdCBmaXJzdERheVRoaXNNb250aCA9IG5ldyBEYXRlKFxuICAgICAgICAgICAgICBub3cuZ2V0RnVsbFllYXIoKSxcbiAgICAgICAgICAgICAgbm93LmdldE1vbnRoKCksXG4gICAgICAgICAgICAgIDFcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBjb25zdCBsYXN0RGF5VGhpc01vbnRoID0gbmV3IERhdGUoXG4gICAgICAgICAgICAgIG5vdy5nZXRGdWxsWWVhcigpLFxuICAgICAgICAgICAgICBub3cuZ2V0TW9udGgoKSArIDEsXG4gICAgICAgICAgICAgIDBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmFmdGVyID0gZm9ybWF0RGF0ZShmaXJzdERheVRoaXNNb250aCk7XG4gICAgICAgICAgICByZXNvbHZlZERhdGVzLmJlZm9yZSA9IGZvcm1hdERhdGUobGFzdERheVRoaXNNb250aCk7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKHJlc29sdmVkRGF0ZXMuYWZ0ZXIgfHwgcmVzb2x2ZWREYXRlcy5iZWZvcmUpIHtcbiAgICAgICAgICAgIHByb2Nlc3NlZC5lbnRpdGllcy5yZXNvbHZlZF9kYXRlX3JhbmdlID0gcmVzb2x2ZWREYXRlcztcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICBgW05MVSBTZXJ2aWNlXSBSZXNvbHZlZCBkYXRlX3F1ZXJ5IFwiJHtkYXRlX3F1ZXJ5fVwiIHRvOmAsXG4gICAgICAgICAgICAgIHJlc29sdmVkRGF0ZXNcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICBgW05MVSBTZXJ2aWNlXSBDb3VsZCBub3QgcmVzb2x2ZSBkYXRlX3F1ZXJ5IFwiJHtkYXRlX3F1ZXJ5fVwiIHdpdGggYmFzaWMgbG9naWMuIFBhc3NpbmcgcmF3LmBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHByb2Nlc3NlZC5pbnRlbnQgPT09ICdRdWVyeUVtYWlscycgJiYgcHJvY2Vzc2VkLmVudGl0aWVzKSB7XG4gICAgICAgICAgaWYgKCFwcm9jZXNzZWQuZW50aXRpZXMucmF3X2VtYWlsX3NlYXJjaF9xdWVyeSAmJiBtZXNzYWdlKSB7XG4gICAgICAgICAgICBwcm9jZXNzZWQuZW50aXRpZXMucmF3X2VtYWlsX3NlYXJjaF9xdWVyeSA9IG1lc3NhZ2U7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIFwiW05MVSBTZXJ2aWNlXSBMTE0gZGlkIG5vdCBleHBsaWNpdGx5IHJldHVybiAncmF3X2VtYWlsX3NlYXJjaF9xdWVyeScgZm9yIFF1ZXJ5RW1haWxzIGludGVudC4gVXNpbmcgb3JpZ2luYWwgbWVzc2FnZSBhcyBmYWxsYmFjay5cIlxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBjb25zdCBhY3Rpb25UeXBlRnJvbUxMTSA9IHByb2Nlc3NlZC5lbnRpdGllcy5hY3Rpb25fb25fZW1haWwgYXNcbiAgICAgICAgICAgIHwgRW1haWxBY3Rpb25UeXBlXG4gICAgICAgICAgICB8IHVuZGVmaW5lZDtcbiAgICAgICAgICBwcm9jZXNzZWQuZW50aXRpZXMuc3RydWN0dXJlZF9hY3Rpb25fcmVxdWVzdCA9IHtcbiAgICAgICAgICAgIGFjdGlvblR5cGU6IGFjdGlvblR5cGVGcm9tTExNIHx8ICdHRVRfRlVMTF9DT05URU5UJyxcbiAgICAgICAgICAgIGluZm9LZXl3b3JkczpcbiAgICAgICAgICAgICAgcHJvY2Vzc2VkLmVudGl0aWVzLmluZm9ybWF0aW9uX3RvX2V4dHJhY3Rfa2V5d29yZHMgfHwgdW5kZWZpbmVkLFxuICAgICAgICAgICAgbmF0dXJhbExhbmd1YWdlUXVlc3Rpb246XG4gICAgICAgICAgICAgIHByb2Nlc3NlZC5lbnRpdGllcy5uYXR1cmFsX2xhbmd1YWdlX3F1ZXN0aW9uX2Fib3V0X2VtYWlsIHx8XG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB9O1xuICAgICAgICB9XG4gICAgICB9XG4gICAgICByZXR1cm4gcHJvY2Vzc2VkO1xuICAgIH0gY2F0Y2ggKGpzb25FcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgRXJyb3IgcGFyc2luZyBOTFUgcmVzcG9uc2UgZnJvbSBBSS4gUmF3IHJlc3BvbnNlOiAke2xsbVJlc3BvbnNlfS4gRXJyb3I6ICR7anNvbkVycm9yLm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9yaWdpbmFsTWVzc2FnZTogbWVzc2FnZSxcbiAgICAgICAgaW50ZW50OiBudWxsLFxuICAgICAgICBlbnRpdGllczoge30sXG4gICAgICAgIGVycm9yOiBgRXJyb3IgcGFyc2luZyBOTFUgcmVzcG9uc2UgZnJvbSBBSS4gUmF3IHJlc3BvbnNlOiAke2xsbVJlc3BvbnNlfS4gRXJyb3I6ICR7anNvbkVycm9yLm1lc3NhZ2V9YCxcbiAgICAgIH07XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgY2FsbGluZyBPcGVuQUkgZm9yIE5MVSBzZXJ2aWNlOicsIGVycm9yLm1lc3NhZ2UpO1xuICAgIGxldCBlcnJvck1lc3NhZ2UgPVxuICAgICAgJ0ZhaWxlZCB0byB1bmRlcnN0YW5kIG1lc3NhZ2UgZHVlIHRvIGFuIE5MVSBzZXJ2aWNlIGVycm9yLic7XG4gICAgaWYgKGVycm9yLnJlc3BvbnNlPy5kYXRhPy5lcnJvcj8ubWVzc2FnZSkge1xuICAgICAgZXJyb3JNZXNzYWdlICs9IGAgQVBJIEVycm9yOiAke2Vycm9yLnJlc3BvbnNlLmRhdGEuZXJyb3IubWVzc2FnZX1gO1xuICAgIH0gZWxzZSBpZiAoZXJyb3IubWVzc2FnZSkge1xuICAgICAgZXJyb3JNZXNzYWdlICs9IGAgRGV0YWlsczogJHtlcnJvci5tZXNzYWdlfWA7XG4gICAgfVxuICAgIHJldHVybiB7XG4gICAgICBvcmlnaW5hbE1lc3NhZ2U6IG1lc3NhZ2UsXG4gICAgICBpbnRlbnQ6IG51bGwsXG4gICAgICBlbnRpdGllczoge30sXG4gICAgICBlcnJvcjogZXJyb3JNZXNzYWdlLFxuICAgIH07XG4gIH1cbn1cbiJdfQ==