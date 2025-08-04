export const findASlotForNewEventPrompt = `
    Given user schedule find a reasonable slot for a new event. Use the JSON format  { startTime: [12 hour]:[2-digit minutes] [am | pm], endTime:  [12 hour]:[2-digit minutes] [am | pm] }. Give the JSON response only.
`;

export const findASlotForNewEventTemplate = `
    Event duration: {{eventDuration}} min.
    User schedule:
    {{userSchedule}}
`;

export const findASlotForNewEventExampleInput = `
    Event duration: 30 min.
    User schedule:
    Fri (2023-06-23):
    - Review email and prioritize tasks: 8:00 am - 9:00 am
    - Business development meeting: 9:30 am - 10:30 am
    - Market research and competitor analysis: 11:00 am - 12:30 pm.
    - Lunch break: 12:30 pm - 1:30 pm
    - Product/service brainstorming: 2:00 pm - 3:30 pm.
    - Networking event: 4:00 pm - 6:00 pm
`;

export const findASlotForNewEventExampleOutput = `
    {
        "startTime": "3:30 pm",
        "endTime": "4:00 pm"
    }
`;
