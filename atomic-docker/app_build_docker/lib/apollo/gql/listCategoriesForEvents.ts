import gql from 'graphql-tag';

export default gql`
  query ListCategoriesForEventIds($eventIds: [String!]!) {
    Category_Event(where: { eventId: { _in: $eventIds } }) {
      Category {
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
      eventId
      categoryId
      createdDate
      deleted
      id
      updatedAt
      userId
    }
  }
`;
