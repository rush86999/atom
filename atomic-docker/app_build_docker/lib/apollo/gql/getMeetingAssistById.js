"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetMeetingAssistById($id: uuid!) {
    Meeting_Assist_by_pk(id: $id) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0TWVldGluZ0Fzc2lzdEJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRNZWV0aW5nQXNzaXN0QnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBbURqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IEdldE1lZXRpbmdBc3Npc3RCeUlkKCRpZDogdXVpZCEpIHtcbiAgICBNZWV0aW5nX0Fzc2lzdF9ieV9wayhpZDogJGlkKSB7XG4gICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgIGF0dGVuZGVlQ2FuTW9kaWZ5XG4gICAgICBhdHRlbmRlZUNvdW50XG4gICAgICBhdHRlbmRlZVJlc3BvbmRlZENvdW50XG4gICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgIGJ1ZmZlclRpbWVcbiAgICAgIGNhbGVuZGFySWRcbiAgICAgIGNhbmNlbElmQW55UmVmdXNlXG4gICAgICBjYW5jZWxsZWRcbiAgICAgIGNvbG9ySWRcbiAgICAgIGNvbmZlcmVuY2VBcHBcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkdXJhdGlvblxuICAgICAgZW5hYmxlQXR0ZW5kZWVQcmVmZXJlbmNlc1xuICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgZW5hYmxlSG9zdFByZWZlcmVuY2VzXG4gICAgICBlbmREYXRlXG4gICAgICBldmVudElkXG4gICAgICBleHBpcmVEYXRlXG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIGZyZXF1ZW5jeVxuICAgICAgZ3VhcmFudGVlQXZhaWxhYmlsaXR5XG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICBpZFxuICAgICAgaW50ZXJ2YWxcbiAgICAgIGxvY2F0aW9uXG4gICAgICBtaW5UaHJlc2hvbGRDb3VudFxuICAgICAgbm90ZXNcbiAgICAgIG9yaWdpbmFsTWVldGluZ0lkXG4gICAgICBwcmlvcml0eVxuICAgICAgcmVtaW5kZXJzXG4gICAgICBzZW5kVXBkYXRlc1xuICAgICAgc3RhcnREYXRlXG4gICAgICBzdW1tYXJ5XG4gICAgICB0aW1lem9uZVxuICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICB1bnRpbFxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICB1c2VySWRcbiAgICAgIHZpc2liaWxpdHlcbiAgICAgIHdpbmRvd0VuZERhdGVcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZVxuICAgICAgbG9ja0FmdGVyXG4gICAgfVxuICB9XG5gO1xuIl19