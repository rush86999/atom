"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  subscription OnCategoryEventConnectionAdded(
    $userId: uuid!
    $createdDate: timestamptz!
  ) {
    Category_Event(
      where: { userId: { _eq: $userId }, createdDate: { _gt: $createdDate } }
      order_by: { createdDate: desc }
    ) {
      categoryId
      createdDate
      deleted
      eventId
      id
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3Vic2NyaWJlQ2F0ZWdvcnlFdmVudEFkZGVkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3Vic2NyaWJlQ2F0ZWdvcnlFdmVudEFkZGVkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FrQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgc3Vic2NyaXB0aW9uIE9uQ2F0ZWdvcnlFdmVudENvbm5lY3Rpb25BZGRlZChcbiAgICAkdXNlcklkOiB1dWlkIVxuICAgICRjcmVhdGVkRGF0ZTogdGltZXN0YW1wdHohXG4gICkge1xuICAgIENhdGVnb3J5X0V2ZW50KFxuICAgICAgd2hlcmU6IHsgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9LCBjcmVhdGVkRGF0ZTogeyBfZ3Q6ICRjcmVhdGVkRGF0ZSB9IH1cbiAgICAgIG9yZGVyX2J5OiB7IGNyZWF0ZWREYXRlOiBkZXNjIH1cbiAgICApIHtcbiAgICAgIGNhdGVnb3J5SWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkZWxldGVkXG4gICAgICBldmVudElkXG4gICAgICBpZFxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=