"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation insertPreferredTimeRange(
    $preferredTimeRange: PreferredTimeRange_insert_input!
  ) {
    insert_PreferredTimeRange_one(object: $preferredTimeRange) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Q0FlakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBpbnNlcnRQcmVmZXJyZWRUaW1lUmFuZ2UoXG4gICAgJHByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlX2luc2VydF9pbnB1dCFcbiAgKSB7XG4gICAgaW5zZXJ0X1ByZWZlcnJlZFRpbWVSYW5nZV9vbmUob2JqZWN0OiAkcHJlZmVycmVkVGltZVJhbmdlKSB7XG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGF5T2ZXZWVrXG4gICAgICBlbmRUaW1lXG4gICAgICBldmVudElkXG4gICAgICBpZFxuICAgICAgc3RhcnRUaW1lXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==