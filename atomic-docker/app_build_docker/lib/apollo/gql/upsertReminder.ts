import { gql } from '@apollo/client';

export default gql`
  mutation InsertReminder($reminders: [Reminder_insert_input!]!) {
    insert_Reminder(
      objects: $reminders
      on_conflict: {
        constraint: Reminder_pkey
        update_columns: [
          eventId
          reminderDate
          timezone
          method
          minutes
          useDefault
          updatedAt
          deleted
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
