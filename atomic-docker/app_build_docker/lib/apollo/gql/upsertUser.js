"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertUser($user: User_insert_input!) {
    insert_User_one(
      object: $user
      on_conflict: {
        constraint: User_pkey
        update_columns: [email, name, deleted, updatedAt]
      }
    ) {
      id
      name
      email
      deleted
      createdDate
      updatedAt
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0VXNlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydFVzZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBaUJqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIEluc2VydFVzZXIoJHVzZXI6IFVzZXJfaW5zZXJ0X2lucHV0ISkge1xuICAgIGluc2VydF9Vc2VyX29uZShcbiAgICAgIG9iamVjdDogJHVzZXJcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IFVzZXJfcGtleVxuICAgICAgICB1cGRhdGVfY29sdW1uczogW2VtYWlsLCBuYW1lLCBkZWxldGVkLCB1cGRhdGVkQXRdXG4gICAgICB9XG4gICAgKSB7XG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgZW1haWxcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICB9XG4gIH1cbmA7XG4iXX0=