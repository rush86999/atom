import { gql } from '@apollo/client';

export default gql`
  mutation DeletePreferredTimeRangesGivenEvent($eventId: String!) {
    delete_PreferredTimeRange(where: { eventId: { _eq: $eventId } }) {
      affected_rows
    }
  }
`;
