import { gql } from '@apollo/client';

export default gql`
  mutation InsertPreferredTimeRanges(
    $preferredTimeRanges: [PreferredTimeRange_insert_input!]!
  ) {
    insert_PreferredTimeRange(objects: $preferredTimeRanges) {
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
