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
        required: [
            // 'startDate'
            {
                oneOf: [
                    { value: 'day', type: 'chat' },
                    { value: 'isoWeekday', type: 'chat' },
                ],
            },
            {
                oneOf: [
                    {
                        and: [
                            { value: 'hour', type: 'chat' },
                            { value: 'minute', type: 'chat' },
                        ],
                    },
                    { value: 'startTime', type: 'chat' },
                ],
            },
        ],
        optional: [
            {
                oneOf: [
                    { value: 'duration', type: 'chat' },
                    { value: 'endTime', type: 'chat' },
                ],
            },
            { value: 'recur', type: 'chat' },
        ],
    },
};
export default requiredFields;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO1FBQ0Q7WUFDRSxHQUFHLEVBQUU7Z0JBQ0gsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQ3BDLEVBQUUsS0FBSyxFQUFFLG9CQUFvQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7Z0JBQzdDLEVBQUUsS0FBSyxFQUFFLG1CQUFtQixFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7YUFDN0M7U0FDRjtLQUNGO0lBRUQsUUFBUSxFQUFFO1FBQ1IsRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDbkMsRUFBRSxLQUFLLEVBQUUsYUFBYSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDdEMsRUFBRSxLQUFLLEVBQUUsZUFBZSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDeEMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDckMsRUFBRSxLQUFLLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDcEMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDbEMsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDaEMsRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDakMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDckMsRUFBRSxLQUFLLEVBQUUsY0FBYyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7UUFDdkMsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7S0FDdEM7SUFDRCxRQUFRLEVBQUU7UUFDUixRQUFRLEVBQUU7WUFDUixjQUFjO1lBQ2Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUM5QixFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDdEM7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQy9CLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUNsQztxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDckM7YUFDRjtTQUNGO1FBQ0QsUUFBUSxFQUFFO1lBQ1I7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUNuQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDbkM7YUFDRjtZQUNELEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1NBQ2pDO0tBQ0Y7Q0FDRixDQUFDO0FBRUYsZUFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5cbi8vIHVzZXJJZCBhbmQgdGltZXpvbmUgYXJlIGFscmVhZHkgcHJvdmlkZWRcblxuY29uc3QgcmVxdWlyZWRGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgcmVxdWlyZWQ6IFtcbiAgICB7XG4gICAgICBvbmVPZjogW1xuICAgICAgICB7IHZhbHVlOiAndGl0bGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ3N1bW1hcnknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIF0sXG4gICAgfSxcbiAgICB7XG4gICAgICBhbmQ6IFtcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzW10uaXNIb3N0JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXNbXS5lbWFpbCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICBdLFxuXG4gIG9wdGlvbmFsOiBbXG4gICAgeyB2YWx1ZTogJ3ByaW9yaXR5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2Rlc2NyaXB0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2NvbmZlcmVuY2VBcHAnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnYnVmZmVyVGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdhdHRlbmRlZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdub3RlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdhbGFybXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnY29uZmVyZW5jZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICd0cmFuc3BhcmVuY3knLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndmlzaWJpbGl0eScsIHR5cGU6ICdjaGF0JyB9LFxuICBdLFxuICBkYXRlVGltZToge1xuICAgIHJlcXVpcmVkOiBbXG4gICAgICAvLyAnc3RhcnREYXRlJ1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnaXNvV2Vla2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhbmQ6IFtcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2hvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ21pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdzdGFydFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgICBvcHRpb25hbDogW1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkdXJhdGlvbicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdlbmRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAgeyB2YWx1ZTogJ3JlY3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgXSxcbiAgfSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IHJlcXVpcmVkRmllbGRzO1xuIl19