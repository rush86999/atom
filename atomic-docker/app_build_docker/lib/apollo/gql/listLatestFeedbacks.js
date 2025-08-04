"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListLatestFeedbacks($userId: uuid!) {
    Feedback(
      where: { userId: { _eq: $userId } }
      order_by: { lastSeen: desc }
    ) {
      count
      createdDate
      deleted
      id
      lastSeen
      question1_A
      question1_B
      question1_C
      question2
      question3
      question4
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdExhdGVzdEZlZWRiYWNrcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RMYXRlc3RGZWVkYmFja3MudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBMaXN0TGF0ZXN0RmVlZGJhY2tzKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgRmVlZGJhY2soXG4gICAgICB3aGVyZTogeyB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfVxuICAgICAgb3JkZXJfYnk6IHsgbGFzdFNlZW46IGRlc2MgfVxuICAgICkge1xuICAgICAgY291bnRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkZWxldGVkXG4gICAgICBpZFxuICAgICAgbGFzdFNlZW5cbiAgICAgIHF1ZXN0aW9uMV9BXG4gICAgICBxdWVzdGlvbjFfQlxuICAgICAgcXVlc3Rpb24xX0NcbiAgICAgIHF1ZXN0aW9uMlxuICAgICAgcXVlc3Rpb24zXG4gICAgICBxdWVzdGlvbjRcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19