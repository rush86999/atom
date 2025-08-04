import { gql } from '@apollo/client';

export default gql`
  mutation DeleteAttendees($eventId: String!) {
    delete_Attendee(where: { eventId: { _eq: $eventId } }) {
      affected_rows
    }
  }
`;
