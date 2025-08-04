export default `
    query ListPreferredTimeRangesGivenEventId($eventId: String!) {
        PreferredTimeRange(where: {eventId: {_eq: $eventId}}) {
            createdDate
            dayOfWeek
            endTime
            eventId
            id
            startTime
            updatedAt
            userId
        }
    }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0UHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7O0NBYWQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbiAgICBxdWVyeSBMaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZCgkZXZlbnRJZDogU3RyaW5nISkge1xuICAgICAgICBQcmVmZXJyZWRUaW1lUmFuZ2Uod2hlcmU6IHtldmVudElkOiB7X2VxOiAkZXZlbnRJZH19KSB7XG4gICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgICBlbmRUaW1lXG4gICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgc3RhcnRUaW1lXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgfVxuYDtcbiJdfQ==