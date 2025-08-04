"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteCalendarPushNotificationById($id: String!) {
    delete_Calendar_Push_Notification_by_pk(id: $id) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZUNhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7O0NBY2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gRGVsZXRlQ2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlJZCgkaWQ6IFN0cmluZyEpIHtcbiAgICBkZWxldGVfQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb25fYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgY2FsZW5kYXJJZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGV4cGlyYXRpb25cbiAgICAgIGlkXG4gICAgICByZXNvdXJjZUlkXG4gICAgICByZXNvdXJjZVVyaVxuICAgICAgdG9rZW5cbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19