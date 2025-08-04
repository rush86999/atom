"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateUserForUserPreference($id: uuid!, $userPreferenceId: uuid) {
    update_User_by_pk(
      pk_columns: { id: $id }
      _set: { userPreferenceId: $userPreferenceId }
    ) {
      createdDate
      deleted
      email
      id
      name
      updatedAt
      userPreferenceId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlVXNlckZvclVzZXJQcmVmZXJlbmNlSWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cGRhdGVVc2VyRm9yVXNlclByZWZlcmVuY2VJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7O0NBZWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlVXNlckZvclVzZXJQcmVmZXJlbmNlKCRpZDogdXVpZCEsICR1c2VyUHJlZmVyZW5jZUlkOiB1dWlkKSB7XG4gICAgdXBkYXRlX1VzZXJfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyB1c2VyUHJlZmVyZW5jZUlkOiAkdXNlclByZWZlcmVuY2VJZCB9XG4gICAgKSB7XG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGVsZXRlZFxuICAgICAgZW1haWxcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJQcmVmZXJlbmNlSWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=