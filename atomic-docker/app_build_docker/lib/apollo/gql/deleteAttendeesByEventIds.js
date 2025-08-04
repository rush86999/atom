"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteAttendees($eventIds: [String!]!) {
    delete_Attendee(where: { eventId: { _in: $eventIds } }) {
      returning {
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
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQXR0ZW5kZWVzQnlFdmVudElkcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZUF0dGVuZGVlc0J5RXZlbnRJZHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXdCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVBdHRlbmRlZXMoJGV2ZW50SWRzOiBbU3RyaW5nIV0hKSB7XG4gICAgZGVsZXRlX0F0dGVuZGVlKHdoZXJlOiB7IGV2ZW50SWQ6IHsgX2luOiAkZXZlbnRJZHMgfSB9KSB7XG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzXG4gICAgICAgIGNvbW1lbnRcbiAgICAgICAgY29udGFjdElkXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZW1haWxzXG4gICAgICAgIGV2ZW50SWRcbiAgICAgICAgaWRcbiAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgbmFtZVxuICAgICAgICBvcHRpb25hbFxuICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgcmVzcG9uc2VTdGF0dXNcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgIH1cbiAgfVxuYDtcbiJdfQ==