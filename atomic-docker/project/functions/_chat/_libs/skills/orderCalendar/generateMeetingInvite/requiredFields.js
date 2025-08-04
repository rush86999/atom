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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO1FBQ0Q7WUFDRSxHQUFHLEVBQUU7Z0JBQ0gsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQ3BDLEVBQUUsS0FBSyxFQUFFLG9CQUFvQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQzdDLEVBQUUsS0FBSyxFQUFFLG1CQUFtQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7YUFDN0M7U0FDRjtRQUNELEVBQUUsS0FBSyxFQUFFLGtCQUFrQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7S0FDNUM7SUFFRCxRQUFRLEVBQUU7UUFDUixFQUFFLEtBQUssRUFBRSxhQUFhLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN0QyxFQUFFLEtBQUssRUFBRSxlQUFlLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN4QyxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNwQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNsQyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNoQyxFQUFFLEtBQUssRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNqQyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNyQyxFQUFFLEtBQUssRUFBRSxjQUFjLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN2QyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtLQUN0QztJQUNELFFBQVEsRUFBRTtRQUNSLFFBQVEsRUFBRSxFQUFFO1FBQ1osUUFBUSxFQUFFO1lBQ1I7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUNuQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDbkM7YUFDRjtZQUNELEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1lBQ2hDO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSx5QkFBeUIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUNsRCxFQUFFLEtBQUssRUFBRSxnQ0FBZ0MsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUMxRDthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMO3dCQUNFLEdBQUcsRUFBRTs0QkFDSCxFQUFFLEtBQUssRUFBRSwwQkFBMEIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFOzRCQUNuRCxFQUFFLEtBQUssRUFBRSw0QkFBNEIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUN0RDtxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSwrQkFBK0IsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN6RDthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLHVCQUF1QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQ2hELEVBQUUsS0FBSyxFQUFFLDhCQUE4QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ3hEO2FBQ0Y7WUFDRDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0w7d0JBQ0UsR0FBRyxFQUFFOzRCQUNILEVBQUUsS0FBSyxFQUFFLHdCQUF3QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQ2pELEVBQUUsS0FBSyxFQUFFLDBCQUEwQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7eUJBQ3BEO3FCQUNGO29CQUNELEVBQUUsS0FBSyxFQUFFLDZCQUE2QixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ3ZEO2FBQ0Y7U0FDRjtLQUNGO0NBQ0YsQ0FBQztBQUVGLGVBQWUsY0FBYyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuXG4vLyB1c2VySWQgYW5kIHRpbWV6b25lIGFyZSBhbHJlYWR5IHByb3ZpZGVkXG5cbmNvbnN0IHJlcXVpcmVkRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gIHJlcXVpcmVkOiBbXG4gICAge1xuICAgICAgb25lT2Y6IFtcbiAgICAgICAgeyB2YWx1ZTogJ3RpdGxlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdzdW1tYXJ5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICBdLFxuICAgIH0sXG4gICAge1xuICAgICAgYW5kOiBbXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlc1tdLmlzSG9zdCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzW10uZW1haWwnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIF0sXG4gICAgfSxcbiAgICB7IHZhbHVlOiAncmVjZWl2ZXJUaW1lem9uZScsIHR5cGU6ICdmb3JtJyB9LFxuICBdLFxuXG4gIG9wdGlvbmFsOiBbXG4gICAgeyB2YWx1ZTogJ2Rlc2NyaXB0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2NvbmZlcmVuY2VBcHAnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3N1bW1hcnknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnbm90ZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnYWxhcm1zJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2NvbmZlcmVuY2UnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndHJhbnNwYXJlbmN5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3Zpc2liaWxpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgXSxcbiAgZGF0ZVRpbWU6IHtcbiAgICByZXF1aXJlZDogW10sXG4gICAgb3B0aW9uYWw6IFtcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZHVyYXRpb24nLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZW5kVGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHsgdmFsdWU6ICdyZWN1cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0LmRheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0Lmlzb1dlZWtkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgYW5kOiBbXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd1N0YXJ0LmhvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93U3RhcnQubWludXRlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93U3RhcnQuc3RhcnRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5kYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZmluZFRpbWVXaW5kb3dFbmQuaXNvV2Vla2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhbmQ6IFtcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93RW5kLmhvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2ZpbmRUaW1lV2luZG93RW5kLm1pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdmaW5kVGltZVdpbmRvd0VuZC5zdGFydFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgfSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IHJlcXVpcmVkRmllbGRzO1xuIl19