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
        { value: 'description', type: 'chat' },
        { value: 'bufferTime', type: 'chat' },
        { value: 'summary', type: 'chat' },
        { value: 'notes', type: 'chat' },
        { value: 'alarms', type: 'chat' },
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO0tBQ0Y7SUFFRCxRQUFRLEVBQUU7UUFDUixFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNuQyxFQUFFLEtBQUssRUFBRSxhQUFhLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN0QyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNyQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNsQyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNoQyxFQUFFLEtBQUssRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUNqQyxFQUFFLEtBQUssRUFBRSxjQUFjLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtRQUN2QyxFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtLQUN0QztJQUNELFFBQVEsRUFBRTtRQUNSLFFBQVEsRUFBRTtZQUNSLGNBQWM7WUFDZDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQzlCLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN0QzthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMO3dCQUNFLEdBQUcsRUFBRTs0QkFDSCxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTs0QkFDL0IsRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7eUJBQ2xDO3FCQUNGO29CQUNELEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNyQzthQUNGO1NBQ0Y7UUFDRCxRQUFRLEVBQUU7WUFDUjtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQ25DLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNuQzthQUNGO1lBQ0QsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7U0FDakM7S0FDRjtDQUNGLENBQUM7QUFFRixlQUFlLGNBQWMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcblxuLy8gdXNlcklkIGFuZCB0aW1lem9uZSBhcmUgYWxyZWFkeSBwcm92aWRlZFxuXG5jb25zdCByZXF1aXJlZEZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICByZXF1aXJlZDogW1xuICAgIHtcbiAgICAgIG9uZU9mOiBbXG4gICAgICAgIHsgdmFsdWU6ICd0aXRsZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICBdLFxuXG4gIG9wdGlvbmFsOiBbXG4gICAgeyB2YWx1ZTogJ3ByaW9yaXR5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2Rlc2NyaXB0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ2J1ZmZlclRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdub3RlcycsIHR5cGU6ICdjaGF0JyB9LFxuICAgIHsgdmFsdWU6ICdhbGFybXMnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICB7IHZhbHVlOiAndHJhbnNwYXJlbmN5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgeyB2YWx1ZTogJ3Zpc2liaWxpdHknLCB0eXBlOiAnY2hhdCcgfSxcbiAgXSxcbiAgZGF0ZVRpbWU6IHtcbiAgICByZXF1aXJlZDogW1xuICAgICAgLy8gJ3N0YXJ0RGF0ZSdcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2lzb1dlZWtkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgYW5kOiBbXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdob3VyJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICAgIHsgdmFsdWU6ICdtaW51dGUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnc3RhcnRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgIF0sXG4gICAgb3B0aW9uYWw6IFtcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7IHZhbHVlOiAnZHVyYXRpb24nLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnZW5kVGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHsgdmFsdWU6ICdyZWN1cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==