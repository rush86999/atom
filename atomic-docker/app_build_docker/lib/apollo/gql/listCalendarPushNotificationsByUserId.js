"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListCalendarPushNotificationsByUserId($userId: uuid!) {
    Calendar_Push_Notification(where: { userId: { _eq: $userId } }) {
      calendarId
      createdDate
      expiration
      id
      resourceId
      resourceUri
      token
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbnNCeVVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RDYWxlbmRhclB1c2hOb3RpZmljYXRpb25zQnlVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7O0NBY2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgTGlzdENhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbnNCeVVzZXJJZCgkdXNlcklkOiB1dWlkISkge1xuICAgIENhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uKHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9KSB7XG4gICAgICBjYWxlbmRhcklkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZXhwaXJhdGlvblxuICAgICAgaWRcbiAgICAgIHJlc291cmNlSWRcbiAgICAgIHJlc291cmNlVXJpXG4gICAgICB0b2tlblxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=