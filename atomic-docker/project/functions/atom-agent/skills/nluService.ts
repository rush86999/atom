import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import {
  ATOM_OPENAI_API_KEY,
  ATOM_NLU_MODEL_NAME,
} from '../_libs/constants';
import {
  NLUResponseData,
  ProcessedNLUResponse,
  LtmQueryResult, // Import LtmQueryResult
  EmailActionType, // Assuming EmailActionType is defined in types.ts
} from '../../types'; // Adjusted path assuming types.ts is in functions/types.ts

let openAIClient: OpenAI | null = null;

export function resetOpenAIClientCache() {
  openAIClient = null;
}

function getOpenAIClient(): OpenAI | null {
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

export async function understandMessage(
  message: string,
  conversationHistory?: ChatCompletionMessageParam[],
  ltmContext?: LtmQueryResult[] | null // Added ltmContext parameter
): Promise<ProcessedNLUResponse> {
  const client = getOpenAIClient();
  if (!client) {
    return { originalMessage: message, intent: null, entities: {}, error: 'NLU service not configured: OpenAI API Key is missing.' };
  }
  if (!message || message.trim() === '') {
    return { originalMessage: message, intent: null, entities: {}, error: 'Input message is empty.' };
  }

  if (ltmContext && ltmContext.length > 0) {
    console.log(`[NLU Service] Received LTM context with ${ltmContext.length} items. First item (summary): ${JSON.stringify(ltmContext[0].text?.substring(0,100))}... Potential use: Augment prompts to NLU provider.`);
    // console.log('[NLU Service] Full LTM Context:', JSON.stringify(ltmContext, null, 2)); // Optional: for more detail
  }
  // TODO: Future enhancement - incorporate ltmContext into the prompt for the NLU model.
  // This might involve creating a summarized version of ltmContext to fit token limits
  // or selecting the most relevant pieces of context.

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...(conversationHistory || []).map(h => ({ role: h.role as 'user' | 'assistant', content: h.content || '' })),
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
      return { originalMessage: message, intent: null, entities: {}, error: 'NLU service received an empty response from AI.' };
    }

    try {
      const parsedResponse = JSON.parse(llmResponse) as NLUResponseData;
      if (typeof parsedResponse.intent === 'undefined' || typeof parsedResponse.entities !== 'object') {
        return { originalMessage: message, intent: null, entities: {}, error: `NLU service received malformed JSON from AI: ${llmResponse}` };
      }

      const processed: ProcessedNLUResponse = {
        originalMessage: message,
        intent: parsedResponse.intent,
        entities: parsedResponse.entities || {},
        confidence: parsedResponse.confidence,
        recognized_phrase: parsedResponse.recognized_phrase,
      };

      if (parsedResponse.intent === "NeedsClarification" && parsedResponse.clarification_question) {
        processed.requires_clarification = true;
        processed.clarification_question = parsedResponse.clarification_question;
        if (parsedResponse.partially_understood_intent) {
          processed.entities.partially_understood_intent = parsedResponse.partially_understood_intent;
        }
      } else if (parsedResponse.intent === "ComplexTask" && parsedResponse.entities && parsedResponse.entities.sub_tasks) {
        processed.sub_tasks = parsedResponse.entities.sub_tasks.map(st => ({
          intent: st.intent || null,
          entities: st.entities || {},
          summary_for_sub_task: st.summary_for_sub_task || ''
        }));
        // Keep original_query if present in entities
        if (parsedResponse.entities.original_query) {
          processed.entities.original_query = parsedResponse.entities.original_query;
        }
      }

      // Conceptual Post-Processing for QueryEmails intent:
      if (processed.intent === "QueryEmails" && processed.entities) {
        const { date_query, ...otherEntities } = processed.entities;
        const resolvedDates: { after?: string; before?: string } = {};

        if (date_query && typeof date_query === 'string') {
          console.log(`[NLU Service] Raw date_query from LLM: "${date_query}"`);
          const now = new Date();
          const formatDate = (d: Date) => `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;
          const lcDateQuery = date_query.toLowerCase();

          if (lcDateQuery === "today") {
            resolvedDates.after = formatDate(new Date(now.setHours(0, 0, 0, 0)));
            resolvedDates.before = formatDate(new Date(now.setHours(23, 59, 59, 999)));
          } else if (lcDateQuery === "yesterday") {
            const yesterday = new Date(now);
            yesterday.setDate(now.getDate() - 1);
            resolvedDates.after = formatDate(new Date(yesterday.setHours(0, 0, 0, 0)));
            resolvedDates.before = formatDate(new Date(yesterday.setHours(23, 59, 59, 999)));
          } else if (lcDateQuery.includes("last week")) {
            const dayOfWeek = now.getDay();
            const lastMonday = new Date(now);
            lastMonday.setDate(now.getDate() - dayOfWeek - 6);
            lastMonday.setHours(0,0,0,0);
            const lastSunday = new Date(lastMonday);
            lastSunday.setDate(lastMonday.getDate() + 6);
            lastSunday.setHours(23,59,59,999);
            resolvedDates.after = formatDate(lastMonday);
            resolvedDates.before = formatDate(lastSunday);
          } else if (lcDateQuery.includes("this week")) {
            const dayOfWeek = now.getDay();
            const currentMonday = new Date(now);
            currentMonday.setDate(now.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1) );
            currentMonday.setHours(0,0,0,0);
            const currentSunday = new Date(currentMonday);
            currentSunday.setDate(currentMonday.getDate() + 6);
            currentSunday.setHours(23,59,59,999);
            resolvedDates.after = formatDate(currentMonday);
            resolvedDates.before = formatDate(currentSunday);
          } else if (lcDateQuery.includes("last month")) {
            const firstDayLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastDayLastMonth = new Date(now.getFullYear(), now.getMonth(), 0);
            resolvedDates.after = formatDate(firstDayLastMonth);
            resolvedDates.before = formatDate(lastDayLastMonth);
          } else if (lcDateQuery.includes("this month")) {
            const firstDayThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            const lastDayThisMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            resolvedDates.after = formatDate(firstDayThisMonth);
            resolvedDates.before = formatDate(lastDayThisMonth);
          }

          if (resolvedDates.after || resolvedDates.before) {
            processed.entities.resolved_date_range = resolvedDates;
            console.log(`[NLU Service] Resolved date_query "${date_query}" to:`, resolvedDates);
          } else {
            console.log(`[NLU Service] Could not resolve date_query "${date_query}" with basic logic. Passing raw.`);
          }
        }

        if (processed.intent === "QueryEmails" && processed.entities) {
            if (!processed.entities.raw_email_search_query && message) {
                processed.entities.raw_email_search_query = message;
                console.warn("[NLU Service] LLM did not explicitly return 'raw_email_search_query' for QueryEmails intent. Using original message as fallback.");
            }

            const actionTypeFromLLM = processed.entities.action_on_email as (EmailActionType | undefined);
            processed.entities.structured_action_request = {
                actionType: actionTypeFromLLM || "GET_FULL_CONTENT",
                infoKeywords: processed.entities.information_to_extract_keywords || undefined,
                naturalLanguageQuestion: processed.entities.natural_language_question_about_email || undefined,
            };
        }
      }
      return processed;
    } catch (jsonError: any) {
      console.error(`Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}`);
      return { originalMessage: message, intent: null, entities: {}, error: `Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}` };
    }
  } catch (error: any) {
    console.error('Error calling OpenAI for NLU service:', error.message);
    let errorMessage = 'Failed to understand message due to an NLU service error.';
    if (error.response?.data?.error?.message) {
        errorMessage += ` API Error: ${error.response.data.error.message}`;
    } else if (error.message) {
        errorMessage += ` Details: ${error.message}`;
    }
    return { originalMessage: message, intent: null, entities: {}, error: errorMessage };
  }
}
