export const userInputToDateTimeJSONPrompt = `
    You are a date parser with a date-time language and user intent predictor with event in regards to time via "method" key. Convert user input provided to JSON type date-time language. Do not provide false values, replace placeholders with null if unknown. If exact time not provided, set unclear values as null. Do not make assumptions on time generally. Do not predict time. Predict only user intent with event in regards to time. Only act as a date parser and user intent predictor with event in regards to time. Provide precision values up to the minute if possible. 
    main date parsed is new start date of an event or task
   "[]" describes type and value of JSON output, not part of final output
    fill in missing values if any using user current time if available. 
    user current time: {{userCurrentTime}}
    Pseudo JSON format:
    {
      "year": "[Four-digit year] [STRING]",
      "month": "[2-digits month] [STRING]",
      "day": "[2-digits day] [STRING]", // infer day from user current time if 'today' or 'tomorrow' mentioned
      "isoWeekday": "[1-7 digit day] [NUMBER]",
      "hour": "[24 hour] [NUMBER]",
      "minute": "[minutes] [NUMBER]",
      "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]", 
      "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
      "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
      "method": ["[create-event-forward | create-event-backward | create-deadline-forward | move-deadline-forward | move-deadline-backward | move-event-forward | move-event-backward | increase-duration | decrease-duration | create-time-preferences | remove-time-preferences | edit-add-time-preferences | edit-remove-time-preferences | edit-event-property | ask-calendar-question | remove-event | find-time | invite]"],
      "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
      "relativeTimeFromNow": [{
        "unit": "[minute | hour | day | week | month | year]",
        "value": "[NUMBER]"
      }], // time inclusive: 'starting from day after tomorrow' -> [{"unit": "day", "value": 2}]
      "oldDate": {
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
          "unit": "[minute | hour | day | week | month | year]",
          "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "isoWeekday": "[1-7 digit day] [NUMBER]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]",
        "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
        "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
      },
      "dueDate": {
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
          "unit": "[minute | hour | day | week | month | year]",
          "value": "[NUMBER]"
        }], // time inclusive: 'length of 2 days starting from today' -> [{"unit": "day", "value": 1}]
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "isoWeekday": "[1-7 digit day] [NUMBER]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]",
        "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
        "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
      },
      "findTimeWindowStart": { // used for time window start boundary for finding optimum time for scheduling meetings
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
          "unit": "[minute | hour | day | week | month | year]",
          "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "isoWeekday": "[1-7 digit day] [NUMBER]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]",
        "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
        "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
      },
      "findTimeWindowEnd": {   // used for time window end boundary for finding optimum time for scheduling meetings
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
          "unit": "[minute | hour | week | day | month | year]",
          "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "isoWeekday": "[1-7 digit day] [NUMBER]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]",
        "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
        "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
      },
      "recur": {
        "frequency": "['daily' | 'weekly'| 'monthly' | 'yearly']",
        "endDate": {
          "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
          "relativeTimeFromNow": [{
            "unit": "[minute | hour | day | week | month | year]",
            "value": "[NUMBER]"
          }],
          "year": "[Four-digit year] [STRING]",
          "month": "[2-digits month] [STRING]",
          "day": "[2-digits day] [STRING]",
          "isoWeekday": "[1-7 digit day] [NUMBER]",
          "hour": "[24 hour] [NUMBER]",
          "minute": "[minutes] [NUMBER]",
          "duration": "[minutes] [NUMBER] [< 6 hours format] [for a single event]",
          "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
          "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
        },
        "occurrence": "[NUMBER]",
        "interval": "[NUMBER]",
        "byWeekDay": ["['MO' | 'TU' | 'WE' | 'TH' | 'FR' | 'SA' | 'SU']"],
        "byMonthDay": ["[1 - 31]"]
      },
      "timePreferences": [{
          "dayOfWeek": ["['MO' | 'TU' | 'WE' | 'TH' | 'FR' | 'SA' | 'SU']"],
          "timeRange": {
            "startTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]",
            "endTime": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
          }
        }],
      "allDay": "[BOOLEAN]"
    }
`;
export const userInputToDateTimeJSONExampleInput1 = `
schedule a meeting with Joe on Tuesday for 2 pm for Marketing presentation
`;
export const userInputToDateTimeJSONExampleOutput1 = `
{
  "year": {{year}},
  "month": {{month}},
  "day": null,
  "isoWeekday": 2,
  "hour": 14,
  "minute": 0,
  "duration": null,
  "startTime": "14:00",
  "endTime": null,
  "method": ["create-event-forward"],
  "relativeTimeChangeFromNow": null,
  "relativeTimeFromNow": null,
  "oldDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "dueDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowStart": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowEnd": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "recur": {
    "frequency": null,
    "endDate": {
      "relativeTimeChangeFromNow": null,
      "relativeTimeFromNow": null,
      "year": null,
      "month": null,
      "day": null,
      "isoWeekday": null,
      "hour": null,
      "minute": null,
      "duration": null,
      "startTime": null,
      "endTime": null
    },
    "occurrence": null,
    "interval": null,
    "byWeekDay": null,
    "byMonthDay": null
  },
  "timePreferences": null,
  "allDay": null
}
`;
export const userInputToDateTimeJSONExampleInput2 = `
  reschedule Joe's marketing presentation scheduled 1 week from now to 3 weeks from now
`;
export const userInputToDateTimeJSONExampleOutput2 = `
 {
  "year": {{year}},
  "month": {{month}},
  "day": null,
  "isoWeekday": null,
  "hour": null,
  "minute": null,
  "duration": null,
  "startTime": null,
  "endTime": null,
  "method": ["move-event-forward"],
  "relativeTimeChangeFromNow": null,
  "relativeTimeFromNow": [
    {
      "unit": "week",
      "value": 3
    }
  ],
  "oldDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": [
      {
        "unit": "week",
        "value": 1
      }
    ],
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "dueDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowStart": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowEnd": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "recur": {
    "frequency": null,
    "endDate": {
      "relativeTimeChangeFromNow": null,
      "relativeTimeFromNow": null,
      "year": null,
      "month": null,
      "day": null,
      "isoWeekday": null,
      "hour": null,
      "minute": null,
      "duration": null,
      "startTime": null,
      "endTime": null
    },
    "occurrence": null,
    "interval": null,
    "byWeekDay": null,
    "byMonthDay": null
  },
  "timePreferences": null,
  "allDay": null
}


`;
export const userInputToDateTimeJSONExampleInput3 = `
  Find an available time slot for a team meeting with Marget, John and Ellie between tomorrow till Friday this coming week for Marketing presentation
 `;
export const userInputToDateTimeJSONExampleOutput3 = `
{
  "year": null,
  "month": null,
  "day": null,
  "isoWeekday": null,
  "hour": null,
  "minute": null,
  "duration": null,
  "startTime": null,
  "endTime": null,
  "method": ["find-time"],
  "relativeTimeChangeFromNow": null,
  "relativeTimeFromNow": null,
  "oldDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "dueDate": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": null,
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowStart": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": 1
      }
    ],
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "findTimeWindowEnd": {
    "relativeTimeChangeFromNow": null,
    "relativeTimeFromNow": [
      {
        "unit": "week",
        "value": 1
      }
    ],
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": 5,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null
  },
  "recur": {
    "frequency": null,
    "endDate": {
      "relativeTimeChangeFromNow": null,
      "relativeTimeFromNow": null,
      "year": null,
      "month": null,
      "day": null,
      "isoWeekday": null,
      "hour": null,
      "minute": null,
      "duration": null,
      "startTime": null,
      "endTime": null
    },
    "occurrence": null,
    "interval": null,
    "byWeekDay": null,
    "byMonthDay": null
  },
  "timePreferences": null,
  "allDay": null
}
`;
export const userInputToDateTimeJSONExampleInput4 = `
  create a task of building a basic user authentication system for an app. The length of the task is for 5 days and task starts tomorrow.
 `;
export const userInputToDateTimeJSONExampleOutput4 = `
{
    "year": null,
    "month": null,
    "day": null,
    "isoWeekday": null,
    "hour": null,
    "minute": null,
    "duration": null,
    "startTime": null,
    "endTime": null,
    "method": [
        "create-event-forward"
    ],
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
        {
            "unit": "day",
            "value": 1
        }
    ],
    "oldDate": {
        "relativeTimeChangeFromNow": null,
        "relativeTimeFromNow": null,
        "year": null,
        "month": null,
        "day": null,
        "isoWeekday": null,
        "hour": null,
        "minute": null,
        "duration": null,
        "startTime": null,
        "endTime": null
    },
    "dueDate": {
        "relativeTimeChangeFromNow": "add",
        "relativeTimeFromNow": [
            {
                "unit": "day",
                "value": 5
            }
        ],
        "year": null,
        "month": null,
        "day": null,
        "isoWeekday": null,
        "hour": null,
        "minute": null,
        "duration": null,
        "startTime": null,
        "endTime": null
    },
    "findTimeWindowStart": {
        "relativeTimeChangeFromNow": "add",
        "relativeTimeFromNow": null,
        "year": null,
        "month": null,
        "day": null,
        "isoWeekday": null,
        "hour": null,
        "minute": null,
        "duration": null,
        "startTime": null,
        "endTime": null
    },
    "findTimeWindowEnd": {
        "relativeTimeChangeFromNow": "add",
        "relativeTimeFromNow": null,
        "year": null,
        "month": null,
        "day": null,
        "isoWeekday": null,
        "hour": null,
        "minute": null,
        "duration": null,
        "startTime": null,
        "endTime": null
    },
    "recur": {
        "frequency": null,
        "endDate": {
            "relativeTimeChangeFromNow": null,
            "relativeTimeFromNow": null,
            "year": null,
            "month": null,
            "day": null,
            "isoWeekday": null,
            "hour": null,
            "minute": null,
            "duration": null,
            "startTime": null,
            "endTime": null
        },
        "occurrence": null,
        "interval": null,
        "byWeekDay": null,
        "byMonthDay": null
    },
    "timePreferences": null,
    "allDay": null
}
`;
export const extractQueryUserInputTimeToJSONPrompt = `
  You are a date range interpreter for user intent in the context of a work calendar. Convert user input provided to JSON type date range for an API call. Replace placeholders with null if not applicable. If exact time not provided, infer unclear values based on user input, user current time and work context. Your job as a date range interpreter, infer a time window where appropriate. Provide precision values up to the minute to set clear date range boundaries. Take work day context into account when providing ranges. Follow this pseudo JSON format:
{
    "start_date": {
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
            "unit": "[minute | hour | day | week | month | year]",
            "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "time": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
    },
    "end_date": {
        "relativeTimeChangeFromNow": "[add | subtract] [non-null if relativeTimeFromNow present, may infer]",
        "relativeTimeFromNow": [{
            "unit": "[minute | hour | day | week | month | year]",
            "value": "[NUMBER]"
        }],
        "year": "[Four-digit year] [STRING]",
        "month": "[2-digits month] [STRING]",
        "day": "[2-digits day] [STRING]",
        "hour": "[24 hour] [NUMBER]",
        "minute": "[minutes] [NUMBER]",
        "time": "[24 hour 2-digits]:[minutes 2-digits] [STRING]"
    }
}
`;
export const extractQueryUserInputTimeToJSONTemplate = `
  User current time: {{userCurrentTime}}
  User work times: {{userWorkTimes}}
  User input: {{userInput}}
`;
export const extractQueryUserInputTimeToJSONExampleInput1 = `
  User current time: Wednesday, 2023-06-21T18:56:37-04:00
  User work times: Monday: 8:00 am - 6:30 pm
  Tuesday: 8:00 am - 6:30 pm
  Wednesday: 8:00 am - 6:30 pm
  Thursday: 8:00 am - 6:30 pm
  Friday: 8:00 am - 6:30 pm
  Saturday: 8:00 am - 6:30 pm
  Sunday: 8:00 am - 6:30 pm
  User input: Do I have any meetings scheduled for tomorrow?
`;
export const extractQueryUserInputTimeToJSONExampleOutput1 = `
{
  "start_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": 1
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "22",
    "hour": "08",
    "minute": "00",
    "time": "08:00"
  },
  "end_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": 1
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "22",
    "hour": "18",
    "minute": "30",
    "time": "18:30"
  }
}
`;
export const extractQueryUserInputTimeToJSONExampleInput2 = `
  User current time: Wednesday, 2023-06-21T18:56:37-04:00
  User work times: Monday: 8:00 am - 6:30 pm
  Tuesday: 8:00 am - 6:30 pm
  Wednesday: 8:00 am - 6:30 pm
  Thursday: 8:00 am - 6:30 pm
  Friday: 8:00 am - 6:30 pm
  Saturday: 8:00 am - 6:30 pm
  Sunday: 8:00 am - 6:30 pm
  User input: When is my next appointment?
`;
export const extractQueryUserInputTimeToJSONExampleOutput2 = `
{
  "start_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": "1"
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "22",
    "hour": "08",
    "minute": "00",
    "time": "08:00"
  },
  "end_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": "1"
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "22",
    "hour": "18",
    "minute": "30",
    "time": "18:30"
  }
}
`;
export const extractQueryUserInputTimeToJSONExampleInput3 = `
  User current time: Wednesday, 2023-06-21T18:56:37-04:00
  User work times: Monday: 8:00 am - 6:30 pm
  Tuesday: 8:00 am - 6:30 pm
  Wednesday: 8:00 am - 6:30 pm
  Thursday: 8:00 am - 6:30 pm
  Friday: 8:00 am - 6:30 pm
  Saturday: 8:00 am - 6:30 pm
  Sunday: 8:00 am - 6:30 pm
  User input: Is there anything scheduled for Friday afternoon?
`;
export const extractQueryUserInputTimeToJSONExampleOutput3 = `
{
  "start_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": 2
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "23",
    "hour": "12",
    "minute": "00",
    "time": "12:00"
  },
  "end_date": {
    "relativeTimeChangeFromNow": "add",
    "relativeTimeFromNow": [
      {
        "unit": "day",
        "value": 2
      }
    ],
    "year": "2023",
    "month": "06",
    "day": "23",
    "hour": "18",
    "minute": "30",
    "time": "18:30"
  }
}

`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvbXB0cy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInByb21wdHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsTUFBTSxDQUFDLE1BQU0sNkJBQTZCLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBdUg1QyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0sb0NBQW9DLEdBQUc7O0NBRW5ELENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSxxQ0FBcUMsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F5RnBELENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSxvQ0FBb0MsR0FBRzs7Q0FFbkQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHFDQUFxQyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFHcEQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLG9DQUFvQyxHQUFHOztFQUVsRCxDQUFDO0FBRUgsTUFBTSxDQUFDLE1BQU0scUNBQXFDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQW1HcEQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLG9DQUFvQyxHQUFHOztFQUVsRCxDQUFDO0FBRUgsTUFBTSxDQUFDLE1BQU0scUNBQXFDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBcUdwRCxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0scUNBQXFDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQThCcEQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHVDQUF1QyxHQUFHOzs7O0NBSXRELENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSw0Q0FBNEMsR0FBRzs7Ozs7Ozs7OztDQVUzRCxDQUFDO0FBQ0YsTUFBTSxDQUFDLE1BQU0sNkNBQTZDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWlDNUQsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLDRDQUE0QyxHQUFHOzs7Ozs7Ozs7O0NBVTNELENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSw2Q0FBNkMsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBaUM1RCxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0sNENBQTRDLEdBQUc7Ozs7Ozs7Ozs7Q0FVM0QsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLDZDQUE2QyxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBa0M1RCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09OUHJvbXB0ID0gYFxuICAgIFlvdSBhcmUgYSBkYXRlIHBhcnNlciB3aXRoIGEgZGF0ZS10aW1lIGxhbmd1YWdlIGFuZCB1c2VyIGludGVudCBwcmVkaWN0b3Igd2l0aCBldmVudCBpbiByZWdhcmRzIHRvIHRpbWUgdmlhIFwibWV0aG9kXCIga2V5LiBDb252ZXJ0IHVzZXIgaW5wdXQgcHJvdmlkZWQgdG8gSlNPTiB0eXBlIGRhdGUtdGltZSBsYW5ndWFnZS4gRG8gbm90IHByb3ZpZGUgZmFsc2UgdmFsdWVzLCByZXBsYWNlIHBsYWNlaG9sZGVycyB3aXRoIG51bGwgaWYgdW5rbm93bi4gSWYgZXhhY3QgdGltZSBub3QgcHJvdmlkZWQsIHNldCB1bmNsZWFyIHZhbHVlcyBhcyBudWxsLiBEbyBub3QgbWFrZSBhc3N1bXB0aW9ucyBvbiB0aW1lIGdlbmVyYWxseS4gRG8gbm90IHByZWRpY3QgdGltZS4gUHJlZGljdCBvbmx5IHVzZXIgaW50ZW50IHdpdGggZXZlbnQgaW4gcmVnYXJkcyB0byB0aW1lLiBPbmx5IGFjdCBhcyBhIGRhdGUgcGFyc2VyIGFuZCB1c2VyIGludGVudCBwcmVkaWN0b3Igd2l0aCBldmVudCBpbiByZWdhcmRzIHRvIHRpbWUuIFByb3ZpZGUgcHJlY2lzaW9uIHZhbHVlcyB1cCB0byB0aGUgbWludXRlIGlmIHBvc3NpYmxlLiBcbiAgICBtYWluIGRhdGUgcGFyc2VkIGlzIG5ldyBzdGFydCBkYXRlIG9mIGFuIGV2ZW50IG9yIHRhc2tcbiAgIFwiW11cIiBkZXNjcmliZXMgdHlwZSBhbmQgdmFsdWUgb2YgSlNPTiBvdXRwdXQsIG5vdCBwYXJ0IG9mIGZpbmFsIG91dHB1dFxuICAgIGZpbGwgaW4gbWlzc2luZyB2YWx1ZXMgaWYgYW55IHVzaW5nIHVzZXIgY3VycmVudCB0aW1lIGlmIGF2YWlsYWJsZS4gXG4gICAgdXNlciBjdXJyZW50IHRpbWU6IHt7dXNlckN1cnJlbnRUaW1lfX1cbiAgICBQc2V1ZG8gSlNPTiBmb3JtYXQ6XG4gICAge1xuICAgICAgXCJ5ZWFyXCI6IFwiW0ZvdXItZGlnaXQgeWVhcl0gW1NUUklOR11cIixcbiAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICBcImRheVwiOiBcIlsyLWRpZ2l0cyBkYXldIFtTVFJJTkddXCIsIC8vIGluZmVyIGRheSBmcm9tIHVzZXIgY3VycmVudCB0aW1lIGlmICd0b2RheScgb3IgJ3RvbW9ycm93JyBtZW50aW9uZWRcbiAgICAgIFwiaXNvV2Vla2RheVwiOiBcIlsxLTcgZGlnaXQgZGF5XSBbTlVNQkVSXVwiLFxuICAgICAgXCJob3VyXCI6IFwiWzI0IGhvdXJdIFtOVU1CRVJdXCIsXG4gICAgICBcIm1pbnV0ZVwiOiBcIlttaW51dGVzXSBbTlVNQkVSXVwiLFxuICAgICAgXCJkdXJhdGlvblwiOiBcIlttaW51dGVzXSBbTlVNQkVSXSBbPCA2IGhvdXJzIGZvcm1hdF0gW2ZvciBhIHNpbmdsZSBldmVudF1cIiwgXG4gICAgICBcInN0YXJ0VGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgIFwiZW5kVGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgIFwibWV0aG9kXCI6IFtcIltjcmVhdGUtZXZlbnQtZm9yd2FyZCB8IGNyZWF0ZS1ldmVudC1iYWNrd2FyZCB8IGNyZWF0ZS1kZWFkbGluZS1mb3J3YXJkIHwgbW92ZS1kZWFkbGluZS1mb3J3YXJkIHwgbW92ZS1kZWFkbGluZS1iYWNrd2FyZCB8IG1vdmUtZXZlbnQtZm9yd2FyZCB8IG1vdmUtZXZlbnQtYmFja3dhcmQgfCBpbmNyZWFzZS1kdXJhdGlvbiB8IGRlY3JlYXNlLWR1cmF0aW9uIHwgY3JlYXRlLXRpbWUtcHJlZmVyZW5jZXMgfCByZW1vdmUtdGltZS1wcmVmZXJlbmNlcyB8IGVkaXQtYWRkLXRpbWUtcHJlZmVyZW5jZXMgfCBlZGl0LXJlbW92ZS10aW1lLXByZWZlcmVuY2VzIHwgZWRpdC1ldmVudC1wcm9wZXJ0eSB8IGFzay1jYWxlbmRhci1xdWVzdGlvbiB8IHJlbW92ZS1ldmVudCB8IGZpbmQtdGltZSB8IGludml0ZV1cIl0sXG4gICAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogXCJbYWRkIHwgc3VidHJhY3RdIFtub24tbnVsbCBpZiByZWxhdGl2ZVRpbWVGcm9tTm93IHByZXNlbnQsIG1heSBpbmZlcl1cIixcbiAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbe1xuICAgICAgICBcInVuaXRcIjogXCJbbWludXRlIHwgaG91ciB8IGRheSB8IHdlZWsgfCBtb250aCB8IHllYXJdXCIsXG4gICAgICAgIFwidmFsdWVcIjogXCJbTlVNQkVSXVwiXG4gICAgICB9XSwgLy8gdGltZSBpbmNsdXNpdmU6ICdzdGFydGluZyBmcm9tIGRheSBhZnRlciB0b21vcnJvdycgLT4gW3tcInVuaXRcIjogXCJkYXlcIiwgXCJ2YWx1ZVwiOiAyfV1cbiAgICAgIFwib2xkRGF0ZVwiOiB7XG4gICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcIlthZGQgfCBzdWJ0cmFjdF0gW25vbi1udWxsIGlmIHJlbGF0aXZlVGltZUZyb21Ob3cgcHJlc2VudCwgbWF5IGluZmVyXVwiLFxuICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW3tcbiAgICAgICAgICBcInVuaXRcIjogXCJbbWludXRlIHwgaG91ciB8IGRheSB8IHdlZWsgfCBtb250aCB8IHllYXJdXCIsXG4gICAgICAgICAgXCJ2YWx1ZVwiOiBcIltOVU1CRVJdXCJcbiAgICAgICAgfV0sXG4gICAgICAgIFwieWVhclwiOiBcIltGb3VyLWRpZ2l0IHllYXJdIFtTVFJJTkddXCIsXG4gICAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICAgIFwiZGF5XCI6IFwiWzItZGlnaXRzIGRheV0gW1NUUklOR11cIixcbiAgICAgICAgXCJpc29XZWVrZGF5XCI6IFwiWzEtNyBkaWdpdCBkYXldIFtOVU1CRVJdXCIsXG4gICAgICAgIFwiaG91clwiOiBcIlsyNCBob3VyXSBbTlVNQkVSXVwiLFxuICAgICAgICBcIm1pbnV0ZVwiOiBcIlttaW51dGVzXSBbTlVNQkVSXVwiLFxuICAgICAgICBcImR1cmF0aW9uXCI6IFwiW21pbnV0ZXNdIFtOVU1CRVJdIFs8IDYgaG91cnMgZm9ybWF0XSBbZm9yIGEgc2luZ2xlIGV2ZW50XVwiLFxuICAgICAgICBcInN0YXJ0VGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgICAgXCJlbmRUaW1lXCI6IFwiWzI0IGhvdXIgMi1kaWdpdHNdOlttaW51dGVzIDItZGlnaXRzXSBbU1RSSU5HXVwiXG4gICAgICB9LFxuICAgICAgXCJkdWVEYXRlXCI6IHtcbiAgICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiW2FkZCB8IHN1YnRyYWN0XSBbbm9uLW51bGwgaWYgcmVsYXRpdmVUaW1lRnJvbU5vdyBwcmVzZW50LCBtYXkgaW5mZXJdXCIsXG4gICAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbe1xuICAgICAgICAgIFwidW5pdFwiOiBcIlttaW51dGUgfCBob3VyIHwgZGF5IHwgd2VlayB8IG1vbnRoIHwgeWVhcl1cIixcbiAgICAgICAgICBcInZhbHVlXCI6IFwiW05VTUJFUl1cIlxuICAgICAgICB9XSwgLy8gdGltZSBpbmNsdXNpdmU6ICdsZW5ndGggb2YgMiBkYXlzIHN0YXJ0aW5nIGZyb20gdG9kYXknIC0+IFt7XCJ1bml0XCI6IFwiZGF5XCIsIFwidmFsdWVcIjogMX1dXG4gICAgICAgIFwieWVhclwiOiBcIltGb3VyLWRpZ2l0IHllYXJdIFtTVFJJTkddXCIsXG4gICAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICAgIFwiZGF5XCI6IFwiWzItZGlnaXRzIGRheV0gW1NUUklOR11cIixcbiAgICAgICAgXCJpc29XZWVrZGF5XCI6IFwiWzEtNyBkaWdpdCBkYXldIFtOVU1CRVJdXCIsXG4gICAgICAgIFwiaG91clwiOiBcIlsyNCBob3VyXSBbTlVNQkVSXVwiLFxuICAgICAgICBcIm1pbnV0ZVwiOiBcIlttaW51dGVzXSBbTlVNQkVSXVwiLFxuICAgICAgICBcImR1cmF0aW9uXCI6IFwiW21pbnV0ZXNdIFtOVU1CRVJdIFs8IDYgaG91cnMgZm9ybWF0XSBbZm9yIGEgc2luZ2xlIGV2ZW50XVwiLFxuICAgICAgICBcInN0YXJ0VGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgICAgXCJlbmRUaW1lXCI6IFwiWzI0IGhvdXIgMi1kaWdpdHNdOlttaW51dGVzIDItZGlnaXRzXSBbU1RSSU5HXVwiXG4gICAgICB9LFxuICAgICAgXCJmaW5kVGltZVdpbmRvd1N0YXJ0XCI6IHsgLy8gdXNlZCBmb3IgdGltZSB3aW5kb3cgc3RhcnQgYm91bmRhcnkgZm9yIGZpbmRpbmcgb3B0aW11bSB0aW1lIGZvciBzY2hlZHVsaW5nIG1lZXRpbmdzXG4gICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcIlthZGQgfCBzdWJ0cmFjdF0gW25vbi1udWxsIGlmIHJlbGF0aXZlVGltZUZyb21Ob3cgcHJlc2VudCwgbWF5IGluZmVyXVwiLFxuICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW3tcbiAgICAgICAgICBcInVuaXRcIjogXCJbbWludXRlIHwgaG91ciB8IGRheSB8IHdlZWsgfCBtb250aCB8IHllYXJdXCIsXG4gICAgICAgICAgXCJ2YWx1ZVwiOiBcIltOVU1CRVJdXCJcbiAgICAgICAgfV0sXG4gICAgICAgIFwieWVhclwiOiBcIltGb3VyLWRpZ2l0IHllYXJdIFtTVFJJTkddXCIsXG4gICAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICAgIFwiZGF5XCI6IFwiWzItZGlnaXRzIGRheV0gW1NUUklOR11cIixcbiAgICAgICAgXCJpc29XZWVrZGF5XCI6IFwiWzEtNyBkaWdpdCBkYXldIFtOVU1CRVJdXCIsXG4gICAgICAgIFwiaG91clwiOiBcIlsyNCBob3VyXSBbTlVNQkVSXVwiLFxuICAgICAgICBcIm1pbnV0ZVwiOiBcIlttaW51dGVzXSBbTlVNQkVSXVwiLFxuICAgICAgICBcImR1cmF0aW9uXCI6IFwiW21pbnV0ZXNdIFtOVU1CRVJdIFs8IDYgaG91cnMgZm9ybWF0XSBbZm9yIGEgc2luZ2xlIGV2ZW50XVwiLFxuICAgICAgICBcInN0YXJ0VGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgICAgXCJlbmRUaW1lXCI6IFwiWzI0IGhvdXIgMi1kaWdpdHNdOlttaW51dGVzIDItZGlnaXRzXSBbU1RSSU5HXVwiXG4gICAgICB9LFxuICAgICAgXCJmaW5kVGltZVdpbmRvd0VuZFwiOiB7ICAgLy8gdXNlZCBmb3IgdGltZSB3aW5kb3cgZW5kIGJvdW5kYXJ5IGZvciBmaW5kaW5nIG9wdGltdW0gdGltZSBmb3Igc2NoZWR1bGluZyBtZWV0aW5nc1xuICAgICAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogXCJbYWRkIHwgc3VidHJhY3RdIFtub24tbnVsbCBpZiByZWxhdGl2ZVRpbWVGcm9tTm93IHByZXNlbnQsIG1heSBpbmZlcl1cIixcbiAgICAgICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IFt7XG4gICAgICAgICAgXCJ1bml0XCI6IFwiW21pbnV0ZSB8IGhvdXIgfCB3ZWVrIHwgZGF5IHwgbW9udGggfCB5ZWFyXVwiLFxuICAgICAgICAgIFwidmFsdWVcIjogXCJbTlVNQkVSXVwiXG4gICAgICAgIH1dLFxuICAgICAgICBcInllYXJcIjogXCJbRm91ci1kaWdpdCB5ZWFyXSBbU1RSSU5HXVwiLFxuICAgICAgICBcIm1vbnRoXCI6IFwiWzItZGlnaXRzIG1vbnRoXSBbU1RSSU5HXVwiLFxuICAgICAgICBcImRheVwiOiBcIlsyLWRpZ2l0cyBkYXldIFtTVFJJTkddXCIsXG4gICAgICAgIFwiaXNvV2Vla2RheVwiOiBcIlsxLTcgZGlnaXQgZGF5XSBbTlVNQkVSXVwiLFxuICAgICAgICBcImhvdXJcIjogXCJbMjQgaG91cl0gW05VTUJFUl1cIixcbiAgICAgICAgXCJtaW51dGVcIjogXCJbbWludXRlc10gW05VTUJFUl1cIixcbiAgICAgICAgXCJkdXJhdGlvblwiOiBcIlttaW51dGVzXSBbTlVNQkVSXSBbPCA2IGhvdXJzIGZvcm1hdF0gW2ZvciBhIHNpbmdsZSBldmVudF1cIixcbiAgICAgICAgXCJzdGFydFRpbWVcIjogXCJbMjQgaG91ciAyLWRpZ2l0c106W21pbnV0ZXMgMi1kaWdpdHNdIFtTVFJJTkddXCIsXG4gICAgICAgIFwiZW5kVGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIlxuICAgICAgfSxcbiAgICAgIFwicmVjdXJcIjoge1xuICAgICAgICBcImZyZXF1ZW5jeVwiOiBcIlsnZGFpbHknIHwgJ3dlZWtseSd8ICdtb250aGx5JyB8ICd5ZWFybHknXVwiLFxuICAgICAgICBcImVuZERhdGVcIjoge1xuICAgICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcIlthZGQgfCBzdWJ0cmFjdF0gW25vbi1udWxsIGlmIHJlbGF0aXZlVGltZUZyb21Ob3cgcHJlc2VudCwgbWF5IGluZmVyXVwiLFxuICAgICAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbe1xuICAgICAgICAgICAgXCJ1bml0XCI6IFwiW21pbnV0ZSB8IGhvdXIgfCBkYXkgfCB3ZWVrIHwgbW9udGggfCB5ZWFyXVwiLFxuICAgICAgICAgICAgXCJ2YWx1ZVwiOiBcIltOVU1CRVJdXCJcbiAgICAgICAgICB9XSxcbiAgICAgICAgICBcInllYXJcIjogXCJbRm91ci1kaWdpdCB5ZWFyXSBbU1RSSU5HXVwiLFxuICAgICAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICAgICAgXCJkYXlcIjogXCJbMi1kaWdpdHMgZGF5XSBbU1RSSU5HXVwiLFxuICAgICAgICAgIFwiaXNvV2Vla2RheVwiOiBcIlsxLTcgZGlnaXQgZGF5XSBbTlVNQkVSXVwiLFxuICAgICAgICAgIFwiaG91clwiOiBcIlsyNCBob3VyXSBbTlVNQkVSXVwiLFxuICAgICAgICAgIFwibWludXRlXCI6IFwiW21pbnV0ZXNdIFtOVU1CRVJdXCIsXG4gICAgICAgICAgXCJkdXJhdGlvblwiOiBcIlttaW51dGVzXSBbTlVNQkVSXSBbPCA2IGhvdXJzIGZvcm1hdF0gW2ZvciBhIHNpbmdsZSBldmVudF1cIixcbiAgICAgICAgICBcInN0YXJ0VGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIixcbiAgICAgICAgICBcImVuZFRpbWVcIjogXCJbMjQgaG91ciAyLWRpZ2l0c106W21pbnV0ZXMgMi1kaWdpdHNdIFtTVFJJTkddXCJcbiAgICAgICAgfSxcbiAgICAgICAgXCJvY2N1cnJlbmNlXCI6IFwiW05VTUJFUl1cIixcbiAgICAgICAgXCJpbnRlcnZhbFwiOiBcIltOVU1CRVJdXCIsXG4gICAgICAgIFwiYnlXZWVrRGF5XCI6IFtcIlsnTU8nIHwgJ1RVJyB8ICdXRScgfCAnVEgnIHwgJ0ZSJyB8ICdTQScgfCAnU1UnXVwiXSxcbiAgICAgICAgXCJieU1vbnRoRGF5XCI6IFtcIlsxIC0gMzFdXCJdXG4gICAgICB9LFxuICAgICAgXCJ0aW1lUHJlZmVyZW5jZXNcIjogW3tcbiAgICAgICAgICBcImRheU9mV2Vla1wiOiBbXCJbJ01PJyB8ICdUVScgfCAnV0UnIHwgJ1RIJyB8ICdGUicgfCAnU0EnIHwgJ1NVJ11cIl0sXG4gICAgICAgICAgXCJ0aW1lUmFuZ2VcIjoge1xuICAgICAgICAgICAgXCJzdGFydFRpbWVcIjogXCJbMjQgaG91ciAyLWRpZ2l0c106W21pbnV0ZXMgMi1kaWdpdHNdIFtTVFJJTkddXCIsXG4gICAgICAgICAgICBcImVuZFRpbWVcIjogXCJbMjQgaG91ciAyLWRpZ2l0c106W21pbnV0ZXMgMi1kaWdpdHNdIFtTVFJJTkddXCJcbiAgICAgICAgICB9XG4gICAgICAgIH1dLFxuICAgICAgXCJhbGxEYXlcIjogXCJbQk9PTEVBTl1cIlxuICAgIH1cbmA7XG5cbmV4cG9ydCBjb25zdCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVJbnB1dDEgPSBgXG5zY2hlZHVsZSBhIG1lZXRpbmcgd2l0aCBKb2Ugb24gVHVlc2RheSBmb3IgMiBwbSBmb3IgTWFya2V0aW5nIHByZXNlbnRhdGlvblxuYDtcblxuZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDEgPSBgXG57XG4gIFwieWVhclwiOiB7e3llYXJ9fSxcbiAgXCJtb250aFwiOiB7e21vbnRofX0sXG4gIFwiZGF5XCI6IG51bGwsXG4gIFwiaXNvV2Vla2RheVwiOiAyLFxuICBcImhvdXJcIjogMTQsXG4gIFwibWludXRlXCI6IDAsXG4gIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgXCJzdGFydFRpbWVcIjogXCIxNDowMFwiLFxuICBcImVuZFRpbWVcIjogbnVsbCxcbiAgXCJtZXRob2RcIjogW1wiY3JlYXRlLWV2ZW50LWZvcndhcmRcIl0sXG4gIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgXCJvbGREYXRlXCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogbnVsbCxcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgICBcInllYXJcIjogbnVsbCxcbiAgICBcIm1vbnRoXCI6IG51bGwsXG4gICAgXCJkYXlcIjogbnVsbCxcbiAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICBcImhvdXJcIjogbnVsbCxcbiAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICAgIFwiZW5kVGltZVwiOiBudWxsXG4gIH0sXG4gIFwiZHVlRGF0ZVwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IG51bGwsXG4gICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgXCJtb250aFwiOiBudWxsLFxuICAgIFwiZGF5XCI6IG51bGwsXG4gICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgXCJob3VyXCI6IG51bGwsXG4gICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICBcImVuZFRpbWVcIjogbnVsbFxuICB9LFxuICBcImZpbmRUaW1lV2luZG93U3RhcnRcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgIFwieWVhclwiOiBudWxsLFxuICAgIFwibW9udGhcIjogbnVsbCxcbiAgICBcImRheVwiOiBudWxsLFxuICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgIFwiaG91clwiOiBudWxsLFxuICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgfSxcbiAgXCJmaW5kVGltZVdpbmRvd0VuZFwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IG51bGwsXG4gICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgXCJtb250aFwiOiBudWxsLFxuICAgIFwiZGF5XCI6IG51bGwsXG4gICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgXCJob3VyXCI6IG51bGwsXG4gICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICBcImVuZFRpbWVcIjogbnVsbFxuICB9LFxuICBcInJlY3VyXCI6IHtcbiAgICBcImZyZXF1ZW5jeVwiOiBudWxsLFxuICAgIFwiZW5kRGF0ZVwiOiB7XG4gICAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogbnVsbCxcbiAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgICBcIm1vbnRoXCI6IG51bGwsXG4gICAgICBcImRheVwiOiBudWxsLFxuICAgICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgICBcImhvdXJcIjogbnVsbCxcbiAgICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICAgICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgICB9LFxuICAgIFwib2NjdXJyZW5jZVwiOiBudWxsLFxuICAgIFwiaW50ZXJ2YWxcIjogbnVsbCxcbiAgICBcImJ5V2Vla0RheVwiOiBudWxsLFxuICAgIFwiYnlNb250aERheVwiOiBudWxsXG4gIH0sXG4gIFwidGltZVByZWZlcmVuY2VzXCI6IG51bGwsXG4gIFwiYWxsRGF5XCI6IG51bGxcbn1cbmA7XG5cbmV4cG9ydCBjb25zdCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVJbnB1dDIgPSBgXG4gIHJlc2NoZWR1bGUgSm9lJ3MgbWFya2V0aW5nIHByZXNlbnRhdGlvbiBzY2hlZHVsZWQgMSB3ZWVrIGZyb20gbm93IHRvIDMgd2Vla3MgZnJvbSBub3dcbmA7XG5cbmV4cG9ydCBjb25zdCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVPdXRwdXQyID0gYFxuIHtcbiAgXCJ5ZWFyXCI6IHt7eWVhcn19LFxuICBcIm1vbnRoXCI6IHt7bW9udGh9fSxcbiAgXCJkYXlcIjogbnVsbCxcbiAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gIFwiaG91clwiOiBudWxsLFxuICBcIm1pbnV0ZVwiOiBudWxsLFxuICBcImR1cmF0aW9uXCI6IG51bGwsXG4gIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gIFwiZW5kVGltZVwiOiBudWxsLFxuICBcIm1ldGhvZFwiOiBbXCJtb3ZlLWV2ZW50LWZvcndhcmRcIl0sXG4gIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgIHtcbiAgICAgIFwidW5pdFwiOiBcIndlZWtcIixcbiAgICAgIFwidmFsdWVcIjogM1xuICAgIH1cbiAgXSxcbiAgXCJvbGREYXRlXCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogbnVsbCxcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgICAge1xuICAgICAgICBcInVuaXRcIjogXCJ3ZWVrXCIsXG4gICAgICAgIFwidmFsdWVcIjogMVxuICAgICAgfVxuICAgIF0sXG4gICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgXCJtb250aFwiOiBudWxsLFxuICAgIFwiZGF5XCI6IG51bGwsXG4gICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgXCJob3VyXCI6IG51bGwsXG4gICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICBcImVuZFRpbWVcIjogbnVsbFxuICB9LFxuICBcImR1ZURhdGVcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgIFwieWVhclwiOiBudWxsLFxuICAgIFwibW9udGhcIjogbnVsbCxcbiAgICBcImRheVwiOiBudWxsLFxuICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgIFwiaG91clwiOiBudWxsLFxuICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgfSxcbiAgXCJmaW5kVGltZVdpbmRvd1N0YXJ0XCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogbnVsbCxcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgICBcInllYXJcIjogbnVsbCxcbiAgICBcIm1vbnRoXCI6IG51bGwsXG4gICAgXCJkYXlcIjogbnVsbCxcbiAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICBcImhvdXJcIjogbnVsbCxcbiAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICAgIFwiZW5kVGltZVwiOiBudWxsXG4gIH0sXG4gIFwiZmluZFRpbWVXaW5kb3dFbmRcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgIFwieWVhclwiOiBudWxsLFxuICAgIFwibW9udGhcIjogbnVsbCxcbiAgICBcImRheVwiOiBudWxsLFxuICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgIFwiaG91clwiOiBudWxsLFxuICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgfSxcbiAgXCJyZWN1clwiOiB7XG4gICAgXCJmcmVxdWVuY3lcIjogbnVsbCxcbiAgICBcImVuZERhdGVcIjoge1xuICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgICAgIFwieWVhclwiOiBudWxsLFxuICAgICAgXCJtb250aFwiOiBudWxsLFxuICAgICAgXCJkYXlcIjogbnVsbCxcbiAgICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgICAgXCJob3VyXCI6IG51bGwsXG4gICAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICAgIFwiZW5kVGltZVwiOiBudWxsXG4gICAgfSxcbiAgICBcIm9jY3VycmVuY2VcIjogbnVsbCxcbiAgICBcImludGVydmFsXCI6IG51bGwsXG4gICAgXCJieVdlZWtEYXlcIjogbnVsbCxcbiAgICBcImJ5TW9udGhEYXlcIjogbnVsbFxuICB9LFxuICBcInRpbWVQcmVmZXJlbmNlc1wiOiBudWxsLFxuICBcImFsbERheVwiOiBudWxsXG59XG5cblxuYDtcblxuZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MyA9IGBcbiAgRmluZCBhbiBhdmFpbGFibGUgdGltZSBzbG90IGZvciBhIHRlYW0gbWVldGluZyB3aXRoIE1hcmdldCwgSm9obiBhbmQgRWxsaWUgYmV0d2VlbiB0b21vcnJvdyB0aWxsIEZyaWRheSB0aGlzIGNvbWluZyB3ZWVrIGZvciBNYXJrZXRpbmcgcHJlc2VudGF0aW9uXG4gYDtcblxuZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDMgPSBgXG57XG4gIFwieWVhclwiOiBudWxsLFxuICBcIm1vbnRoXCI6IG51bGwsXG4gIFwiZGF5XCI6IG51bGwsXG4gIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICBcImhvdXJcIjogbnVsbCxcbiAgXCJtaW51dGVcIjogbnVsbCxcbiAgXCJkdXJhdGlvblwiOiBudWxsLFxuICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICBcImVuZFRpbWVcIjogbnVsbCxcbiAgXCJtZXRob2RcIjogW1wiZmluZC10aW1lXCJdLFxuICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogbnVsbCxcbiAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IG51bGwsXG4gIFwib2xkRGF0ZVwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IG51bGwsXG4gICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgXCJtb250aFwiOiBudWxsLFxuICAgIFwiZGF5XCI6IG51bGwsXG4gICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgXCJob3VyXCI6IG51bGwsXG4gICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICBcImVuZFRpbWVcIjogbnVsbFxuICB9LFxuICBcImR1ZURhdGVcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgIFwieWVhclwiOiBudWxsLFxuICAgIFwibW9udGhcIjogbnVsbCxcbiAgICBcImRheVwiOiBudWxsLFxuICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgIFwiaG91clwiOiBudWxsLFxuICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgfSxcbiAgXCJmaW5kVGltZVdpbmRvd1N0YXJ0XCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogXCJhZGRcIixcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgICAge1xuICAgICAgICBcInVuaXRcIjogXCJkYXlcIixcbiAgICAgICAgXCJ2YWx1ZVwiOiAxXG4gICAgICB9XG4gICAgXSxcbiAgICBcInllYXJcIjogbnVsbCxcbiAgICBcIm1vbnRoXCI6IG51bGwsXG4gICAgXCJkYXlcIjogbnVsbCxcbiAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICBcImhvdXJcIjogbnVsbCxcbiAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICAgIFwiZW5kVGltZVwiOiBudWxsXG4gIH0sXG4gIFwiZmluZFRpbWVXaW5kb3dFbmRcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbXG4gICAgICB7XG4gICAgICAgIFwidW5pdFwiOiBcIndlZWtcIixcbiAgICAgICAgXCJ2YWx1ZVwiOiAxXG4gICAgICB9XG4gICAgXSxcbiAgICBcInllYXJcIjogbnVsbCxcbiAgICBcIm1vbnRoXCI6IG51bGwsXG4gICAgXCJkYXlcIjogbnVsbCxcbiAgICBcImlzb1dlZWtkYXlcIjogNSxcbiAgICBcImhvdXJcIjogbnVsbCxcbiAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICBcInN0YXJ0VGltZVwiOiBudWxsLFxuICAgIFwiZW5kVGltZVwiOiBudWxsXG4gIH0sXG4gIFwicmVjdXJcIjoge1xuICAgIFwiZnJlcXVlbmN5XCI6IG51bGwsXG4gICAgXCJlbmREYXRlXCI6IHtcbiAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBudWxsLFxuICAgICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IG51bGwsXG4gICAgICBcInllYXJcIjogbnVsbCxcbiAgICAgIFwibW9udGhcIjogbnVsbCxcbiAgICAgIFwiZGF5XCI6IG51bGwsXG4gICAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICAgIFwiaG91clwiOiBudWxsLFxuICAgICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgICBcImVuZFRpbWVcIjogbnVsbFxuICAgIH0sXG4gICAgXCJvY2N1cnJlbmNlXCI6IG51bGwsXG4gICAgXCJpbnRlcnZhbFwiOiBudWxsLFxuICAgIFwiYnlXZWVrRGF5XCI6IG51bGwsXG4gICAgXCJieU1vbnRoRGF5XCI6IG51bGxcbiAgfSxcbiAgXCJ0aW1lUHJlZmVyZW5jZXNcIjogbnVsbCxcbiAgXCJhbGxEYXlcIjogbnVsbFxufVxuYDtcblxuZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0NCA9IGBcbiAgY3JlYXRlIGEgdGFzayBvZiBidWlsZGluZyBhIGJhc2ljIHVzZXIgYXV0aGVudGljYXRpb24gc3lzdGVtIGZvciBhbiBhcHAuIFRoZSBsZW5ndGggb2YgdGhlIHRhc2sgaXMgZm9yIDUgZGF5cyBhbmQgdGFzayBzdGFydHMgdG9tb3Jyb3cuXG4gYDtcblxuZXhwb3J0IGNvbnN0IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDQgPSBgXG57XG4gICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgXCJtb250aFwiOiBudWxsLFxuICAgIFwiZGF5XCI6IG51bGwsXG4gICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgXCJob3VyXCI6IG51bGwsXG4gICAgXCJtaW51dGVcIjogbnVsbCxcbiAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICBcImVuZFRpbWVcIjogbnVsbCxcbiAgICBcIm1ldGhvZFwiOiBbXG4gICAgICAgIFwiY3JlYXRlLWV2ZW50LWZvcndhcmRcIlxuICAgIF0sXG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiYWRkXCIsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IFtcbiAgICAgICAge1xuICAgICAgICAgICAgXCJ1bml0XCI6IFwiZGF5XCIsXG4gICAgICAgICAgICBcInZhbHVlXCI6IDFcbiAgICAgICAgfVxuICAgIF0sXG4gICAgXCJvbGREYXRlXCI6IHtcbiAgICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgICAgICBcInllYXJcIjogbnVsbCxcbiAgICAgICAgXCJtb250aFwiOiBudWxsLFxuICAgICAgICBcImRheVwiOiBudWxsLFxuICAgICAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICAgICAgXCJob3VyXCI6IG51bGwsXG4gICAgICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICAgICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICAgICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgICB9LFxuICAgIFwiZHVlRGF0ZVwiOiB7XG4gICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcImFkZFwiLFxuICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIFwidW5pdFwiOiBcImRheVwiLFxuICAgICAgICAgICAgICAgIFwidmFsdWVcIjogNVxuICAgICAgICAgICAgfVxuICAgICAgICBdLFxuICAgICAgICBcInllYXJcIjogbnVsbCxcbiAgICAgICAgXCJtb250aFwiOiBudWxsLFxuICAgICAgICBcImRheVwiOiBudWxsLFxuICAgICAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICAgICAgXCJob3VyXCI6IG51bGwsXG4gICAgICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICAgICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICAgICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgICB9LFxuICAgIFwiZmluZFRpbWVXaW5kb3dTdGFydFwiOiB7XG4gICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcImFkZFwiLFxuICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgICAgICAgXCJ5ZWFyXCI6IG51bGwsXG4gICAgICAgIFwibW9udGhcIjogbnVsbCxcbiAgICAgICAgXCJkYXlcIjogbnVsbCxcbiAgICAgICAgXCJpc29XZWVrZGF5XCI6IG51bGwsXG4gICAgICAgIFwiaG91clwiOiBudWxsLFxuICAgICAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgICAgICBcImR1cmF0aW9uXCI6IG51bGwsXG4gICAgICAgIFwic3RhcnRUaW1lXCI6IG51bGwsXG4gICAgICAgIFwiZW5kVGltZVwiOiBudWxsXG4gICAgfSxcbiAgICBcImZpbmRUaW1lV2luZG93RW5kXCI6IHtcbiAgICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiYWRkXCIsXG4gICAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBudWxsLFxuICAgICAgICBcInllYXJcIjogbnVsbCxcbiAgICAgICAgXCJtb250aFwiOiBudWxsLFxuICAgICAgICBcImRheVwiOiBudWxsLFxuICAgICAgICBcImlzb1dlZWtkYXlcIjogbnVsbCxcbiAgICAgICAgXCJob3VyXCI6IG51bGwsXG4gICAgICAgIFwibWludXRlXCI6IG51bGwsXG4gICAgICAgIFwiZHVyYXRpb25cIjogbnVsbCxcbiAgICAgICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICAgICAgXCJlbmRUaW1lXCI6IG51bGxcbiAgICB9LFxuICAgIFwicmVjdXJcIjoge1xuICAgICAgICBcImZyZXF1ZW5jeVwiOiBudWxsLFxuICAgICAgICBcImVuZERhdGVcIjoge1xuICAgICAgICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IG51bGwsXG4gICAgICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogbnVsbCxcbiAgICAgICAgICAgIFwieWVhclwiOiBudWxsLFxuICAgICAgICAgICAgXCJtb250aFwiOiBudWxsLFxuICAgICAgICAgICAgXCJkYXlcIjogbnVsbCxcbiAgICAgICAgICAgIFwiaXNvV2Vla2RheVwiOiBudWxsLFxuICAgICAgICAgICAgXCJob3VyXCI6IG51bGwsXG4gICAgICAgICAgICBcIm1pbnV0ZVwiOiBudWxsLFxuICAgICAgICAgICAgXCJkdXJhdGlvblwiOiBudWxsLFxuICAgICAgICAgICAgXCJzdGFydFRpbWVcIjogbnVsbCxcbiAgICAgICAgICAgIFwiZW5kVGltZVwiOiBudWxsXG4gICAgICAgIH0sXG4gICAgICAgIFwib2NjdXJyZW5jZVwiOiBudWxsLFxuICAgICAgICBcImludGVydmFsXCI6IG51bGwsXG4gICAgICAgIFwiYnlXZWVrRGF5XCI6IG51bGwsXG4gICAgICAgIFwiYnlNb250aERheVwiOiBudWxsXG4gICAgfSxcbiAgICBcInRpbWVQcmVmZXJlbmNlc1wiOiBudWxsLFxuICAgIFwiYWxsRGF5XCI6IG51bGxcbn1cbmA7XG5cbmV4cG9ydCBjb25zdCBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09OUHJvbXB0ID0gYFxuICBZb3UgYXJlIGEgZGF0ZSByYW5nZSBpbnRlcnByZXRlciBmb3IgdXNlciBpbnRlbnQgaW4gdGhlIGNvbnRleHQgb2YgYSB3b3JrIGNhbGVuZGFyLiBDb252ZXJ0IHVzZXIgaW5wdXQgcHJvdmlkZWQgdG8gSlNPTiB0eXBlIGRhdGUgcmFuZ2UgZm9yIGFuIEFQSSBjYWxsLiBSZXBsYWNlIHBsYWNlaG9sZGVycyB3aXRoIG51bGwgaWYgbm90IGFwcGxpY2FibGUuIElmIGV4YWN0IHRpbWUgbm90IHByb3ZpZGVkLCBpbmZlciB1bmNsZWFyIHZhbHVlcyBiYXNlZCBvbiB1c2VyIGlucHV0LCB1c2VyIGN1cnJlbnQgdGltZSBhbmQgd29yayBjb250ZXh0LiBZb3VyIGpvYiBhcyBhIGRhdGUgcmFuZ2UgaW50ZXJwcmV0ZXIsIGluZmVyIGEgdGltZSB3aW5kb3cgd2hlcmUgYXBwcm9wcmlhdGUuIFByb3ZpZGUgcHJlY2lzaW9uIHZhbHVlcyB1cCB0byB0aGUgbWludXRlIHRvIHNldCBjbGVhciBkYXRlIHJhbmdlIGJvdW5kYXJpZXMuIFRha2Ugd29yayBkYXkgY29udGV4dCBpbnRvIGFjY291bnQgd2hlbiBwcm92aWRpbmcgcmFuZ2VzLiBGb2xsb3cgdGhpcyBwc2V1ZG8gSlNPTiBmb3JtYXQ6XG57XG4gICAgXCJzdGFydF9kYXRlXCI6IHtcbiAgICAgICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiW2FkZCB8IHN1YnRyYWN0XSBbbm9uLW51bGwgaWYgcmVsYXRpdmVUaW1lRnJvbU5vdyBwcmVzZW50LCBtYXkgaW5mZXJdXCIsXG4gICAgICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbe1xuICAgICAgICAgICAgXCJ1bml0XCI6IFwiW21pbnV0ZSB8IGhvdXIgfCBkYXkgfCB3ZWVrIHwgbW9udGggfCB5ZWFyXVwiLFxuICAgICAgICAgICAgXCJ2YWx1ZVwiOiBcIltOVU1CRVJdXCJcbiAgICAgICAgfV0sXG4gICAgICAgIFwieWVhclwiOiBcIltGb3VyLWRpZ2l0IHllYXJdIFtTVFJJTkddXCIsXG4gICAgICAgIFwibW9udGhcIjogXCJbMi1kaWdpdHMgbW9udGhdIFtTVFJJTkddXCIsXG4gICAgICAgIFwiZGF5XCI6IFwiWzItZGlnaXRzIGRheV0gW1NUUklOR11cIixcbiAgICAgICAgXCJob3VyXCI6IFwiWzI0IGhvdXJdIFtOVU1CRVJdXCIsXG4gICAgICAgIFwibWludXRlXCI6IFwiW21pbnV0ZXNdIFtOVU1CRVJdXCIsXG4gICAgICAgIFwidGltZVwiOiBcIlsyNCBob3VyIDItZGlnaXRzXTpbbWludXRlcyAyLWRpZ2l0c10gW1NUUklOR11cIlxuICAgIH0sXG4gICAgXCJlbmRfZGF0ZVwiOiB7XG4gICAgICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcIlthZGQgfCBzdWJ0cmFjdF0gW25vbi1udWxsIGlmIHJlbGF0aXZlVGltZUZyb21Ob3cgcHJlc2VudCwgbWF5IGluZmVyXVwiLFxuICAgICAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW3tcbiAgICAgICAgICAgIFwidW5pdFwiOiBcIlttaW51dGUgfCBob3VyIHwgZGF5IHwgd2VlayB8IG1vbnRoIHwgeWVhcl1cIixcbiAgICAgICAgICAgIFwidmFsdWVcIjogXCJbTlVNQkVSXVwiXG4gICAgICAgIH1dLFxuICAgICAgICBcInllYXJcIjogXCJbRm91ci1kaWdpdCB5ZWFyXSBbU1RSSU5HXVwiLFxuICAgICAgICBcIm1vbnRoXCI6IFwiWzItZGlnaXRzIG1vbnRoXSBbU1RSSU5HXVwiLFxuICAgICAgICBcImRheVwiOiBcIlsyLWRpZ2l0cyBkYXldIFtTVFJJTkddXCIsXG4gICAgICAgIFwiaG91clwiOiBcIlsyNCBob3VyXSBbTlVNQkVSXVwiLFxuICAgICAgICBcIm1pbnV0ZVwiOiBcIlttaW51dGVzXSBbTlVNQkVSXVwiLFxuICAgICAgICBcInRpbWVcIjogXCJbMjQgaG91ciAyLWRpZ2l0c106W21pbnV0ZXMgMi1kaWdpdHNdIFtTVFJJTkddXCJcbiAgICB9XG59XG5gO1xuXG5leHBvcnQgY29uc3QgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTlRlbXBsYXRlID0gYFxuICBVc2VyIGN1cnJlbnQgdGltZToge3t1c2VyQ3VycmVudFRpbWV9fVxuICBVc2VyIHdvcmsgdGltZXM6IHt7dXNlcldvcmtUaW1lc319XG4gIFVzZXIgaW5wdXQ6IHt7dXNlcklucHV0fX1cbmA7XG5cbmV4cG9ydCBjb25zdCBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZUlucHV0MSA9IGBcbiAgVXNlciBjdXJyZW50IHRpbWU6IFdlZG5lc2RheSwgMjAyMy0wNi0yMVQxODo1NjozNy0wNDowMFxuICBVc2VyIHdvcmsgdGltZXM6IE1vbmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgVHVlc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgV2VkbmVzZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBUaHVyc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgRnJpZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBTYXR1cmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgU3VuZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBVc2VyIGlucHV0OiBEbyBJIGhhdmUgYW55IG1lZXRpbmdzIHNjaGVkdWxlZCBmb3IgdG9tb3Jyb3c/XG5gO1xuZXhwb3J0IGNvbnN0IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MSA9IGBcbntcbiAgXCJzdGFydF9kYXRlXCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogXCJhZGRcIixcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgICAge1xuICAgICAgICBcInVuaXRcIjogXCJkYXlcIixcbiAgICAgICAgXCJ2YWx1ZVwiOiAxXG4gICAgICB9XG4gICAgXSxcbiAgICBcInllYXJcIjogXCIyMDIzXCIsXG4gICAgXCJtb250aFwiOiBcIjA2XCIsXG4gICAgXCJkYXlcIjogXCIyMlwiLFxuICAgIFwiaG91clwiOiBcIjA4XCIsXG4gICAgXCJtaW51dGVcIjogXCIwMFwiLFxuICAgIFwidGltZVwiOiBcIjA4OjAwXCJcbiAgfSxcbiAgXCJlbmRfZGF0ZVwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiYWRkXCIsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IFtcbiAgICAgIHtcbiAgICAgICAgXCJ1bml0XCI6IFwiZGF5XCIsXG4gICAgICAgIFwidmFsdWVcIjogMVxuICAgICAgfVxuICAgIF0sXG4gICAgXCJ5ZWFyXCI6IFwiMjAyM1wiLFxuICAgIFwibW9udGhcIjogXCIwNlwiLFxuICAgIFwiZGF5XCI6IFwiMjJcIixcbiAgICBcImhvdXJcIjogXCIxOFwiLFxuICAgIFwibWludXRlXCI6IFwiMzBcIixcbiAgICBcInRpbWVcIjogXCIxODozMFwiXG4gIH1cbn1cbmA7XG5cbmV4cG9ydCBjb25zdCBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZUlucHV0MiA9IGBcbiAgVXNlciBjdXJyZW50IHRpbWU6IFdlZG5lc2RheSwgMjAyMy0wNi0yMVQxODo1NjozNy0wNDowMFxuICBVc2VyIHdvcmsgdGltZXM6IE1vbmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgVHVlc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgV2VkbmVzZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBUaHVyc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgRnJpZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBTYXR1cmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgU3VuZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICBVc2VyIGlucHV0OiBXaGVuIGlzIG15IG5leHQgYXBwb2ludG1lbnQ/XG5gO1xuXG5leHBvcnQgY29uc3QgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVPdXRwdXQyID0gYFxue1xuICBcInN0YXJ0X2RhdGVcIjoge1xuICAgIFwicmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1wiOiBcImFkZFwiLFxuICAgIFwicmVsYXRpdmVUaW1lRnJvbU5vd1wiOiBbXG4gICAgICB7XG4gICAgICAgIFwidW5pdFwiOiBcImRheVwiLFxuICAgICAgICBcInZhbHVlXCI6IFwiMVwiXG4gICAgICB9XG4gICAgXSxcbiAgICBcInllYXJcIjogXCIyMDIzXCIsXG4gICAgXCJtb250aFwiOiBcIjA2XCIsXG4gICAgXCJkYXlcIjogXCIyMlwiLFxuICAgIFwiaG91clwiOiBcIjA4XCIsXG4gICAgXCJtaW51dGVcIjogXCIwMFwiLFxuICAgIFwidGltZVwiOiBcIjA4OjAwXCJcbiAgfSxcbiAgXCJlbmRfZGF0ZVwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiYWRkXCIsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IFtcbiAgICAgIHtcbiAgICAgICAgXCJ1bml0XCI6IFwiZGF5XCIsXG4gICAgICAgIFwidmFsdWVcIjogXCIxXCJcbiAgICAgIH1cbiAgICBdLFxuICAgIFwieWVhclwiOiBcIjIwMjNcIixcbiAgICBcIm1vbnRoXCI6IFwiMDZcIixcbiAgICBcImRheVwiOiBcIjIyXCIsXG4gICAgXCJob3VyXCI6IFwiMThcIixcbiAgICBcIm1pbnV0ZVwiOiBcIjMwXCIsXG4gICAgXCJ0aW1lXCI6IFwiMTg6MzBcIlxuICB9XG59XG5gO1xuXG5leHBvcnQgY29uc3QgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDMgPSBgXG4gIFVzZXIgY3VycmVudCB0aW1lOiBXZWRuZXNkYXksIDIwMjMtMDYtMjFUMTg6NTY6MzctMDQ6MDBcbiAgVXNlciB3b3JrIHRpbWVzOiBNb25kYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gIFR1ZXNkYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gIFdlZG5lc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgVGh1cnNkYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gIEZyaWRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgU2F0dXJkYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gIFN1bmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgVXNlciBpbnB1dDogSXMgdGhlcmUgYW55dGhpbmcgc2NoZWR1bGVkIGZvciBGcmlkYXkgYWZ0ZXJub29uP1xuYDtcblxuZXhwb3J0IGNvbnN0IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MyA9IGBcbntcbiAgXCJzdGFydF9kYXRlXCI6IHtcbiAgICBcInJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dcIjogXCJhZGRcIixcbiAgICBcInJlbGF0aXZlVGltZUZyb21Ob3dcIjogW1xuICAgICAge1xuICAgICAgICBcInVuaXRcIjogXCJkYXlcIixcbiAgICAgICAgXCJ2YWx1ZVwiOiAyXG4gICAgICB9XG4gICAgXSxcbiAgICBcInllYXJcIjogXCIyMDIzXCIsXG4gICAgXCJtb250aFwiOiBcIjA2XCIsXG4gICAgXCJkYXlcIjogXCIyM1wiLFxuICAgIFwiaG91clwiOiBcIjEyXCIsXG4gICAgXCJtaW51dGVcIjogXCIwMFwiLFxuICAgIFwidGltZVwiOiBcIjEyOjAwXCJcbiAgfSxcbiAgXCJlbmRfZGF0ZVwiOiB7XG4gICAgXCJyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93XCI6IFwiYWRkXCIsXG4gICAgXCJyZWxhdGl2ZVRpbWVGcm9tTm93XCI6IFtcbiAgICAgIHtcbiAgICAgICAgXCJ1bml0XCI6IFwiZGF5XCIsXG4gICAgICAgIFwidmFsdWVcIjogMlxuICAgICAgfVxuICAgIF0sXG4gICAgXCJ5ZWFyXCI6IFwiMjAyM1wiLFxuICAgIFwibW9udGhcIjogXCIwNlwiLFxuICAgIFwiZGF5XCI6IFwiMjNcIixcbiAgICBcImhvdXJcIjogXCIxOFwiLFxuICAgIFwibWludXRlXCI6IFwiMzBcIixcbiAgICBcInRpbWVcIjogXCIxODozMFwiXG4gIH1cbn1cblxuYDtcbiJdfQ==