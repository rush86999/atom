"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteTasksByIds($taskIds: [uuid!]!) {
    delete_Task(where: { id: { _in: $taskIds } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlVGFza3NCeUlkcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZVRhc2tzQnlJZHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7OztDQU1qQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIERlbGV0ZVRhc2tzQnlJZHMoJHRhc2tJZHM6IFt1dWlkIV0hKSB7XG4gICAgZGVsZXRlX1Rhc2sod2hlcmU6IHsgaWQ6IHsgX2luOiAkdGFza0lkcyB9IH0pIHtcbiAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICB9XG4gIH1cbmA7XG4iXX0=