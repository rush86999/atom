"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCustomerByUserId($userId: uuid!) {
    Customer(where: { userId: { _eq: $userId } }) {
      address
      createdDate
      description
      email
      id
      name
      phone
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q3VzdG9tZXJCeVVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdldEN1c3RvbWVyQnlVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7O0NBY2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgR2V0Q3VzdG9tZXJCeVVzZXJJZCgkdXNlcklkOiB1dWlkISkge1xuICAgIEN1c3RvbWVyKHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9KSB7XG4gICAgICBhZGRyZXNzXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGVzY3JpcHRpb25cbiAgICAgIGVtYWlsXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgcGhvbmVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19