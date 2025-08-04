import { gql } from '@apollo/client';

export default gql`
  mutation DeletePreferredTimeRangeById($id: uuid!) {
    delete_PreferredTimeRange_by_pk(id: $id) {
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
