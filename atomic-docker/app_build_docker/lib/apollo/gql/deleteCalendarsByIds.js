"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteCalendarsByIds($ids: [String!]!) {
    delete_Calendar(where: { id: { _in: $ids } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ2FsZW5kYXJzQnlJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVDYWxlbmRhcnNCeUlkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7O0NBTWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gRGVsZXRlQ2FsZW5kYXJzQnlJZHMoJGlkczogW1N0cmluZyFdISkge1xuICAgIGRlbGV0ZV9DYWxlbmRhcih3aGVyZTogeyBpZDogeyBfaW46ICRpZHMgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgfVxuICB9XG5gO1xuIl19