"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteCalendarPushNotificationByCalendarId($calendarId: String!) {
    delete_Calendar_Push_Notification(
      where: { calendarId: { _eq: $calendarId } }
    ) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGVsZXRlQ2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7OztDQVFqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIERlbGV0ZUNhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5Q2FsZW5kYXJJZCgkY2FsZW5kYXJJZDogU3RyaW5nISkge1xuICAgIGRlbGV0ZV9DYWxlbmRhcl9QdXNoX05vdGlmaWNhdGlvbihcbiAgICAgIHdoZXJlOiB7IGNhbGVuZGFySWQ6IHsgX2VxOiAkY2FsZW5kYXJJZCB9IH1cbiAgICApIHtcbiAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICB9XG4gIH1cbmA7XG4iXX0=