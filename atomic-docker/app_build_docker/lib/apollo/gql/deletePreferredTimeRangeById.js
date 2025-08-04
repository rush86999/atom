"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeletePreferredTimeRangeById($id: uuid!) {
    delete_PreferredTimeRange_by_pk(id: $id) {
      createdDate
      dayOfWeek
      endTime
      eventId
      id
      startTime
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlQnlJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZUJ5SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Q0FhakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VCeUlkKCRpZDogdXVpZCEpIHtcbiAgICBkZWxldGVfUHJlZmVycmVkVGltZVJhbmdlX2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkYXlPZldlZWtcbiAgICAgIGVuZFRpbWVcbiAgICAgIGV2ZW50SWRcbiAgICAgIGlkXG4gICAgICBzdGFydFRpbWVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19