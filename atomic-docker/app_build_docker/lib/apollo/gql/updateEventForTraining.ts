import { gql } from '@apollo/client';

export default gql`
  mutation UpdateEventForTraining(
    $id: String!
    $preferredDayOfWeek: Int
    $preferredEndTimeRange: time
    $preferredTime: time
    $preferredStartTimeRange: time
    $copyAvailability: Boolean
    $copyTimeBlocking: Boolean
    $copyTimePreference: Boolean
    $copyReminders: Boolean
    $copyPriorityLevel: Boolean
    $copyModifiable: Boolean
    $copyCategories: Boolean
    $copyIsBreak: Boolean
    $copyIsMeeting: Boolean
    $copyIsExternalMeeting: Boolean
    $copyDuration: Boolean
    $copyColor: Boolean
  ) {
    update_Event_by_pk(
      pk_columns: { id: $id }
      _set: {
        preferredDayOfWeek: $preferredDayOfWeek
        preferredEndTimeRange: $preferredEndTimeRange
        preferredTime: $preferredTime
        preferredStartTimeRange: $preferredStartTimeRange
        copyAvailability: $copyAvailability
        copyTimeBlocking: $copyTimeBlocking
        copyTimePreference: $copyTimePreference
        copyReminders: $copyReminders
        copyPriorityLevel: $copyPriorityLevel
        copyModifiable: $copyModifiable
        copyCategories: $copyCategories
        copyIsBreak: $copyIsBreak
        copyIsMeeting: $copyIsMeeting
        copyIsExternalMeeting: $copyIsExternalMeeting
        copyDuration: $copyDuration
        copyColor: $copyColor
      }
    ) {
      id
      startDate
      endDate
      allDay
      recurrence
      recurrenceRule
      location
      notes
      attachments
      links
      timezone
      taskId
      taskType
      priority
      followUpEventId
      isFollowUp
      isPreEvent
      isPostEvent
      preEventId
      postEventId
      modifiable
      forEventId
      conferenceId
      maxAttendees
      attendeesOmitted
      sendUpdates
      anyoneCanAddSelf
      guestsCanInviteOthers
      guestsCanSeeOtherGuests
      originalStartDate
      originalTimezone
      originalAllDay
      status
      summary
      transparency
      visibility
      recurringEventId
      iCalUID
      htmlLink
      colorId
      creator
      organizer
      endTimeUnspecified
      extendedProperties
      hangoutLink
      guestsCanModify
      locked
      source
      eventType
      privateCopy
      backgroundColor
      foregroundColor
      useDefaultAlarms
      deleted
      createdDate
      updatedAt
      userId
      calendarId
      positiveImpactScore
      negativeImpactScore
      positiveImpactDayOfWeek
      positiveImpactTime
      negativeImpactDayOfWeek
      negativeImpactTime
      preferredDayOfWeek
      preferredTime
      isExternalMeeting
      isExternalMeetingModifiable
      isMeetingModifiable
      isMeeting
      dailyTaskList
      weeklyTaskList
      isBreak
      preferredStartTimeRange
      preferredEndTimeRange
      copyAvailability
      copyTimeBlocking
      copyTimePreference
      copyReminders
      copyPriorityLevel
      copyModifiable
      copyCategories
      copyIsBreak
      userModifiedAvailability
      userModifiedTimeBlocking
      userModifiedTimePreference
      userModifiedReminders
      userModifiedPriorityLevel
      userModifiedCategories
      userModifiedModifiable
      userModifiedIsBreak
      hardDeadline
      softDeadline
      copyIsMeeting
      copyIsExternalMeeting
      userModifiedIsMeeting
      userModifiedIsExternalMeeting
      duration
      copyDuration
      userModifiedDuration
      method
      unlink
      copyColor
      userModifiedColor
      byWeekDay
      localSynced
      title
      timeBlocking
      meetingId
      eventId
    }
  }
`;
