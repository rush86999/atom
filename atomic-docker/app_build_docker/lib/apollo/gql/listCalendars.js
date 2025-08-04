"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListCalendars($userId: uuid!) {
    Calendar(where: { userId: { _eq: $userId } }) {
      id
      title
      colorId
      account
      accessLevel
      modifiable
      resource
      defaultReminders
      globalPrimary
      deleted
      createdDate
      updatedAt
      userId
      foregroundColor
      backgroundColor
      pageToken
      syncToken
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhbGVuZGFycy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RDYWxlbmRhcnMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FzQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgTGlzdENhbGVuZGFycygkdXNlcklkOiB1dWlkISkge1xuICAgIENhbGVuZGFyKHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9KSB7XG4gICAgICBpZFxuICAgICAgdGl0bGVcbiAgICAgIGNvbG9ySWRcbiAgICAgIGFjY291bnRcbiAgICAgIGFjY2Vzc0xldmVsXG4gICAgICBtb2RpZmlhYmxlXG4gICAgICByZXNvdXJjZVxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgZGVsZXRlZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgcGFnZVRva2VuXG4gICAgICBzeW5jVG9rZW5cbiAgICB9XG4gIH1cbmA7XG4iXX0=