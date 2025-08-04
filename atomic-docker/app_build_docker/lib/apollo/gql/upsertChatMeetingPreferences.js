"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydENoYXRNZWV0aW5nUHJlZmVyZW5jZXMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FpRGpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlKFxuICAgICRjaGF0TWVldGluZ1ByZWZlcmVuY2U6IENoYXRfTWVldGluZ19QcmVmZXJlbmNlX2luc2VydF9pbnB1dCFcbiAgKSB7XG4gICAgaW5zZXJ0X0NoYXRfTWVldGluZ19QcmVmZXJlbmNlX29uZShcbiAgICAgIG9iamVjdDogJGNoYXRNZWV0aW5nUHJlZmVyZW5jZVxuICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgY29uc3RyYWludDogQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2VfcGtleVxuICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICBidWZmZXJUaW1lXG4gICAgICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgIHJlbWluZGVyc1xuICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICBdXG4gICAgICB9XG4gICAgKSB7XG4gICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICBidWZmZXJUaW1lXG4gICAgICBjb25mZXJlbmNlQXBwXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZHVyYXRpb25cbiAgICAgIGVuYWJsZUNvbmZlcmVuY2VcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICBwcmltYXJ5RW1haWxcbiAgICAgIHJlbWluZGVyc1xuICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgIHRpbWV6b25lXG4gICAgICB0cmFuc3BhcmVuY3lcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgdXNlcklkXG4gICAgICB2aXNpYmlsaXR5XG4gICAgfVxuICB9XG5gO1xuIl19