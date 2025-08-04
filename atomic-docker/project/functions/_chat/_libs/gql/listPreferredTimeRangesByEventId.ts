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
