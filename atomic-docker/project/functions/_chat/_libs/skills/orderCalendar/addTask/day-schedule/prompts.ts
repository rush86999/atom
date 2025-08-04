export const dailyScheduleTemplate = `
  User current time: {{userCurrentTime}}
  User work times: {{userWorkTimes}}
  User input: {{userInput}}
`;

export const dailySchedulePrompt = `
     Give a minute by minute schedule while taking work times into consideration. Start time should be equal or greater to start work times for the given day. Choose an appropriate time given the task. Take into account start time if available but prioritize work times. Minimum duration should be atleast 30 minutes. Provide good time estimates. If possible make start times in 15 minute increments of time such as 8:00, 8:15, 8:30, 8:45 and so forth. Try to center work around morning, afternoon and before dinner if possible. Take lunch and breakfast time into account if possible. Give the respone in JSON array format with keys 'start_time', 'end_time', and 'task'.
`;

export const dailyScheduleExampleInput = `
    User current time: Wednesday, 2023-06-21T18:56:37-04:00
    User work times: Monday: 8:00 am - 6:30 pm
    Tuesday: 8:00 am - 6:30 pm
    Wednesday: 8:00 am - 6:30 pm
    Thursday: 8:00 am - 6:30 pm
    Friday: 8:00 am - 6:30 pm
    Saturday: 8:00 am - 6:30 pm
    Sunday: 8:00 am - 6:30 pm
    User input: 
        start time for tasks: 8:30 am 
        tasks:
        Exercise
    `;

export const dailyScheduleExampleOutput = `[{ "start_time": "8:30 am", "end_time": "9:15 am", "task": "Exercise"}]`;
