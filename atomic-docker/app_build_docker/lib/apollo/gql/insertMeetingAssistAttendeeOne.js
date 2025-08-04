"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertMeetingAssistAttendee(
    $attendee: Meeting_Assist_Attendee_insert_input!
  ) {
    insert_Meeting_Assist_Attendee_one(object: $attendee) {
      createdDate
      contactId
      emails
      externalAttendee
      hostId
      id
      imAddresses
      meetingId
      name
      phoneNumbers
      primaryEmail
      timezone
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlT25lLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlT25lLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FxQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gSW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlKFxuICAgICRhdHRlbmRlZTogTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfaW5zZXJ0X2lucHV0IVxuICApIHtcbiAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfb25lKG9iamVjdDogJGF0dGVuZGVlKSB7XG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgY29udGFjdElkXG4gICAgICBlbWFpbHNcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgIGhvc3RJZFxuICAgICAgaWRcbiAgICAgIGltQWRkcmVzc2VzXG4gICAgICBtZWV0aW5nSWRcbiAgICAgIG5hbWVcbiAgICAgIHBob25lTnVtYmVyc1xuICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICB0aW1lem9uZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=