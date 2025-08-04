import { gql } from '@apollo/client';

export default gql`
  mutation InsertUserPreference(
    $userPreference: User_Preference_insert_input!
  ) {
    insert_User_Preference_one(
      object: $userPreference
      on_conflict: {
        constraint: UserPreference_pkey
        update_columns: [
          userId
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
          breakLength
          breakColor
          maxWorkLoadPercent
          backToBackMeetings
          maxNumberOfMeetings
          minNumberOfBreaks
          copyIsMeeting
          copyIsExternalMeeting
          copyColor
          deleted
          updatedAt
        ]
      }
    ) {
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
    }
  }
`;
