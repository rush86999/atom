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
                { value: 'attendees[].isHost', type: 'chat' },
                { value: 'attendees[].email', type: 'chat' },
            ],
        },
        { value: 'receiverTimezone', type: 'form' },
        { value: 'dayAvailabilitySummary', type: 'form' },
    ],
    optional: [
        { value: 'description', type: 'chat' },
        { value: 'conferenceApp', type: 'chat' },
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO1FBQ0Q7WUFDRSxHQUFHLEVBQUU7Z0JBQ0gsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQ3BDLEVBQUUsS0FBSyxFQUFFLG9CQUFvQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQzdDLEVBQUUsS0FBSyxFQUFFLG1CQUFtQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7YUFDN0M7U0FDRjtRQUNELEVBQUUsS0FBSyxFQUFFLGtCQUFrQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDM0MsRUFBRSxLQUFLLEVBQUUsd0JBQXdCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtLQUNsRDtJQUVELFFBQVEsRUFBRTtRQUNSLEVBQUUsS0FBSyxFQUFFLGFBQWEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3RDLEVBQUUsS0FBSyxFQUFFLGVBQWUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3hDLEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3BDLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2xDLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2hDLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2pDLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3JDLEVBQUUsS0FBSyxFQUFFLGNBQWMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3ZDLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO0tBQ3RDO0lBQ0QsUUFBUSxFQUFFO1FBQ1IsUUFBUSxFQUFFLEVBQUU7UUFDWixRQUFRLEVBQUU7WUFDUjtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQ25DLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNuQzthQUNGO1lBQ0QsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7WUFDaEM7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLHlCQUF5QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQ2xELEVBQUUsS0FBSyxFQUFFLGdDQUFnQyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQzFEO2FBQ0Y7WUFDRDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0w7d0JBQ0UsR0FBRyxFQUFFOzRCQUNILEVBQUUsS0FBSyxFQUFFLDBCQUEwQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQ25ELEVBQUUsS0FBSyxFQUFFLDRCQUE0QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7eUJBQ3REO3FCQUNGO29CQUNELEVBQUUsS0FBSyxFQUFFLCtCQUErQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ3pEO2FBQ0Y7WUFDRDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsdUJBQXVCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDaEQsRUFBRSxLQUFLLEVBQUUsOEJBQThCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDeEQ7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsd0JBQXdCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTs0QkFDakQsRUFBRSxLQUFLLEVBQUUsMEJBQTBCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTt5QkFDcEQ7cUJBQ0Y7b0JBQ0QsRUFBRSxLQUFLLEVBQUUsNkJBQTZCLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDdkQ7YUFDRjtTQUNGO0tBQ0Y7Q0FDRixDQUFDO0FBRUYsZUFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5cbi8vIHVzZXJJZCBhbmQgdGltZXpvbmUgYXJlIGFscmVhZHkgcHJvdmlkZWRcblxuY29uc3QgcmVxdWlyZWRGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgcmVxdWlyZWQ6IFtcbiAgICB7XG4gICAgICBvbmVPZjogW1xuICAgICAgICB7IHZhbHVlOiAndGl0bGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ3N1bW1hcnknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIF0sXG4gICAgfSxcbiAgICB7XG4gICAgICBhbmQ6IFtcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzW10uaXNIb3N0JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXNbXS5lbWFpbCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICAgIHsgdmFsdWU6ICdyZWNlaXZlclRpbWV6b25lJywgdHlwZTogJ2Zvcm0nIH0sXG4gICAgeyB2YWx1ZTogJ2RheUF2YWlsYWJpbGl0eVN1bW1hcnknLCB0eXBlOiAnZm9ybScgfSxcbiAgXSxcblxuICBvcHRpb25hbDogW1xuICAgIHsgdmFsdWU6ICdkZXNjcmlwdGlvbicsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdjb25mZXJlbmNlQXBwJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdzdW1tYXJ5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ25vdGVzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2FsYXJtcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdjb25mZXJlbmNlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3RyYW5zcGFyZW5jeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICd2aXNpYmlsaXR5JywgdHlwZTogJ2NoYXQnIH0sXG4gIF0sXG4gIGRhdGVUaW1lOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2R1cmF0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2VuZFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7IHZhbHVlOiAncmVjdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5kYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5pc29XZWVrZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGFuZDogW1xuICAgICAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dTdGFydC5ob3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0Lm1pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0LnN0YXJ0VGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dFbmQuZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93RW5kLmlzb1dlZWtkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgYW5kOiBbXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5ob3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5taW51dGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dFbmQuc3RhcnRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==