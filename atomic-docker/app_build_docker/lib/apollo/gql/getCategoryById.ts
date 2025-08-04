import { gql } from '@apollo/client';

export default gql`
  query GetCategoryById($id: uuid!) {
    Category_by_pk(id: $id) {
      color
      copyAvailability
      copyIsBreak
      copyIsExternalMeeting
      copyIsMeeting
      copyModifiable
      copyPriorityLevel
      copyReminders
      copyTimeBlocking
      copyTimePreference
      createdDate
      defaultAvailability
      defaultExternalMeetingModifiable
      defaultIsBreak
      defaultIsExternalMeeting
      defaultIsMeeting
      defaultMeetingModifiable
      defaultModifiable
      defaultPriorityLevel
      defaultReminders
      defaultTimeBlocking
      defaultTimePreference
      deleted
      id
      name
      updatedAt
      userId
    }
  }
`;
