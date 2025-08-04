"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertMeetingAssistPreferredTimeRanges(
    $meetingAssistPreferredTimeRanges: [Meeting_Assist_Preferred_Time_Range_insert_input!]!
  ) {
    insert_Meeting_Assist_Preferred_Time_Range(
      objects: $meetingAssistPreferredTimeRanges
    ) {
      affected_rows
      returning {
        attendeeId
        createdDate
        dayOfWeek
        endTime
        hostId
        id
        meetingId
        startTime
        updatedAt
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNNdXRhdGlvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImluc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzTXV0YXRpb24udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlcyhcbiAgICAkbWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXM6IFtNZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZV9pbnNlcnRfaW5wdXQhXSFcbiAgKSB7XG4gICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlKFxuICAgICAgb2JqZWN0czogJG1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzXG4gICAgKSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBhdHRlbmRlZUlkXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRheU9mV2Vla1xuICAgICAgICBlbmRUaW1lXG4gICAgICAgIGhvc3RJZFxuICAgICAgICBpZFxuICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgc3RhcnRUaW1lXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==