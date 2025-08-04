import { gql } from '@apollo/client';

export default gql`
  mutation DeleteMeetingAssistById($id: uuid!) {
    delete_Meeting_Assist_by_pk(id: $id) {
      allowAttendeeUpdatePreferences
      anyoneCanAddSelf
      attendeeCanModify
      attendeeCount
      backgroundColor
      attendeeRespondedCount
      bufferTime
      calendarId
      cancelIfAnyRefuse
      cancelled
      colorId
      conferenceApp
      createdDate
      duration
      enableAttendeePreferences
      enableConference
      enableHostPreferences
      endDate
      eventId
      expireDate
      foregroundColor
      frequency
      guaranteeAvailability
      guestsCanInviteOthers
      guestsCanSeeOtherGuests
      id
      interval
      location
      minThresholdCount
      notes
      originalMeetingId
      priority
      reminders
      sendUpdates
      startDate
      summary
      timezone
      transparency
      until
      updatedAt
      useDefaultAlarms
      userId
      visibility
      windowEndDate
      windowStartDate
      lockAfter
    }
  }
`;
