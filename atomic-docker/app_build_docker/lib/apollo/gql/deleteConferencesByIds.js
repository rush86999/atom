"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation deleteConferences($ids: [String!]!) {
    delete_Conference(where: { id: { _in: $ids } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ29uZmVyZW5jZXNCeUlkcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZUNvbmZlcmVuY2VzQnlJZHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7OztDQU1qQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIGRlbGV0ZUNvbmZlcmVuY2VzKCRpZHM6IFtTdHJpbmchXSEpIHtcbiAgICBkZWxldGVfQ29uZmVyZW5jZSh3aGVyZTogeyBpZDogeyBfaW46ICRpZHMgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgfVxuICB9XG5gO1xuIl19