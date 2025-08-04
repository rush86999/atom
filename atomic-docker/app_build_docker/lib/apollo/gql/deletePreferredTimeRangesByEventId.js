"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeletePreferredTimeRangesGivenEvent($eventId: String!) {
    delete_PreferredTimeRange(where: { eventId: { _eq: $eventId } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7OztDQU1qQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIERlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50KCRldmVudElkOiBTdHJpbmchKSB7XG4gICAgZGVsZXRlX1ByZWZlcnJlZFRpbWVSYW5nZSh3aGVyZTogeyBldmVudElkOiB7IF9lcTogJGV2ZW50SWQgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgfVxuICB9XG5gO1xuIl19