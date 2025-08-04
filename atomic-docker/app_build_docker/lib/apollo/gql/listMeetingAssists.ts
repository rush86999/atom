import { gql } from '@apollo/client';

export default gql`
  query ListMeetingAssists($userId: uuid!) {
    Meeting_Assist(
      where: { userId: { _eq: $userId } }
      order_by: { windowStartDate: desc_nulls_first }
    ) {
      allowAttendeeUpdatePreferences
      anyoneCanAddSelf
      attendeeCanModify
      attendeeCount
      attendeeRespondedCount
      backgroundColor
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
