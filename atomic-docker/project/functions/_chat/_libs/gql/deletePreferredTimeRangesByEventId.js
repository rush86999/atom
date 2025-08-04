export default `
    mutation DeletePreferredTimeRangesGivenEventId($eventId: String!) {
        delete_PreferredTimeRange(where: {eventId: {_eq: $eventId}}) {
        affected_rows
            returning {
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
    }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7Ozs7OztDQWdCZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxuICAgIG11dGF0aW9uIERlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgZGVsZXRlX1ByZWZlcnJlZFRpbWVSYW5nZSh3aGVyZToge2V2ZW50SWQ6IHtfZXE6ICRldmVudElkfX0pIHtcbiAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgIGRheU9mV2Vla1xuICAgICAgICAgICAgICAgIGVuZFRpbWVcbiAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH1cbmA7XG4iXX0=