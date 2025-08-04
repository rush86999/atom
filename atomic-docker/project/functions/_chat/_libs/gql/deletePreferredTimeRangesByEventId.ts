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
