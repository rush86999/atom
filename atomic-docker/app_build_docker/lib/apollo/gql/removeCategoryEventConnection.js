"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation RemoveCategoryEventConnection(
    $categoryId: uuid!
    $eventId: String!
  ) {
    delete_Category_Event(
      where: { categoryId: { _eq: $categoryId }, eventId: { _eq: $eventId } }
    ) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVtb3ZlQ2F0ZWdvcnlFdmVudENvbm5lY3Rpb24uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZW1vdmVDYXRlZ29yeUV2ZW50Q29ubmVjdGlvbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FvQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gUmVtb3ZlQ2F0ZWdvcnlFdmVudENvbm5lY3Rpb24oXG4gICAgJGNhdGVnb3J5SWQ6IHV1aWQhXG4gICAgJGV2ZW50SWQ6IFN0cmluZyFcbiAgKSB7XG4gICAgZGVsZXRlX0NhdGVnb3J5X0V2ZW50KFxuICAgICAgd2hlcmU6IHsgY2F0ZWdvcnlJZDogeyBfZXE6ICRjYXRlZ29yeUlkIH0sIGV2ZW50SWQ6IHsgX2VxOiAkZXZlbnRJZCB9IH1cbiAgICApIHtcbiAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgIHJldHVybmluZyB7XG4gICAgICAgIGlkXG4gICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBldmVudElkXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=