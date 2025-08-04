"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query listAttendeesByEventId($eventId: String!) {
    Attendee(where: { eventId: { _eq: $eventId } }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdEF0dGVuZGVlc0J5RXZlbnRJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RBdHRlbmRlZXNCeUV2ZW50SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBsaXN0QXR0ZW5kZWVzQnlFdmVudElkKCRldmVudElkOiBTdHJpbmchKSB7XG4gICAgQXR0ZW5kZWUod2hlcmU6IHsgZXZlbnRJZDogeyBfZXE6ICRldmVudElkIH0gfSkge1xuICAgICAgYWRkaXRpb25hbEd1ZXN0c1xuICAgICAgY29tbWVudFxuICAgICAgY29udGFjdElkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGVsZXRlZFxuICAgICAgZW1haWxzXG4gICAgICBldmVudElkXG4gICAgICBpZFxuICAgICAgaW1BZGRyZXNzZXNcbiAgICAgIG5hbWVcbiAgICAgIG9wdGlvbmFsXG4gICAgICBwaG9uZU51bWJlcnNcbiAgICAgIHJlc291cmNlXG4gICAgICByZXNwb25zZVN0YXR1c1xuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=