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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlclJlc3BvbmRlZE1pc3NpbmdEYXRhVG9KU09OLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXNlclJlc3BvbmRlZE1pc3NpbmdEYXRhVG9KU09OLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE1BQU0sQ0FBQyxNQUFNLG9DQUFvQyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0EwQ25ELENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSwwQ0FBMEMsR0FBRzs7Q0FFekQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLDJDQUEyQyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQW1DMUQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBjb25zdCB1c2VyUmVzcG9uZGVkTWlzc2luZ0RhdGFUb0pTT05Qcm9tcHQgPSBgXG4gICAgWW91IGFyZSBhIGNhbGVuZGFyIEFJIGFzc2lzdGFudC4gWW91IHJlcXVlc3RlZCBzb21lIG1pc3NpbmcgZmllbGRzIGFuZCB0aGUgdXNlciByZXNwb25kZWQgYmFjay5cbiAgICBDb252ZXJ0IHVzZXIgaW5wdXQgcHJvdmlkZWQgaW50byBKU09OIHR5cGUgbGFuZ3VhZ2UgdXNlZCB0byB0cmlnZ2VyIGFuIEFQSSBjYWxsLiBEbyBub3QgcHJvdmlkZSBmYWxzZSB2YWx1ZXMsIHJlcGxhY2UgcGxhY2Vob2xkZXJzIHdpdGggbnVsbCBpZiBub3QgYXZhaWxhYmxlIG9yIHVua25vd24uIEpTT04gZm9ybWF0OlxuXG4gICAge1xuICAgICAgICBcImFjdGlvblwiOiBcIltBQ1RJT05dXCIsXG4gICAgICAgIFwicGFyYW1zXCI6IHtcbiAgICAgICAgICBcImF0dGVuZGVlc1wiOiBbe1xuICAgICAgICAgICAgXCJuYW1lXCI6IFwiW0FUVEVOREVFX05BTUVfMV1cIixcbiAgICAgICAgICAgIFwiZW1haWxcIjogXCJbQVRURU5ERUVfRU1BSUxfMV1cIixcbiAgICAgICAgICAgIFwiaXNIb3N0XCI6IFwiW0JPT0xFQU5dXCJcbiAgICAgICAgICB9XSxcbiAgICAgICAgICBcImRlc2NyaXB0aW9uXCI6IFwiW0RFU0NSSVBUSU9OXVwiLFxuICAgICAgICAgIFwidGFza0xpc3RcIjogW3tcbiAgICAgICAgICAgIFwidGl0bGVcIjogXCJbVEFTS18xXVwiLFxuICAgICAgICAgICAgXCJzdGF0dXNcIjogXCJbJ3RvZG8nIHwgJ2RvaW5nJyB8ICdkb25lJ11cIixcbiAgICAgICAgICAgIH1dLFxuICAgICAgICAgIFwic3VtbWFyeVwiOiBcIltTVU1NQVJZXVwiLFxuICAgICAgICAgIFwidGl0bGVcIjogXCJbVElUTEVdXCIsXG4gICAgICAgICAgXCJvbGRUaXRsZVwiOiBcIltPTERfVElUTEVdXCIsXG4gICAgICAgICAgXCJub3Rlc1wiOiBcIltOT1RFU11cIixcbiAgICAgICAgICBcInByaW9yaXR5XCI6IFwiW05VTUJFUl1cIixcbiAgICAgICAgICBcInByb2plY3RcIjogXCJbUFJPSkVDVF9USVRMRV1cIlxuICAgICAgICAgIFwibG9jYXRpb25cIjogXCJbTE9DQVRJT05dXCIsXG4gICAgICAgICAgXCJhbGFybXNcIjogW1wiW05VTUJFUl1cIl0sXG4gICAgICAgICAgXCJyZW1pbmRlck1lc3NhZ2VcIjogXCJbUkVNSU5ERVJfTUVTU0FHRV1cIixcbiAgICAgICAgICBcImF0dGFjaG1lbnRzXCI6IFtcIltBVFRBQ0hNRU5UX0ZJTEVfVVJMXVwiXSxcbiAgICAgICAgICBcImNvbmZlcmVuY2VcIjoge1xuICAgICAgICAgICAgXCJhcHBcIjogXCJbJ3pvb20nIHwgJ2dvb2dsZSddXCJcbiAgICAgICAgICB9LFxuICAgICAgICAgIFwidHJhbnNwYXJlbmN5XCI6IFwiWydvcGFxdWUnIHwgJ3RyYW5zcGFyZW50J11cIixcbiAgICAgICAgICBcInZpc2liaWxpdHlcIjogXCJbJ2RlZmF1bHQnIHwgJ3B1YmxpYycgfCAncHJpdmF0ZScgfCAnY29uZmlkZW50aWFsJ11cIixcbiAgICAgICAgICBcImlzQnJlYWtcIjogXCJbQk9PTEVBTl1cIixcbiAgICAgICAgICBcImJ1ZmZlclRpbWVcIjoge1xuICAgICAgICAgICAgXCJiZWZvcmVFdmVudFwiOiBcIltOVU1CRVJdXCIsXG4gICAgICAgICAgICBcImFmdGVyRXZlbnRcIjogXCJbTlVNQkVSXVwiXG4gICAgICAgICAgfSxcbiAgICAgICAgICBcImRlYWRsaW5lVHlwZVwiOiBcIlsnaGFyZERlYWRsaW5lJyB8ICdzb2Z0RGVhZGxpbmUnXVwiXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBHaXZlbiB1c2VyIGlucHV0OiB7e3VzZXJJbnB1dH19ICYgdXNlciBjdXJyZW50IHRpbWU6IHt7dXNlckN1cnJlbnRUaW1lfX1cbmA7XG5cbmV4cG9ydCBjb25zdCB1c2VyUmVzcG9uZGVkTWlzc2luZ0RhdGFUb0pTT05FeGFtcGxlSW5wdXQgPSBgXG4gICAgYSBtZWV0aW5nIHdpdGggSm9lIG9uIFR1ZXNkYXkgZm9yIE1hcmtldGluZyBwcmVzZW50YXRpb25cbmA7XG5cbmV4cG9ydCBjb25zdCB1c2VyUmVzcG9uZGVkTWlzc2luZ0RhdGFUb0pTT05FeGFtcGxlT3V0cHV0ID0gYFxue1xuICAgIFwiYWN0aW9uXCI6IFwic2NoZWR1bGVNZWV0aW5nXCIsXG4gICAgXCJwYXJhbXNcIjoge1xuICAgICAgXCJhdHRlbmRlZXNcIjogW1xuICAgICAgICB7XG4gICAgICAgICAgXCJuYW1lXCI6IFwiSm9lXCIsXG4gICAgICAgICAgXCJlbWFpbFwiOiBudWxsXG4gICAgICAgIH1cbiAgICAgIF0sXG4gICAgICBcImRlc2NyaXB0aW9uXCI6IFwiTWFya2V0aW5nIHByZXNlbnRhdGlvblwiLFxuICAgICAgXCJ0YXNrTGlzdFwiOiBbXSxcbiAgICAgIFwic3VtbWFyeVwiOiBudWxsLFxuICAgICAgXCJ0aXRsZVwiOiBcIk1lZXRpbmcgd2l0aCBKb2VcIixcbiAgICAgIFwibm90ZXNcIjogbnVsbCxcbiAgICAgIFwicHJpb3JpdHlcIjogbnVsbCxcbiAgICAgIFwicHJvamVjdFwiOiBudWxsLFxuICAgICAgXCJsb2NhdGlvblwiOiBudWxsLFxuICAgICAgXCJhbGFybXNcIjogW10sXG4gICAgICBcInJlbWluZGVyTWVzc2FnZVwiOiBudWxsLFxuICAgICAgXCJhdHRhY2htZW50c1wiOiBbXSxcbiAgICAgIFwiaXNGb2xsb3dVcFwiOiBudWxsLFxuICAgICAgXCJjb25mZXJlbmNlXCI6IHtcbiAgICAgICAgXCJhcHBcIjogbnVsbFxuICAgICAgfSxcbiAgICAgIFwidHJhbnNwYXJlbmN5XCI6IG51bGwsXG4gICAgICBcInZpc2liaWxpdHlcIjogbnVsbCxcbiAgICAgIFwiaXNCcmVha1wiOiBudWxsLFxuICAgICAgXCJidWZmZXJUaW1lXCI6IHtcbiAgICAgICAgXCJiZWZvcmVFdmVudFwiOiBudWxsLFxuICAgICAgICBcImFmdGVyRXZlbnRcIjogbnVsbFxuICAgICAgfSxcbiAgICAgIFwiZGVhZGxpbmVUeXBlXCI6IG51bGxcbiAgICB9XG4gIH1cbmA7XG4iXX0=