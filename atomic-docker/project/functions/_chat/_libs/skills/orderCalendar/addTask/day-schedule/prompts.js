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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvbXB0cy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInByb21wdHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsTUFBTSxDQUFDLE1BQU0scUJBQXFCLEdBQUc7Ozs7Q0FJcEMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLG1CQUFtQixHQUFHOztDQUVsQyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0seUJBQXlCLEdBQUc7Ozs7Ozs7Ozs7Ozs7S0FhcEMsQ0FBQztBQUVOLE1BQU0sQ0FBQyxNQUFNLDBCQUEwQixHQUFHLHlFQUF5RSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGNvbnN0IGRhaWx5U2NoZWR1bGVUZW1wbGF0ZSA9IGBcbiAgVXNlciBjdXJyZW50IHRpbWU6IHt7dXNlckN1cnJlbnRUaW1lfX1cbiAgVXNlciB3b3JrIHRpbWVzOiB7e3VzZXJXb3JrVGltZXN9fVxuICBVc2VyIGlucHV0OiB7e3VzZXJJbnB1dH19XG5gO1xuXG5leHBvcnQgY29uc3QgZGFpbHlTY2hlZHVsZVByb21wdCA9IGBcbiAgICAgR2l2ZSBhIG1pbnV0ZSBieSBtaW51dGUgc2NoZWR1bGUgd2hpbGUgdGFraW5nIHdvcmsgdGltZXMgaW50byBjb25zaWRlcmF0aW9uLiBTdGFydCB0aW1lIHNob3VsZCBiZSBlcXVhbCBvciBncmVhdGVyIHRvIHN0YXJ0IHdvcmsgdGltZXMgZm9yIHRoZSBnaXZlbiBkYXkuIENob29zZSBhbiBhcHByb3ByaWF0ZSB0aW1lIGdpdmVuIHRoZSB0YXNrLiBUYWtlIGludG8gYWNjb3VudCBzdGFydCB0aW1lIGlmIGF2YWlsYWJsZSBidXQgcHJpb3JpdGl6ZSB3b3JrIHRpbWVzLiBNaW5pbXVtIGR1cmF0aW9uIHNob3VsZCBiZSBhdGxlYXN0IDMwIG1pbnV0ZXMuIFByb3ZpZGUgZ29vZCB0aW1lIGVzdGltYXRlcy4gSWYgcG9zc2libGUgbWFrZSBzdGFydCB0aW1lcyBpbiAxNSBtaW51dGUgaW5jcmVtZW50cyBvZiB0aW1lIHN1Y2ggYXMgODowMCwgODoxNSwgODozMCwgODo0NSBhbmQgc28gZm9ydGguIFRyeSB0byBjZW50ZXIgd29yayBhcm91bmQgbW9ybmluZywgYWZ0ZXJub29uIGFuZCBiZWZvcmUgZGlubmVyIGlmIHBvc3NpYmxlLiBUYWtlIGx1bmNoIGFuZCBicmVha2Zhc3QgdGltZSBpbnRvIGFjY291bnQgaWYgcG9zc2libGUuIEdpdmUgdGhlIHJlc3BvbmUgaW4gSlNPTiBhcnJheSBmb3JtYXQgd2l0aCBrZXlzICdzdGFydF90aW1lJywgJ2VuZF90aW1lJywgYW5kICd0YXNrJy5cbmA7XG5cbmV4cG9ydCBjb25zdCBkYWlseVNjaGVkdWxlRXhhbXBsZUlucHV0ID0gYFxuICAgIFVzZXIgY3VycmVudCB0aW1lOiBXZWRuZXNkYXksIDIwMjMtMDYtMjFUMTg6NTY6MzctMDQ6MDBcbiAgICBVc2VyIHdvcmsgdGltZXM6IE1vbmRheTogODowMCBhbSAtIDY6MzAgcG1cbiAgICBUdWVzZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICAgIFdlZG5lc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgICBUaHVyc2RheTogODowMCBhbSAtIDY6MzAgcG1cbiAgICBGcmlkYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gICAgU2F0dXJkYXk6IDg6MDAgYW0gLSA2OjMwIHBtXG4gICAgU3VuZGF5OiA4OjAwIGFtIC0gNjozMCBwbVxuICAgIFVzZXIgaW5wdXQ6IFxuICAgICAgICBzdGFydCB0aW1lIGZvciB0YXNrczogODozMCBhbSBcbiAgICAgICAgdGFza3M6XG4gICAgICAgIEV4ZXJjaXNlXG4gICAgYDtcblxuZXhwb3J0IGNvbnN0IGRhaWx5U2NoZWR1bGVFeGFtcGxlT3V0cHV0ID0gYFt7IFwic3RhcnRfdGltZVwiOiBcIjg6MzAgYW1cIiwgXCJlbmRfdGltZVwiOiBcIjk6MTUgYW1cIiwgXCJ0YXNrXCI6IFwiRXhlcmNpc2VcIn1dYDtcbiJdfQ==