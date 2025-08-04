import { gql } from '@apollo/client';

export default gql`
  query GetUserPreferenceForUser($userId: uuid!) {
    User_Preference(where: { userId: { _eq: $userId } }) {
      id
      reminders
      followUp
      isPublicCalendar
      publicCalendarCategories
      startTimes
      endTimes
      copyAvailability
      copyTimeBlocking
      copyTimePreference
      copyReminders
      copyPriorityLevel
      copyModifiable
      copyCategories
      copyIsBreak
      maxWorkLoadPercent
      backToBackMeetings
      maxNumberOfMeetings
      minNumberOfBreaks
      breakLength
      breakColor
      copyIsMeeting
      copyIsExternalMeeting
      copyColor
      deleted
      createdDate
      updatedAt
      userId
      onBoarded
    }
  }
`;
