"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlTWVldGluZ0Fzc2lzdEJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVNZWV0aW5nQXNzaXN0QnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBbURqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIERlbGV0ZU1lZXRpbmdBc3Npc3RCeUlkKCRpZDogdXVpZCEpIHtcbiAgICBkZWxldGVfTWVldGluZ19Bc3Npc3RfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgYWxsb3dBdHRlbmRlZVVwZGF0ZVByZWZlcmVuY2VzXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgYXR0ZW5kZWVDb3VudFxuICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICBhdHRlbmRlZVJlc3BvbmRlZENvdW50XG4gICAgICBidWZmZXJUaW1lXG4gICAgICBjYWxlbmRhcklkXG4gICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgY2FuY2VsbGVkXG4gICAgICBjb2xvcklkXG4gICAgICBjb25mZXJlbmNlQXBwXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZHVyYXRpb25cbiAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgIGVuYWJsZUNvbmZlcmVuY2VcbiAgICAgIGVuYWJsZUhvc3RQcmVmZXJlbmNlc1xuICAgICAgZW5kRGF0ZVxuICAgICAgZXZlbnRJZFxuICAgICAgZXhwaXJlRGF0ZVxuICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICBmcmVxdWVuY3lcbiAgICAgIGd1YXJhbnRlZUF2YWlsYWJpbGl0eVxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgaWRcbiAgICAgIGludGVydmFsXG4gICAgICBsb2NhdGlvblxuICAgICAgbWluVGhyZXNob2xkQ291bnRcbiAgICAgIG5vdGVzXG4gICAgICBvcmlnaW5hbE1lZXRpbmdJZFxuICAgICAgcHJpb3JpdHlcbiAgICAgIHJlbWluZGVyc1xuICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgIHN0YXJ0RGF0ZVxuICAgICAgc3VtbWFyeVxuICAgICAgdGltZXpvbmVcbiAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgdW50aWxcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgdXNlcklkXG4gICAgICB2aXNpYmlsaXR5XG4gICAgICB3aW5kb3dFbmREYXRlXG4gICAgICB3aW5kb3dTdGFydERhdGVcbiAgICAgIGxvY2tBZnRlclxuICAgIH1cbiAgfVxuYDtcbiJdfQ==