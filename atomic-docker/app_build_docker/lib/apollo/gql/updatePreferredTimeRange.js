"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdatePreferredTimeRange(
    $id: uuid!
    $dayOfWeek: Int
    $endTime: time!
    $startTime: time!
  ) {
    update_PreferredTimeRange_by_pk(
      pk_columns: { id: $id }
      _set: { dayOfWeek: $dayOfWeek, endTime: $endTime, startTime: $startTime }
    ) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlUHJlZmVycmVkVGltZVJhbmdlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXBkYXRlUHJlZmVycmVkVGltZVJhbmdlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FxQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlUHJlZmVycmVkVGltZVJhbmdlKFxuICAgICRpZDogdXVpZCFcbiAgICAkZGF5T2ZXZWVrOiBJbnRcbiAgICAkZW5kVGltZTogdGltZSFcbiAgICAkc3RhcnRUaW1lOiB0aW1lIVxuICApIHtcbiAgICB1cGRhdGVfUHJlZmVycmVkVGltZVJhbmdlX2J5X3BrKFxuICAgICAgcGtfY29sdW1uczogeyBpZDogJGlkIH1cbiAgICAgIF9zZXQ6IHsgZGF5T2ZXZWVrOiAkZGF5T2ZXZWVrLCBlbmRUaW1lOiAkZW5kVGltZSwgc3RhcnRUaW1lOiAkc3RhcnRUaW1lIH1cbiAgICApIHtcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkYXlPZldlZWtcbiAgICAgIGVuZFRpbWVcbiAgICAgIGV2ZW50SWRcbiAgICAgIGlkXG4gICAgICBzdGFydFRpbWVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19