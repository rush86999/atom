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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlclJlcXVlc3RJbnB1dFRvSlNPTi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVzZXJSZXF1ZXN0SW5wdXRUb0pTT04udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsTUFBTSxDQUFDLE1BQU0scUJBQXFCLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBa0RwQyxDQUFDO0FBRUYsMkNBQTJDO0FBQzNDLHdDQUF3QztBQUN4QyxJQUFJO0FBRUosTUFBTSxDQUFDLE1BQU0sMkJBQTJCLEdBQUc7O0NBRTFDLENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSw0QkFBNEIsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FtQzNDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgY29uc3QgdXNlcklucHV0VG9KU09OUHJvbXB0ID0gYFxuICAgIFlvdSBhcmUgYSB1c2VyIGlucHV0IHRvIGpzb24gZm9ybWF0IHBhcnNlci4gQ29udmVydCB1c2VyIGlucHV0IGNvbW1hbmQgcHJvdmlkZWQgdG8gYW4gQUkgY2FsZW5kYXIgYXNzaXN0YW50IGludG8gSlNPTiB0eXBlIGxhbmd1YWdlIHVzZWQgdG8gdHJpZ2dlciBhbiBBUEkgY2FsbC4gRG8gbm90IHByb3ZpZGUgZmFsc2UgdmFsdWVzLCByZXBsYWNlIHBsYWNlaG9sZGVycyB3aXRoIG51bGwgaWYgbm90IGF2YWlsYWJsZSBvciB1bmtub3duLiBJZiBleGFjdCB2YWx1ZXMgbm90IHByb3ZpZGVkLCBzZXQgdW5jbGVhciB2YWx1ZXMgYXMgbnVsbC4gRG8gbm90IG1ha2UgYXNzdW1wdGlvbnMgb24gaW5wdXQgZ2VuZXJhbGx5LiBQc2V1ZG8gSlNPTiBmb3JtYXQ6IFxuICAgIFxuICAgIHtcbiAgICAgICAgXCJhY3Rpb25cIjogXCJbQUNUSU9OXVwiLFxuICAgICAgICBcInBhcmFtc1wiOiB7XG4gICAgICAgICAgXCJhdHRlbmRlZXNcIjogW3tcbiAgICAgICAgICAgIFwibmFtZVwiOiBcIltBVFRFTkRFRV9OQU1FXzFdXCIsXG4gICAgICAgICAgICBcImVtYWlsXCI6IFwiW0FUVEVOREVFX0VNQUlMXzFdXCIsXG4gICAgICAgICAgICBcImlzSG9zdFwiOiBcIltCT09MRUFOXVwiXG4gICAgICAgICAgfV0sXG4gICAgICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIltERVNDUklQVElPTl1cIixcbiAgICAgICAgICBcInRhc2tMaXN0XCI6IFt7XG4gICAgICAgICAgICBcInRhc2tcIjogXCJbVEFTS11cIixcbiAgICAgICAgICAgIFwiZHVyYXRpb25cIjogXCJbRFVSQVRJT05dXCIsIC8vIGR1cmF0aW9uIG9mIHRhc2sgaW4gbnVtYmVyIG9mIG1pbnV0ZXMgdmFsdWUgaWYgYW55IGZvciBhIHNpbmdsZSBldmVudC4gVmFsaWQgb25seSBpZiA8IDYgaG91cnNcbiAgICAgICAgICAgIFwic3RhdHVzXCI6IFwiWyd0b2RvJyB8ICdkb2luZycgfCAnZG9uZSddXCIsXG4gICAgICAgICAgICBcInRhc2tMaXN0TmFtZVwiOiBcIltUQVNLX0xJU1RfTkFNRV1cIlxuICAgICAgICAgICAgfV0sXG4gICAgICAgICAgXCJzdW1tYXJ5XCI6IFwiW1NVTU1BUlldXCIsXG4gICAgICAgICAgXCJ0aXRsZVwiOiBcIltUSVRMRV1cIixcbiAgICAgICAgICBcIm9sZFRpdGxlXCI6IFwiW09MRF9USVRMRV1cIixcbiAgICAgICAgICBcIm5vdGVzXCI6IFwiW05PVEVTXVwiLFxuICAgICAgICAgIFwicHJpb3JpdHlcIjogXCJbTlVNQkVSXVwiLFxuICAgICAgICAgIFwicHJvamVjdFwiOiBcIltQUk9KRUNUX1RJVExFXVwiXG4gICAgICAgICAgXCJsb2NhdGlvblwiOiBcIltMT0NBVElPTl1cIixcbiAgICAgICAgICBcImFsYXJtc1wiOiBbXCJbTlVNQkVSXVwiXSxcbiAgICAgICAgICBcInJlbWluZGVyTWVzc2FnZVwiOiBcIltSRU1JTkRFUl9NRVNTQUdFXVwiLFxuICAgICAgICAgIFwiYXR0YWNobWVudHNcIjogW1wiW0FUVEFDSE1FTlRfRklMRV9VUkxdXCJdLFxuICAgICAgICAgIFwiY29uZmVyZW5jZVwiOiB7XG4gICAgICAgICAgICBcImFwcFwiOiBcIlsnem9vbScgfCAnZ29vZ2xlJ11cIlxuICAgICAgICAgIH0sXG4gICAgICAgICAgXCJ0cmFuc3BhcmVuY3lcIjogXCJbJ29wYXF1ZScgfCAndHJhbnNwYXJlbnQnXVwiLFxuICAgICAgICAgIFwidmlzaWJpbGl0eVwiOiBcIlsnZGVmYXVsdCcgfCAncHVibGljJyB8ICdwcml2YXRlJyB8ICdjb25maWRlbnRpYWwnXVwiLFxuICAgICAgICAgIFwiaXNCcmVha1wiOiBcIltCT09MRUFOXVwiLFxuICAgICAgICAgIFwiYnVmZmVyVGltZVwiOiB7XG4gICAgICAgICAgICBcImJlZm9yZUV2ZW50XCI6IFwiW05VTUJFUl1cIixcbiAgICAgICAgICAgIFwiYWZ0ZXJFdmVudFwiOiBcIltOVU1CRVJdXCJcbiAgICAgICAgICB9LFxuICAgICAgICAgIFwiZGVhZGxpbmVUeXBlXCI6IFwiWydoYXJkRGVhZGxpbmUnIHwgJ3NvZnREZWFkbGluZSddXCIsXG4gICAgICAgICAgXCJzdGFydFRpbWVcIjogXCJbWVlZWS1NTS1ERFRISDptbTpzc1pdXCIsXG4gICAgICAgICAgXCJlbmRUaW1lXCI6IFwiW1lZWVktTU0tRERUSEg6bW06c3NaXVwiLFxuICAgICAgICAgIFwicmVjdXJyZW5jZVwiOiB7XG4gICAgICAgICAgICBcImZyZXF1ZW5jeVwiOiBcIlsnZGFpbHknIHwgJ3dlZWtseScgfCAnbW9udGhseScgfCAneWVhcmx5J11cIixcbiAgICAgICAgICAgIFwiaW50ZXJ2YWxcIjogXCJbTlVNQkVSXVwiLFxuICAgICAgICAgICAgXCJlbmREYXRlXCI6IFwiW1lZWVktTU0tRERUSEg6bW06c3NaXVwiXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgfVxuXG51c2VyIGN1cnJlbnQgdGltZToge3t1c2VyQ3VycmVudFRpbWV9fVxuYDtcblxuLy8gZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvSlNPTlRlbXBsYXRlID0gYFxuLy8gICAgIEdpdmVuIHVzZXIgaW5wdXQ6IHt7dXNlcklucHV0fX0gJlxuLy8gYFxuXG5leHBvcnQgY29uc3QgdXNlcklucHV0VG9KU09ORXhhbXBsZUlucHV0ID0gYFxuICAgIHNjaGVkdWxlIGEgbWVldGluZyB3aXRoIEpvZSBvbiBUdWVzZGF5IGZvciBNYXJrZXRpbmcgcHJlc2VudGF0aW9uXG5gO1xuXG5leHBvcnQgY29uc3QgdXNlcklucHV0VG9KU09ORXhhbXBsZU91dHB1dCA9IGBcbntcbiAgICBcImFjdGlvblwiOiBcInNjaGVkdWxlTWVldGluZ1wiLFxuICAgIFwicGFyYW1zXCI6IHtcbiAgICAgIFwiYXR0ZW5kZWVzXCI6IFtcbiAgICAgICAge1xuICAgICAgICAgIFwibmFtZVwiOiBcIkpvZVwiLFxuICAgICAgICAgIFwiZW1haWxcIjogbnVsbFxuICAgICAgICB9XG4gICAgICBdLFxuICAgICAgXCJkZXNjcmlwdGlvblwiOiBcIk1hcmtldGluZyBwcmVzZW50YXRpb25cIixcbiAgICAgIFwidGFza0xpc3RcIjogW10sXG4gICAgICBcInN1bW1hcnlcIjogbnVsbCxcbiAgICAgIFwidGl0bGVcIjogXCJNZWV0aW5nIHdpdGggSm9lXCIsXG4gICAgICBcIm5vdGVzXCI6IG51bGwsXG4gICAgICBcInByaW9yaXR5XCI6IG51bGwsXG4gICAgICBcInByb2plY3RcIjogbnVsbCxcbiAgICAgIFwibG9jYXRpb25cIjogbnVsbCxcbiAgICAgIFwiYWxhcm1zXCI6IFtdLFxuICAgICAgXCJyZW1pbmRlck1lc3NhZ2VcIjogbnVsbCxcbiAgICAgIFwiYXR0YWNobWVudHNcIjogW10sXG4gICAgICBcImlzRm9sbG93VXBcIjogbnVsbCxcbiAgICAgIFwiY29uZmVyZW5jZVwiOiB7XG4gICAgICAgIFwiYXBwXCI6IG51bGxcbiAgICAgIH0sXG4gICAgICBcInRyYW5zcGFyZW5jeVwiOiBudWxsLFxuICAgICAgXCJ2aXNpYmlsaXR5XCI6IG51bGwsXG4gICAgICBcImlzQnJlYWtcIjogbnVsbCxcbiAgICAgIFwiYnVmZmVyVGltZVwiOiB7XG4gICAgICAgIFwiYmVmb3JlRXZlbnRcIjogbnVsbCxcbiAgICAgICAgXCJhZnRlckV2ZW50XCI6IG51bGxcbiAgICAgIH0sXG4gICAgICBcImRlYWRsaW5lVHlwZVwiOiBudWxsXG4gICAgfVxuICB9XG5gO1xuIl19