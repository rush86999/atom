export default `
query GetChatMeetingPreferenceByUserId($userId: uuid!) {
    Chat_Meeting_Preference(where: {userId: {_eq: $userId}}) {
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
