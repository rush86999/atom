"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation deleteReminders($userId: uuid!, $eventIds: [String!]!) {
    delete_Reminder(
      where: { userId: { _eq: $userId }, eventId: { _in: $eventIds } }
    ) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVSZW1pbmRlcnNGb3JFdmVudElkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Q0FRakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBkZWxldGVSZW1pbmRlcnMoJHVzZXJJZDogdXVpZCEsICRldmVudElkczogW1N0cmluZyFdISkge1xuICAgIGRlbGV0ZV9SZW1pbmRlcihcbiAgICAgIHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSwgZXZlbnRJZDogeyBfaW46ICRldmVudElkcyB9IH1cbiAgICApIHtcbiAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICB9XG4gIH1cbmA7XG4iXX0=