"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateUserNameById($id: uuid!, $name: String!) {
    update_User_by_pk(pk_columns: { id: $id }, _set: { name: $name }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlVXNlckZvck5hbWUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cGRhdGVVc2VyRm9yTmFtZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7O0NBWWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlVXNlck5hbWVCeUlkKCRpZDogdXVpZCEsICRuYW1lOiBTdHJpbmchKSB7XG4gICAgdXBkYXRlX1VzZXJfYnlfcGsocGtfY29sdW1uczogeyBpZDogJGlkIH0sIF9zZXQ6IHsgbmFtZTogJG5hbWUgfSkge1xuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGVtYWlsXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VyUHJlZmVyZW5jZUlkXG4gICAgfVxuICB9XG5gO1xuIl19