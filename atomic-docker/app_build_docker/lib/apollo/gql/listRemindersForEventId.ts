import { gql } from '@apollo/client';

export default gql`
  query listRemindersForEventId($eventId: String!) {
    Reminder(where: { eventId: { _eq: $eventId } }) {
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
`;
