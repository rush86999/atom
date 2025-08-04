// userId and timezone are already provided
const requiredFields = {
    required: [{ value: 'title', type: 'chat' }],
    optional: [],
    dateTime: {
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
        ],
    },
};
export default requiredFields;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRSxDQUFDLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLENBQUM7SUFDNUMsUUFBUSxFQUFFLEVBQUU7SUFDWixRQUFRLEVBQUU7UUFDUixRQUFRLEVBQUUsRUFBRTtRQUNaLFFBQVEsRUFBRTtZQUNSO2dCQUNFLEtBQUssRUFBRTtvQkFDTCxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtvQkFDbkMsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7aUJBQ25DO2FBQ0Y7WUFDRDtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQzlCLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUN0QzthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMO3dCQUNFLEdBQUcsRUFBRTs0QkFDSCxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTs0QkFDL0IsRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7eUJBQ2xDO3FCQUNGO29CQUNELEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNyQzthQUNGO1NBQ0Y7S0FDRjtDQUNGLENBQUM7QUFFRixlQUFlLGNBQWMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcblxuLy8gdXNlcklkIGFuZCB0aW1lem9uZSBhcmUgYWxyZWFkeSBwcm92aWRlZFxuXG5jb25zdCByZXF1aXJlZEZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICByZXF1aXJlZDogW3sgdmFsdWU6ICd0aXRsZScsIHR5cGU6ICdjaGF0JyB9XSxcbiAgb3B0aW9uYWw6IFtdLFxuICBkYXRlVGltZToge1xuICAgIHJlcXVpcmVkOiBbXSxcbiAgICBvcHRpb25hbDogW1xuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkdXJhdGlvbicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdlbmRUaW1lJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHsgdmFsdWU6ICdkYXknLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICB7IHZhbHVlOiAnaXNvV2Vla2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgb25lT2Y6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhbmQ6IFtcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ2hvdXInLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgICAgICAgeyB2YWx1ZTogJ21pbnV0ZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdzdGFydFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgfSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IHJlcXVpcmVkRmllbGRzO1xuIl19