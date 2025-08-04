"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCalendarPushNotificationByCalendarId($calendarId: String!) {
    Calendar_Push_Notification(
      where: { calendarId: { _eq: $calendarId } }
      limit: 1
    ) {
      calendarId
      createdDate
      expiration
      id
      resourceId
      resourceUri
      token
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0Q2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7OztDQWlCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBHZXRDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUNhbGVuZGFySWQoJGNhbGVuZGFySWQ6IFN0cmluZyEpIHtcbiAgICBDYWxlbmRhcl9QdXNoX05vdGlmaWNhdGlvbihcbiAgICAgIHdoZXJlOiB7IGNhbGVuZGFySWQ6IHsgX2VxOiAkY2FsZW5kYXJJZCB9IH1cbiAgICAgIGxpbWl0OiAxXG4gICAgKSB7XG4gICAgICBjYWxlbmRhcklkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZXhwaXJhdGlvblxuICAgICAgaWRcbiAgICAgIHJlc291cmNlSWRcbiAgICAgIHJlc291cmNlVXJpXG4gICAgICB0b2tlblxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=