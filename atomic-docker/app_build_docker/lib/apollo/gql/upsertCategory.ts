import { gql } from '@apollo/client';

export default gql`
  mutation InsertCategory($categories: [Category_insert_input!]!) {
    insert_Category(
      objects: $categories
      on_conflict: {
        constraint: Category_pkey
        update_columns: [
          name
          copyAvailability
          copyTimeBlocking
          copyTimePreference
          copyReminders
          copyPriorityLevel
          copyModifiable
          defaultAvailability
          defaultTimeBlocking
          defaultTimePreference
          defaultReminders
          defaultPriorityLevel
          defaultModifiable
          copyIsBreak
          color
          copyIsMeeting
          copyIsExternalMeeting
          defaultIsMeeting
          defaultIsExternalMeeting
          deleted
          updatedAt
          defaultIsBreak
          defaultMeetingModifiable
          defaultExternalMeetingModifiable
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
