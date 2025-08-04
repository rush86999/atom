export const userInputToJSONPrompt = `
    You are a user input to json format parser. Convert user input command provided to an AI calendar assistant into JSON type language used to trigger an API call. Do not provide false values, replace placeholders with null if not available or unknown. If exact values not provided, set unclear values as null. Do not make assumptions on input generally. Pseudo JSON format: 
    
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
            "task": "[TASK]",
            "duration": "[DURATION]", // duration of task in number of minutes value if any for a single event. Valid only if < 6 hours
            "status": "['todo' | 'doing' | 'done']",
            "taskListName": "[TASK_LIST_NAME]"
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
          "deadlineType": "['hardDeadline' | 'softDeadline']",
          "startTime": "[YYYY-MM-DDTHH:mm:ssZ]",
          "endTime": "[YYYY-MM-DDTHH:mm:ssZ]",
          "recurrence": {
            "frequency": "['daily' | 'weekly' | 'monthly' | 'yearly']",
            "interval": "[NUMBER]",
            "endDate": "[YYYY-MM-DDTHH:mm:ssZ]"
          }
        }
    }

user current time: {{userCurrentTime}}
`;

// export const userInputToJSONTemplate = `
//     Given user input: {{userInput}} &
// `

export const userInputToJSONExampleInput = `
    schedule a meeting with Joe on Tuesday for Marketing presentation
`;

export const userInputToJSONExampleOutput = `
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
