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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluZEFTbG90Rm9yTmV3RXZlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmaW5kQVNsb3RGb3JOZXdFdmVudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxNQUFNLENBQUMsTUFBTSwwQkFBMEIsR0FBRzs7Q0FFekMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLDRCQUE0QixHQUFHOzs7O0NBSTNDLENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSxnQ0FBZ0MsR0FBRzs7Ozs7Ozs7OztDQVUvQyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0saUNBQWlDLEdBQUc7Ozs7O0NBS2hELENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgY29uc3QgZmluZEFTbG90Rm9yTmV3RXZlbnRQcm9tcHQgPSBgXG4gICAgR2l2ZW4gdXNlciBzY2hlZHVsZSBmaW5kIGEgcmVhc29uYWJsZSBzbG90IGZvciBhIG5ldyBldmVudC4gVXNlIHRoZSBKU09OIGZvcm1hdCAgeyBzdGFydFRpbWU6IFsxMiBob3VyXTpbMi1kaWdpdCBtaW51dGVzXSBbYW0gfCBwbV0sIGVuZFRpbWU6ICBbMTIgaG91cl06WzItZGlnaXQgbWludXRlc10gW2FtIHwgcG1dIH0uIEdpdmUgdGhlIEpTT04gcmVzcG9uc2Ugb25seS5cbmA7XG5cbmV4cG9ydCBjb25zdCBmaW5kQVNsb3RGb3JOZXdFdmVudFRlbXBsYXRlID0gYFxuICAgIEV2ZW50IGR1cmF0aW9uOiB7e2V2ZW50RHVyYXRpb259fSBtaW4uXG4gICAgVXNlciBzY2hlZHVsZTpcbiAgICB7e3VzZXJTY2hlZHVsZX19XG5gO1xuXG5leHBvcnQgY29uc3QgZmluZEFTbG90Rm9yTmV3RXZlbnRFeGFtcGxlSW5wdXQgPSBgXG4gICAgRXZlbnQgZHVyYXRpb246IDMwIG1pbi5cbiAgICBVc2VyIHNjaGVkdWxlOlxuICAgIEZyaSAoMjAyMy0wNi0yMyk6XG4gICAgLSBSZXZpZXcgZW1haWwgYW5kIHByaW9yaXRpemUgdGFza3M6IDg6MDAgYW0gLSA5OjAwIGFtXG4gICAgLSBCdXNpbmVzcyBkZXZlbG9wbWVudCBtZWV0aW5nOiA5OjMwIGFtIC0gMTA6MzAgYW1cbiAgICAtIE1hcmtldCByZXNlYXJjaCBhbmQgY29tcGV0aXRvciBhbmFseXNpczogMTE6MDAgYW0gLSAxMjozMCBwbS5cbiAgICAtIEx1bmNoIGJyZWFrOiAxMjozMCBwbSAtIDE6MzAgcG1cbiAgICAtIFByb2R1Y3Qvc2VydmljZSBicmFpbnN0b3JtaW5nOiAyOjAwIHBtIC0gMzozMCBwbS5cbiAgICAtIE5ldHdvcmtpbmcgZXZlbnQ6IDQ6MDAgcG0gLSA2OjAwIHBtXG5gO1xuXG5leHBvcnQgY29uc3QgZmluZEFTbG90Rm9yTmV3RXZlbnRFeGFtcGxlT3V0cHV0ID0gYFxuICAgIHtcbiAgICAgICAgXCJzdGFydFRpbWVcIjogXCIzOjMwIHBtXCIsXG4gICAgICAgIFwiZW5kVGltZVwiOiBcIjQ6MDAgcG1cIlxuICAgIH1cbmA7XG4iXX0=