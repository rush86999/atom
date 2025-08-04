import { gql } from '@apollo/client';

export default gql`
  mutation insertPreferredTimeRange(
    $preferredTimeRange: PreferredTimeRange_insert_input!
  ) {
    insert_PreferredTimeRange_one(object: $preferredTimeRange) {
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
