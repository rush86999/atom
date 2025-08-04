"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertCustomerOne($customer: Customer_insert_input!) {
    insert_Customer_one(object: $customer) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0Q3VzdG9tZXJPbmUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbnNlcnRDdXN0b21lck9uZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Q0FjakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRDdXN0b21lck9uZSgkY3VzdG9tZXI6IEN1c3RvbWVyX2luc2VydF9pbnB1dCEpIHtcbiAgICBpbnNlcnRfQ3VzdG9tZXJfb25lKG9iamVjdDogJGN1c3RvbWVyKSB7XG4gICAgICBhZGRyZXNzXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGVzY3JpcHRpb25cbiAgICAgIGVtYWlsXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgcGhvbmVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19