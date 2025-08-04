"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation RemoveEventConnectionsForCategory($categoryId: uuid!) {
    delete_Category_Event(where: { categoryId: { _eq: $categoryId } }) {
      affected_rows
      returning {
        id
        categoryId
        createdDate
        deleted
        eventId
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVtb3ZlRXZlbnRDb25uZWN0aW9uc0ZvckNhdGVnb3J5TXV0YXRpb24uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZW1vdmVFdmVudENvbm5lY3Rpb25zRm9yQ2F0ZWdvcnlNdXRhdGlvbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7O0NBZWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gUmVtb3ZlRXZlbnRDb25uZWN0aW9uc0ZvckNhdGVnb3J5KCRjYXRlZ29yeUlkOiB1dWlkISkge1xuICAgIGRlbGV0ZV9DYXRlZ29yeV9FdmVudCh3aGVyZTogeyBjYXRlZ29yeUlkOiB7IF9lcTogJGNhdGVnb3J5SWQgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBpZFxuICAgICAgICBjYXRlZ29yeUlkXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZXZlbnRJZFxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICB9XG4gICAgfVxuICB9XG5gO1xuIl19