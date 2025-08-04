"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation deleteRemindersForEventId($eventId: String!) {
    delete_Reminder(where: { eventId: { _eq: $eventId } }) {
      affected_rows
      returning {
        id
        reminderDate
        eventId
        timezone
        method
        minutes
        useDefault
        deleted
        createdDate
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRlbGV0ZVJlbWluZGVyc0ZvckV2ZW50SWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FtQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRJZCgkZXZlbnRJZDogU3RyaW5nISkge1xuICAgIGRlbGV0ZV9SZW1pbmRlcih3aGVyZTogeyBldmVudElkOiB7IF9lcTogJGV2ZW50SWQgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBpZFxuICAgICAgICByZW1pbmRlckRhdGVcbiAgICAgICAgZXZlbnRJZFxuICAgICAgICB0aW1lem9uZVxuICAgICAgICBtZXRob2RcbiAgICAgICAgbWludXRlc1xuICAgICAgICB1c2VEZWZhdWx0XG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==