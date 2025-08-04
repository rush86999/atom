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
        { value: 'bufferTime', type: 'chat' },
        { value: 'notes', type: 'chat' },
        { value: 'summary', type: 'chat' },
        { value: 'alarms', type: 'chat' },
        { value: 'transparency', type: 'chat' },
        { value: 'visibility', type: 'chat' },
    ],
    dateTime: {
        required: [
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
            // 'startDate'
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO0tBQ0Y7SUFFRCxRQUFRLEVBQUU7UUFDUixFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNuQyxFQUFFLEtBQUssRUFBRSxpQkFBaUIsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQzFDLEVBQUUsS0FBSyxFQUFFLGFBQWEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3RDLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3JDLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2hDLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2xDLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ2pDLEVBQUUsS0FBSyxFQUFFLGNBQWMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1FBQ3ZDLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO0tBQ3RDO0lBQ0QsUUFBUSxFQUFFO1FBQ1IsUUFBUSxFQUFFO1lBQ1I7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUM5QixFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDdEM7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQy9CLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUNsQztxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDckM7YUFDRjtTQUNGO1FBQ0QsUUFBUSxFQUFFO1lBQ1IsY0FBYztZQUNkO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDbkMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ25DO2FBQ0Y7WUFDRCxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtTQUNqQztLQUNGO0NBQ0YsQ0FBQztBQUVGLGVBQWUsY0FBYyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuXG4vLyB1c2VySWQgYW5kIHRpbWV6b25lIGFyZSBhbHJlYWR5IHByb3ZpZGVkXG5cbmNvbnN0IHJlcXVpcmVkRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gIHJlcXVpcmVkOiBbXG4gICAge1xuICAgICAgb25lT2Y6IFtcbiAgICAgICAgeyB2YWx1ZTogJ3RpdGxlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIHsgdmFsdWU6ICdzdW1tYXJ5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICBdLFxuICAgIH0sXG4gIF0sXG5cbiAgb3B0aW9uYWw6IFtcbiAgICB7IHZhbHVlOiAncHJpb3JpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndGltZVByZWZlcmVuY2VzJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2Rlc2NyaXB0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2J1ZmZlclRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnbm90ZXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdhbGFybXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndHJhbnNwYXJlbmN5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3Zpc2liaWxpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgXSxcbiAgZGF0ZVRpbWU6IHtcbiAgICByZXF1aXJlZDogW1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnaXNvV2Vla2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhbmQ6IFtcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2hvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ21pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdzdGFydFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgICBvcHRpb25hbDogW1xuICAgICAgLy8gJ3N0YXJ0RGF0ZSdcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZHVyYXRpb24nLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZW5kVGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHsgdmFsdWU6ICdyZWN1cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==