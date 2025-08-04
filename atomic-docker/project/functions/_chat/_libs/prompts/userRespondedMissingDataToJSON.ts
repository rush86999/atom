export const userRespondedMissingDataToJSONPrompt = `
    You are a calendar AI assistant. You requested some missing fields and the user responded back.
    Convert user input provided into JSON type language used to trigger an API call. Do not provide false values, replace placeholders with null if not available or unknown. JSON format:

    {
        "action": "[ACTION]",
        "params": {
          "attendees": [{
            "name": "[ATTENDEE_NAME_1]",
            "email": "[ATTENDEE_EMAIL_1]",
            "isHost": "[BOOLEAN]"
          }],
          "description": "[DESCRIPTION]",
          "taskList": [{
            "title": "[TASK_1]",
            "status": "['todo' | 'doing' | 'done']",
            }],
          "summary": "[SUMMARY]",
          "title": "[TITLE]",
          "oldTitle": "[OLD_TITLE]",
          "notes": "[NOTES]",
          "priority": "[NUMBER]",
          "project": "[PROJECT_TITLE]"
          "location": "[LOCATION]",
          "alarms": ["[NUMBER]"],
          "reminderMessage": "[REMINDER_MESSAGE]",
          "attachments": ["[ATTACHMENT_FILE_URL]"],
          "conference": {
            "app": "['zoom' | 'google']"
          },
          "transparency": "['opaque' | 'transparent']",
          "visibility": "['default' | 'public' | 'private' | 'confidential']",
          "isBreak": "[BOOLEAN]",
          "bufferTime": {
            "beforeEvent": "[NUMBER]",
            "afterEvent": "[NUMBER]"
          },
          "deadlineType": "['hardDeadline' | 'softDeadline']"
        }
    }

    Given user input: {{userInput}} & user current time: {{userCurrentTime}}
`;

export const userRespondedMissingDataToJSONExampleInput = `
    a meeting with Joe on Tuesday for Marketing presentation
`;

export const userRespondedMissingDataToJSONExampleOutput = `
{
    "action": "scheduleMeeting",
    "params": {
      "attendees": [
        {
          "name": "Joe",
          "email": null
        }
      ],
      "description": "Marketing presentation",
      "taskList": [],
      "summary": null,
      "title": "Meeting with Joe",
      "notes": null,
      "priority": null,
      "project": null,
      "location": null,
      "alarms": [],
      "reminderMessage": null,
      "attachments": [],
      "isFollowUp": null,
      "conference": {
        "app": null
      },
      "transparency": null,
      "visibility": null,
      "isBreak": null,
      "bufferTime": {
        "beforeEvent": null,
        "afterEvent": null
      },
      "deadlineType": null
    }
  }
`;
