"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertPreferredTimeRanges(
    $preferredTimeRanges: [PreferredTimeRange_insert_input!]!
  ) {
    insert_PreferredTimeRange(objects: $preferredTimeRanges) {
      affected_rows
      returning {
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
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImluc2VydFByZWZlcnJlZFRpbWVSYW5nZXMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWtCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzKFxuICAgICRwcmVmZXJyZWRUaW1lUmFuZ2VzOiBbUHJlZmVycmVkVGltZVJhbmdlX2luc2VydF9pbnB1dCFdIVxuICApIHtcbiAgICBpbnNlcnRfUHJlZmVycmVkVGltZVJhbmdlKG9iamVjdHM6ICRwcmVmZXJyZWRUaW1lUmFuZ2VzKSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkYXlPZldlZWtcbiAgICAgICAgZW5kVGltZVxuICAgICAgICBldmVudElkXG4gICAgICAgIGlkXG4gICAgICAgIHN0YXJ0VGltZVxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICB9XG4gICAgfVxuICB9XG5gO1xuIl19