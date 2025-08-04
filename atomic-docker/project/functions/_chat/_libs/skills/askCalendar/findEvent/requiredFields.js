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
    optional: [],
    dateTime: {
        required: [],
        optional: [],
    },
    attributes: {
        required: [],
    },
    queryDate: {
        required: [],
        optional: [
            {
                oneOf: [
                    { value: 'duration', type: 'chat' },
                    { value: 'endTime', type: 'chat' },
                ],
            },
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
            { value: 'recur', type: 'chat' },
        ],
    },
};
export default requiredFields;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRTtRQUNSO1lBQ0UsS0FBSyxFQUFFO2dCQUNMLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2dCQUNoQyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTthQUNuQztTQUNGO0tBQ0Y7SUFDRCxRQUFRLEVBQUUsRUFBRTtJQUNaLFFBQVEsRUFBRTtRQUNSLFFBQVEsRUFBRSxFQUFFO1FBQ1osUUFBUSxFQUFFLEVBQUU7S0FDYjtJQUNELFVBQVUsRUFBRTtRQUNWLFFBQVEsRUFBRSxFQUFFO0tBQ2I7SUFDRCxTQUFTLEVBQUU7UUFDVCxRQUFRLEVBQUUsRUFBRTtRQUNaLFFBQVEsRUFBRTtZQUNSO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDbkMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ25DO2FBQ0Y7WUFDRDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQzlCLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN0QzthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMO3dCQUNFLEdBQUcsRUFBRTs0QkFDSCxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTs0QkFDL0IsRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7eUJBQ2xDO3FCQUNGO29CQUNELEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNyQzthQUNGO1lBQ0QsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7U0FDakM7S0FDRjtDQUNGLENBQUM7QUFFRixlQUFlLGNBQWMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcblxuLy8gdXNlcklkIGFuZCB0aW1lem9uZSBhcmUgYWxyZWFkeSBwcm92aWRlZFxuXG5jb25zdCByZXF1aXJlZEZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICByZXF1aXJlZDogW1xuICAgIHtcbiAgICAgIG9uZU9mOiBbXG4gICAgICAgIHsgdmFsdWU6ICd0aXRsZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICB7IHZhbHVlOiAnc3VtbWFyeScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgXSxcbiAgICB9LFxuICBdLFxuICBvcHRpb25hbDogW10sXG4gIGRhdGVUaW1lOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXSxcbiAgfSxcbiAgYXR0cmlidXRlczoge1xuICAgIHJlcXVpcmVkOiBbXSxcbiAgfSxcbiAgcXVlcnlEYXRlOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2R1cmF0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2VuZFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdpc29XZWVrZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGFuZDogW1xuICAgICAgICAgICAgICB7IHZhbHVlOiAnaG91cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgICB7IHZhbHVlOiAnbWludXRlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ3N0YXJ0VGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHsgdmFsdWU6ICdyZWN1cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==