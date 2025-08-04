import { gql } from '@apollo/client';

export default gql`
  mutation UpdateCategoryForName(
    $id: uuid!
    $name: String!
    $updatedAt: timestamptz
  ) {
    update_Category_by_pk(
      pk_columns: { id: $id }
      _set: { name: $name, updatedAt: $updatedAt }
    ) {
      id
      name
      deleted
      createdDate
      updatedAt
      userId
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
      defaultIsBreak
      color
      copyIsMeeting
      copyIsExternalMeeting
      defaultIsMeeting
      defaultIsExternalMeeting
      defaultMeetingModifiable
      defaultExternalMeetingModifiable
    }
  }
`;
