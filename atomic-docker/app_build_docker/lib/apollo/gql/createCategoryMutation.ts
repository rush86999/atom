import { gql } from '@apollo/client';

export default gql`
  mutation CreateCategory(
    $id: uuid!
    $userId: uuid!
    $name: String!
    $updatedAt: timestamptz
    $createdDate: timestamptz
  ) {
    insert_Category_one(
      object: {
        name: $name
        id: $id
        deleted: false
        updatedAt: $updatedAt
        createdDate: $createdDate
        userId: $userId
        defaultAvailability: false
        defaultModifiable: true
        defaultIsMeeting: false
        defaultIsExternalMeeting: false
        defaultMeetingModifiable: true
        defaultExternalMeetingModifiable: true
      }
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
