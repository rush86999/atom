import { gql } from '@apollo/client';

export default gql`
  mutation deleteReminders($userId: uuid!, $eventIds: [String!]!) {
    delete_Reminder(
      where: { userId: { _eq: $userId }, eventId: { _in: $eventIds } }
    ) {
      affected_rows
    }
  }
`;
