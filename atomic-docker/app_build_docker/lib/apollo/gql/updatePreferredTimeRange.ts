import { gql } from '@apollo/client';

export default gql`
  mutation UpdatePreferredTimeRange(
    $id: uuid!
    $dayOfWeek: Int
    $endTime: time!
    $startTime: time!
  ) {
    update_PreferredTimeRange_by_pk(
      pk_columns: { id: $id }
      _set: { dayOfWeek: $dayOfWeek, endTime: $endTime, startTime: $startTime }
    ) {
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
