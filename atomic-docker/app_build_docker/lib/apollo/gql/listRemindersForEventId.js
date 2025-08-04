"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query listRemindersForEventId($eventId: String!) {
    Reminder(where: { eventId: { _eq: $eventId } }) {
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
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFJlbWluZGVyc0ZvckV2ZW50SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0UmVtaW5kZXJzRm9yRXZlbnRJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7OztDQWdCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBsaXN0UmVtaW5kZXJzRm9yRXZlbnRJZCgkZXZlbnRJZDogU3RyaW5nISkge1xuICAgIFJlbWluZGVyKHdoZXJlOiB7IGV2ZW50SWQ6IHsgX2VxOiAkZXZlbnRJZCB9IH0pIHtcbiAgICAgIGlkXG4gICAgICByZW1pbmRlckRhdGVcbiAgICAgIGV2ZW50SWRcbiAgICAgIHRpbWV6b25lXG4gICAgICBtZXRob2RcbiAgICAgIG1pbnV0ZXNcbiAgICAgIHVzZURlZmF1bHRcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==