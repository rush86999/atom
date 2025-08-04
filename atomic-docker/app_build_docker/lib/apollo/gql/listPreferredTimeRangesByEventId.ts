import { gql } from '@apollo/client';

export default gql`
  query ListPreferredTimeRangesGivenEventId($eventId: String!) {
    PreferredTimeRange(where: { eventId: { _eq: $eventId } }) {
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
