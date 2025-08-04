export default `
    mutation DeletePreferredTimeRangesWithIds($ids: [uuid!]!) {
        delete_PreferredTimeRange(where: {id: {_in: $ids}}) {
        affected_rows
        returning {
                id
                startTime
                endTime
                eventId
                dayOfWeek
                createdDate
                updatedAt
                userId
            }
        }
    }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc1dpdGhJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzV2l0aElkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7O0NBZ0JkLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgZGVmYXVsdCBgXG4gICAgbXV0YXRpb24gRGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc1dpdGhJZHMoJGlkczogW3V1aWQhXSEpIHtcbiAgICAgICAgZGVsZXRlX1ByZWZlcnJlZFRpbWVSYW5nZSh3aGVyZToge2lkOiB7X2luOiAkaWRzfX0pIHtcbiAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgc3RhcnRUaW1lXG4gICAgICAgICAgICAgICAgZW5kVGltZVxuICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgICAgICBkYXlPZldlZWtcbiAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgfVxuYDtcbiJdfQ==