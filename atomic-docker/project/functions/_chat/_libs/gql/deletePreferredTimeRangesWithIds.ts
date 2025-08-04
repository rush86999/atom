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
