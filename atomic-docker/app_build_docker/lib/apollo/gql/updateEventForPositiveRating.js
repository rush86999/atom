"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateEventForPositiveRating(
    $id: String!
    $positiveImpactScore: Int!
    $positiveImpactDayOfWeek: Int!
    $positiveImpactTime: time!
  ) {
    update_Event_by_pk(
      pk_columns: { id: $id }
      _set: {
        positiveImpactScore: $positiveImpactScore
        positiveImpactDayOfWeek: $positiveImpactDayOfWeek
        positiveImpactTime: $positiveImpactTime
        negativeImpactDayOfWeek: null
        negativeImpactScore: null
        negativeImpactTime: null
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlRXZlbnRGb3JQb3NpdGl2ZVJhdGluZy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZUV2ZW50Rm9yUG9zaXRpdmVSYXRpbmcudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FrSWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlRXZlbnRGb3JQb3NpdGl2ZVJhdGluZyhcbiAgICAkaWQ6IFN0cmluZyFcbiAgICAkcG9zaXRpdmVJbXBhY3RTY29yZTogSW50IVxuICAgICRwb3NpdGl2ZUltcGFjdERheU9mV2VlazogSW50IVxuICAgICRwb3NpdGl2ZUltcGFjdFRpbWU6IHRpbWUhXG4gICkge1xuICAgIHVwZGF0ZV9FdmVudF9ieV9wayhcbiAgICAgIHBrX2NvbHVtbnM6IHsgaWQ6ICRpZCB9XG4gICAgICBfc2V0OiB7XG4gICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmU6ICRwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOiAkcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lOiAkcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrOiBudWxsXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmU6IG51bGxcbiAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lOiBudWxsXG4gICAgICB9XG4gICAgKSB7XG4gICAgICBpZFxuICAgICAgc3RhcnREYXRlXG4gICAgICBlbmREYXRlXG4gICAgICBhbGxEYXlcbiAgICAgIHJlY3VycmVuY2VcbiAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICBsb2NhdGlvblxuICAgICAgbm90ZXNcbiAgICAgIGF0dGFjaG1lbnRzXG4gICAgICBsaW5rc1xuICAgICAgdGltZXpvbmVcbiAgICAgIHRhc2tJZFxuICAgICAgdGFza1R5cGVcbiAgICAgIHByaW9yaXR5XG4gICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgIGlzRm9sbG93VXBcbiAgICAgIGlzUHJlRXZlbnRcbiAgICAgIGlzUG9zdEV2ZW50XG4gICAgICBwcmVFdmVudElkXG4gICAgICBwb3N0RXZlbnRJZFxuICAgICAgbW9kaWZpYWJsZVxuICAgICAgZm9yRXZlbnRJZFxuICAgICAgY29uZmVyZW5jZUlkXG4gICAgICBtYXhBdHRlbmRlZXNcbiAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgIHNlbmRVcGRhdGVzXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgIHN0YXR1c1xuICAgICAgc3VtbWFyeVxuICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICB2aXNpYmlsaXR5XG4gICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICBpQ2FsVUlEXG4gICAgICBodG1sTGlua1xuICAgICAgY29sb3JJZFxuICAgICAgY3JlYXRvclxuICAgICAgb3JnYW5pemVyXG4gICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgaGFuZ291dExpbmtcbiAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgbG9ja2VkXG4gICAgICBzb3VyY2VcbiAgICAgIGV2ZW50VHlwZVxuICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICBkZWxldGVkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIGNhbGVuZGFySWRcbiAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICBuZWdhdGl2ZUltcGFjdFRpbWVcbiAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgaXNNZWV0aW5nXG4gICAgICBkYWlseVRhc2tMaXN0XG4gICAgICB3ZWVrbHlUYXNrTGlzdFxuICAgICAgaXNCcmVha1xuICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICBjb3B5SXNCcmVha1xuICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgIGhhcmREZWFkbGluZVxuICAgICAgc29mdERlYWRsaW5lXG4gICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIGR1cmF0aW9uXG4gICAgICBjb3B5RHVyYXRpb25cbiAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICBtZXRob2RcbiAgICAgIHVubGlua1xuICAgICAgY29weUNvbG9yXG4gICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgYnlXZWVrRGF5XG4gICAgICBsb2NhbFN5bmNlZFxuICAgICAgdGl0bGVcbiAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgbWVldGluZ0lkXG4gICAgICBldmVudElkXG4gICAgfVxuICB9XG5gO1xuIl19