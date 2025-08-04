"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateUserPreferenceOnBoarding(
    $userId: uuid!
    $onBoarded: Boolean!
  ) {
    update_User_Preference(
      where: { userId: { _eq: $userId } }
      _set: { onBoarded: $onBoarded }
    ) {
      affected_rows
      returning {
        id
        onBoarded
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWRNdXRhdGlvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZVVzZXJQcmVmZXJlbmNlT25Cb2FyZGVkTXV0YXRpb24udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FnQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkaW5nKFxuICAgICR1c2VySWQ6IHV1aWQhXG4gICAgJG9uQm9hcmRlZDogQm9vbGVhbiFcbiAgKSB7XG4gICAgdXBkYXRlX1VzZXJfUHJlZmVyZW5jZShcbiAgICAgIHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9XG4gICAgICBfc2V0OiB7IG9uQm9hcmRlZDogJG9uQm9hcmRlZCB9XG4gICAgKSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBpZFxuICAgICAgICBvbkJvYXJkZWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=