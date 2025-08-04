// userId and timezone are already provided
const requiredFields = {
    required: [
        {
            oneOf: [
                { value: 'title', type: 'chat' },
                { value: 'summary', type: 'chat' },
            ],
        },
        {
            and: [
                { value: 'attendees', type: 'chat' },
                { value: 'attendees[].isHost.email', type: 'chat' },
                { value: 'attendees[].email', type: 'chat' },
            ],
        },
    ],
    optional: [
        { value: 'priority', type: 'chat' },
        { value: 'description', type: 'chat' },
        { value: 'conferenceApp', type: 'chat' },
        { value: 'bufferTime', type: 'chat' },
        { value: 'attendees', type: 'chat' },
        { value: 'summary', type: 'chat' },
        { value: 'notes', type: 'chat' },
        { value: 'alarms', type: 'chat' },
        { value: 'conference', type: 'chat' },
        { value: 'transparency', type: 'chat' },
        { value: 'visibility', type: 'chat' },
    ],
    dateTime: {
        required: [],
        optional: [
            {
                oneOf: [
                    { value: 'duration', type: 'chat' },
                    { value: 'endTime', type: 'chat' },
                ],
            },
            { value: 'recur', type: 'chat' },
            {
                oneOf: [
                    { value: 'findTimeWindowStart.day', type: 'chat' },
                    { value: 'findTimeWindowStart.isoWeekday', type: 'chat' },
                ],
            },
            {
                oneOf: [
                    {
                        and: [
                            { value: 'findTimeWindowStart.hour', type: 'chat' },
                            { value: 'findTimeWindowStart.minute', type: 'chat' },
                        ],
                    },
                    { value: 'findTimeWindowStart.startTime', type: 'chat' },
                ],
            },
            {
                oneOf: [
                    { value: 'findTimeWindowEnd.day', type: 'chat' },
                    { value: 'findTimeWindowEnd.isoWeekday', type: 'chat' },
                ],
            },
            {
                oneOf: [
                    {
                        and: [
                            { value: 'findTimeWindowEnd.hour', type: 'chat' },
                            { value: 'findTimeWindowEnd.minute', type: 'chat' },
                        ],
                    },
                    { value: 'findTimeWindowEnd.startTime', type: 'chat' },
                ],
            },
        ],
    },
};
export default requiredFields;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO1FBQ0Q7WUFDRSxHQUFHLEVBQUU7Z0JBQ0gsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQ3BDLEVBQUUsS0FBSyxFQUFFLDBCQUEwQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQ25ELEVBQUUsS0FBSyxFQUFFLG1CQUFtQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7YUFDN0M7U0FDRjtLQUNGO0lBRUQsUUFBUSxFQUFFO1FBQ1IsRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDbkMsRUFBRSxLQUFLLEVBQUUsYUFBYSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDdEMsRUFBRSxLQUFLLEVBQUUsZUFBZSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDeEMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDckMsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDcEMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDbEMsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDaEMsRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDakMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDckMsRUFBRSxLQUFLLEVBQUUsY0FBYyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDdkMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7S0FDdEM7SUFDRCxRQUFRLEVBQUU7UUFDUixRQUFRLEVBQUUsRUFBRTtRQUNaLFFBQVEsRUFBRTtZQUNSO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDbkMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ25DO2FBQ0Y7WUFDRCxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtZQUNoQztnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUseUJBQXlCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDbEQsRUFBRSxLQUFLLEVBQUUsZ0NBQWdDLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDMUQ7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsMEJBQTBCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTs0QkFDbkQsRUFBRSxLQUFLLEVBQUUsNEJBQTRCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTt5QkFDdEQ7cUJBQ0Y7b0JBQ0QsRUFBRSxLQUFLLEVBQUUsK0JBQStCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDekQ7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSx1QkFBdUIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUNoRCxFQUFFLEtBQUssRUFBRSw4QkFBOEIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN4RDthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMO3dCQUNFLEdBQUcsRUFBRTs0QkFDSCxFQUFFLEtBQUssRUFBRSx3QkFBd0IsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFOzRCQUNqRCxFQUFFLEtBQUssRUFBRSwwQkFBMEIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUNwRDtxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSw2QkFBNkIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN2RDthQUNGO1NBQ0Y7S0FDRjtDQUNGLENBQUM7QUFFRixlQUFlLGNBQWMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcblxuLy8gdXNlcklkIGFuZCB0aW1lem9uZSBhcmUgYWxyZWFkeSBwcm92aWRlZFxuXG5jb25zdCByZXF1aXJlZEZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICByZXF1aXJlZDogW1xuICAgIHtcbiAgICAgIG9uZU9mOiBbXG4gICAgICAgIHsgdmFsdWU6ICd0aXRsZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICAgIHtcbiAgICAgIGFuZDogW1xuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXNbXS5pc0hvc3QuZW1haWwnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlc1tdLmVtYWlsJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICBdLFxuICAgIH0sXG4gIF0sXG5cbiAgb3B0aW9uYWw6IFtcbiAgICB7IHZhbHVlOiAncHJpb3JpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnZGVzY3JpcHRpb24nLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnY29uZmVyZW5jZUFwcCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdidWZmZXJUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdzdW1tYXJ5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ25vdGVzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2FsYXJtcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdjb25mZXJlbmNlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3RyYW5zcGFyZW5jeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICd2aXNpYmlsaXR5JywgdHlwZTogJ2NoYXQnIH0sXG4gIF0sXG4gIGRhdGVUaW1lOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2R1cmF0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2VuZFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7IHZhbHVlOiAncmVjdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5kYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5pc29XZWVrZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGFuZDogW1xuICAgICAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5ob3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0Lm1pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0LnN0YXJ0VGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dFbmQuZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93RW5kLmlzb1dlZWtkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgYW5kOiBbXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5ob3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5taW51dGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dFbmQuc3RhcnRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==