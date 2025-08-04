export default `
    mutation UpsertPreferredTimeRanges($preferredTimeRanges: [PreferredTimeRange_insert_input!]!) {
        insert_PreferredTimeRange(objects: $preferredTimeRanges, on_conflict: {constraint: PreferredTimeRange_pkey, update_columns: [
        dayOfWeek,
        endTime,
        startTime,
    ]}) {
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
