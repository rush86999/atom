"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertAttendee($attendee: Attendee_insert_input!) {
    insert_Attendee_one(object: $attendee) {
      additionalGuests
      comment
      contactId
      createdDate
      deleted
      emails
      eventId
      id
      imAddresses
      name
      optional
      phoneNumbers
      resource
      responseStatus
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0QXR0ZW5kZWVNdXRhdGlvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImluc2VydEF0dGVuZGVlTXV0YXRpb24udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRBdHRlbmRlZSgkYXR0ZW5kZWU6IEF0dGVuZGVlX2luc2VydF9pbnB1dCEpIHtcbiAgICBpbnNlcnRfQXR0ZW5kZWVfb25lKG9iamVjdDogJGF0dGVuZGVlKSB7XG4gICAgICBhZGRpdGlvbmFsR3Vlc3RzXG4gICAgICBjb21tZW50XG4gICAgICBjb250YWN0SWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkZWxldGVkXG4gICAgICBlbWFpbHNcbiAgICAgIGV2ZW50SWRcbiAgICAgIGlkXG4gICAgICBpbUFkZHJlc3Nlc1xuICAgICAgbmFtZVxuICAgICAgb3B0aW9uYWxcbiAgICAgIHBob25lTnVtYmVyc1xuICAgICAgcmVzb3VyY2VcbiAgICAgIHJlc3BvbnNlU3RhdHVzXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==