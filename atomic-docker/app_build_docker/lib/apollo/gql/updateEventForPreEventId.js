"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateEventForPreEventId(
    $id: String!
    $preEventId: String!
    $timeBlocking: jsonb
  ) {
    update_Event_by_pk(
      pk_columns: { id: $id }
      _set: { preEventId: $preEventId, timeBlocking: $timeBlocking }
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlRXZlbnRGb3JQcmVFdmVudElkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXBkYXRlRXZlbnRGb3JQcmVFdmVudElkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQTBIakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBVcGRhdGVFdmVudEZvclByZUV2ZW50SWQoXG4gICAgJGlkOiBTdHJpbmchXG4gICAgJHByZUV2ZW50SWQ6IFN0cmluZyFcbiAgICAkdGltZUJsb2NraW5nOiBqc29uYlxuICApIHtcbiAgICB1cGRhdGVfRXZlbnRfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyBwcmVFdmVudElkOiAkcHJlRXZlbnRJZCwgdGltZUJsb2NraW5nOiAkdGltZUJsb2NraW5nIH1cbiAgICApIHtcbiAgICAgIGlkXG4gICAgICBzdGFydERhdGVcbiAgICAgIGVuZERhdGVcbiAgICAgIGFsbERheVxuICAgICAgcmVjdXJyZW5jZVxuICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgIGxvY2F0aW9uXG4gICAgICBub3Rlc1xuICAgICAgYXR0YWNobWVudHNcbiAgICAgIGxpbmtzXG4gICAgICB0aW1lem9uZVxuICAgICAgdGFza0lkXG4gICAgICB0YXNrVHlwZVxuICAgICAgcHJpb3JpdHlcbiAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgaXNGb2xsb3dVcFxuICAgICAgaXNQcmVFdmVudFxuICAgICAgaXNQb3N0RXZlbnRcbiAgICAgIHByZUV2ZW50SWRcbiAgICAgIHBvc3RFdmVudElkXG4gICAgICBtb2RpZmlhYmxlXG4gICAgICBmb3JFdmVudElkXG4gICAgICBjb25mZXJlbmNlSWRcbiAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlXG4gICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgc3RhdHVzXG4gICAgICBzdW1tYXJ5XG4gICAgICB0cmFuc3BhcmVuY3lcbiAgICAgIHZpc2liaWxpdHlcbiAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgIGlDYWxVSURcbiAgICAgIGh0bWxMaW5rXG4gICAgICBjb2xvcklkXG4gICAgICBjcmVhdG9yXG4gICAgICBvcmdhbml6ZXJcbiAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICBoYW5nb3V0TGlua1xuICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICBsb2NrZWRcbiAgICAgIHNvdXJjZVxuICAgICAgZXZlbnRUeXBlXG4gICAgICBwcml2YXRlQ29weVxuICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgY2FsZW5kYXJJZFxuICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZVxuICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZVxuICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgICBpc01lZXRpbmdcbiAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICBpc0JyZWFrXG4gICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgcHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgIGNvcHlJc0JyZWFrXG4gICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVyc1xuICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgaGFyZERlYWRsaW5lXG4gICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgZHVyYXRpb25cbiAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgIG1ldGhvZFxuICAgICAgdW5saW5rXG4gICAgICBjb3B5Q29sb3JcbiAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICBieVdlZWtEYXlcbiAgICAgIGxvY2FsU3luY2VkXG4gICAgICB0aXRsZVxuICAgICAgdGltZUJsb2NraW5nXG4gICAgICBtZWV0aW5nSWRcbiAgICAgIGV2ZW50SWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=