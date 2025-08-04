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
