import { gql } from '@apollo/client';

export default gql`
  mutation UpsertChatMeetingPreference(
    $chatMeetingPreference: Chat_Meeting_Preference_insert_input!
  ) {
    insert_Chat_Meeting_Preference_one(
      object: $chatMeetingPreference
      on_conflict: {
        constraint: Chat_Meeting_Preference_pkey
        update_columns: [
          anyoneCanAddSelf
          bufferTime
          conferenceApp
          duration
          enableConference
          guestsCanInviteOthers
          guestsCanSeeOtherGuests
          name
          primaryEmail
          reminders
          sendUpdates
          timezone
          transparency
          updatedAt
          useDefaultAlarms
          visibility
        ]
      }
    ) {
      anyoneCanAddSelf
      bufferTime
      conferenceApp
      createdDate
      duration
      enableConference
      guestsCanInviteOthers
      guestsCanSeeOtherGuests
      id
      name
      primaryEmail
      reminders
      sendUpdates
      timezone
      transparency
      updatedAt
      useDefaultAlarms
      userId
      visibility
    }
  }
`;
