// userId and timezone are already provided
const requiredFields = {
    required: [
        {
            oneOf: [
                { value: 'title', type: 'chat' },
                { value: 'summary', type: 'chat' },
            ],
        },
    ],
    optional: [
        { value: 'priority', type: 'chat' },
        { value: 'timePreferences', type: 'chat' },
        { value: 'description', type: 'chat' },
        { value: 'conferenceApp', type: 'chat' },
        { value: 'bufferTime', type: 'chat' },
        { value: 'oldTitle', type: 'chat' },
        { value: 'attendees', type: 'chat' },
        {
            and: [
                { value: 'attendees', type: 'chat' },
                { value: 'attendees[].isHost', type: 'chat' },
                { value: 'attendees[].email', type: 'chat' },
            ],
        },
        { value: 'summary', type: 'chat' },
        { value: 'notes', type: 'chat' },
        { value: 'alarms', type: 'chat' },
        { value: 'conference', type: 'chat' },
        { value: 'transparency', type: 'chat' },
        { value: 'visibility', type: 'chat' },
        {
            and: [
                { value: 'attendees', type: 'chat' },
                { value: 'attendees[].isHost', type: 'chat' },
                { value: 'attendees[].email', type: 'chat' },
            ],
        },
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO0tBQ0Y7SUFFRCxRQUFRLEVBQUU7UUFDUixFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNuQyxFQUFFLEtBQUssRUFBRSxpQkFBaUIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQzFDLEVBQUUsS0FBSyxFQUFFLGFBQWEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3RDLEVBQUUsS0FBSyxFQUFFLGVBQWUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3hDLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3JDLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ25DLEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3BDO1lBQ0UsR0FBRyxFQUFFO2dCQUNILEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNwQyxFQUFFLEtBQUssRUFBRSxvQkFBb0IsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUM3QyxFQUFFLEtBQUssRUFBRSxtQkFBbUIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2FBQzdDO1NBQ0Y7UUFDRCxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNsQyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNoQyxFQUFFLEtBQUssRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNqQyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNyQyxFQUFFLEtBQUssRUFBRSxjQUFjLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN2QyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNyQztZQUNFLEdBQUcsRUFBRTtnQkFDSCxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtnQkFDcEMsRUFBRSxLQUFLLEVBQUUsb0JBQW9CLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtnQkFDN0MsRUFBRSxLQUFLLEVBQUUsbUJBQW1CLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUM3QztTQUNGO0tBQ0Y7SUFDRCxRQUFRLEVBQUU7UUFDUixRQUFRLEVBQUU7WUFDUixjQUFjO1lBQ2Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUM5QixFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDdEM7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQy9CLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUNsQztxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDckM7YUFDRjtTQUNGO1FBQ0QsUUFBUSxFQUFFO1lBQ1I7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUNuQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDbkM7YUFDRjtZQUNELEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1NBQ2pDO0tBQ0Y7Q0FDRixDQUFDO0FBRUYsZUFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5cbi8vIHVzZXJJZCBhbmQgdGltZXpvbmUgYXJlIGFscmVhZHkgcHJvdmlkZWRcblxuY29uc3QgcmVxdWlyZWRGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgcmVxdWlyZWQ6IFtcbiAgICB7XG4gICAgICBvbmVPZjogW1xuICAgICAgICB7IHZhbHVlOiAndGl0bGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ3N1bW1hcnknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgIF0sXG4gICAgfSxcbiAgXSxcblxuICBvcHRpb25hbDogW1xuICAgIHsgdmFsdWU6ICdwcmlvcml0eScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICd0aW1lUHJlZmVyZW5jZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnZGVzY3JpcHRpb24nLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnY29uZmVyZW5jZUFwcCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdidWZmZXJUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ29sZFRpdGxlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHtcbiAgICAgIGFuZDogW1xuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXNbXS5pc0hvc3QnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlc1tdLmVtYWlsJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICBdLFxuICAgIH0sXG4gICAgeyB2YWx1ZTogJ3N1bW1hcnknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnbm90ZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnYWxhcm1zJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2NvbmZlcmVuY2UnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndHJhbnNwYXJlbmN5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3Zpc2liaWxpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7XG4gICAgICBhbmQ6IFtcbiAgICAgICAgeyB2YWx1ZTogJ2F0dGVuZGVlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnYXR0ZW5kZWVzW10uaXNIb3N0JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdhdHRlbmRlZXNbXS5lbWFpbCcsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICBdLFxuICBkYXRlVGltZToge1xuICAgIHJlcXVpcmVkOiBbXG4gICAgICAvLyAnc3RhcnREYXRlJ1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnaXNvV2Vla2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhbmQ6IFtcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2hvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ21pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdzdGFydFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgICBvcHRpb25hbDogW1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkdXJhdGlvbicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdlbmRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAgeyB2YWx1ZTogJ3JlY3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgXSxcbiAgfSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IHJlcXVpcmVkRmllbGRzO1xuIl19