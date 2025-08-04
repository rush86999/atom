// userId and timezone are already provided
const requiredFields = {
    required: [],
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVxdWlyZWRGaWVsZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZXF1aXJlZEZpZWxkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFFQSwyQ0FBMkM7QUFFM0MsTUFBTSxjQUFjLEdBQXVCO0lBQ3pDLFFBQVEsRUFBRSxFQUFFO0lBQ1osUUFBUSxFQUFFLEVBQUU7SUFDWixRQUFRLEVBQUU7UUFDUixRQUFRLEVBQUUsRUFBRTtRQUNaLFFBQVEsRUFBRSxFQUFFO0tBQ2I7SUFDRCxVQUFVLEVBQUU7UUFDVixRQUFRLEVBQUUsRUFBRTtLQUNiO0lBQ0QsU0FBUyxFQUFFO1FBQ1QsUUFBUSxFQUFFLEVBQUU7UUFDWixRQUFRLEVBQUU7WUFDUjtnQkFDRSxLQUFLLEVBQUU7b0JBQ0wsRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7b0JBQ25DLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO2lCQUNuQzthQUNGO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFO29CQUNMLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO29CQUM5QixFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDdEM7YUFDRjtZQUNEO2dCQUNFLEtBQUssRUFBRTtvQkFDTDt3QkFDRSxHQUFHLEVBQUU7NEJBQ0gsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUU7NEJBQy9CLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO3lCQUNsQztxQkFDRjtvQkFDRCxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRTtpQkFDckM7YUFDRjtZQUNELEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFO1NBQ2pDO0tBQ0Y7Q0FDRixDQUFDO0FBRUYsZUFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5cbi8vIHVzZXJJZCBhbmQgdGltZXpvbmUgYXJlIGFscmVhZHkgcHJvdmlkZWRcblxuY29uc3QgcmVxdWlyZWRGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgcmVxdWlyZWQ6IFtdLFxuICBvcHRpb25hbDogW10sXG4gIGRhdGVUaW1lOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXSxcbiAgfSxcbiAgYXR0cmlidXRlczoge1xuICAgIHJlcXVpcmVkOiBbXSxcbiAgfSxcbiAgcXVlcnlEYXRlOiB7XG4gICAgcmVxdWlyZWQ6IFtdLFxuICAgIG9wdGlvbmFsOiBbXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2R1cmF0aW9uJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ2VuZFRpbWUnLCB0eXBlOiAnY2hhdCcgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIG9uZU9mOiBbXG4gICAgICAgICAgeyB2YWx1ZTogJ2RheScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgIHsgdmFsdWU6ICdpc29XZWVrZGF5JywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICBvbmVPZjogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGFuZDogW1xuICAgICAgICAgICAgICB7IHZhbHVlOiAnaG91cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICAgICAgICB7IHZhbHVlOiAnbWludXRlJywgdHlwZTogJ2NoYXQnIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgeyB2YWx1ZTogJ3N0YXJ0VGltZScsIHR5cGU6ICdjaGF0JyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICAgIHsgdmFsdWU6ICdyZWN1cicsIHR5cGU6ICdjaGF0JyB9LFxuICAgIF0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCByZXF1aXJlZEZpZWxkcztcbiJdfQ==