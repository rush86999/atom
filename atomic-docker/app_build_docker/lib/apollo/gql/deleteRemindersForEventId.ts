import { gql } from '@apollo/client';

export default gql`
  mutation deleteRemindersForEventId($eventId: String!) {
    delete_Reminder(where: { eventId: { _eq: $eventId } }) {
      affected_rows
      returning {
        id
        reminderDate
        eventId
        timezone
        method
        minutes
        useDefault
        deleted
        createdDate
        updatedAt
        userId
      }
    }
  }
`;
