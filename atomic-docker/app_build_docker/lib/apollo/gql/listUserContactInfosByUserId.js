"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListUserContactInfoByUserId($userId: uuid!) {
    User_Contact_Info(where: { userId: { _eq: $userId } }) {
      createdDate
      id
      name
      primary
      type
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFVzZXJDb250YWN0SW5mb3NCeVVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RVc2VyQ29udGFjdEluZm9zQnlVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7OztDQVlqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IExpc3RVc2VyQ29udGFjdEluZm9CeVVzZXJJZCgkdXNlcklkOiB1dWlkISkge1xuICAgIFVzZXJfQ29udGFjdF9JbmZvKHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9KSB7XG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIHByaW1hcnlcbiAgICAgIHR5cGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19