import { gql } from '@apollo/client';

export default gql`
  query listChatMeetingPreferences($userId: uuid!) {
    Chat_Meeting_Preference(where: { userId: { _eq: $userId } }) {
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
