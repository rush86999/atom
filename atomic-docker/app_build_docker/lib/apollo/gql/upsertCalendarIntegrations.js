"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertCalendar_Integration(
    $calendar_integrations: [Calendar_Integration_insert_input!]!
  ) {
    insert_Calendar_Integration(
      objects: $calendar_integrations
      on_conflict: {
        constraint: Calendar_Integration_pkey
        update_columns: [
          token
          refreshToken
          resource
          name
          enabled
          syncEnabled
          expiresAt
          pageToken
          syncToken
          appId
          appEmail
          appAccountId
          contactName
          contactEmail
          deleted
          updatedAt
          clientType
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0Q2FsZW5kYXJJbnRlZ3JhdGlvbnMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRDYWxlbmRhckludGVncmF0aW9ucy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWtDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRDYWxlbmRhcl9JbnRlZ3JhdGlvbihcbiAgICAkY2FsZW5kYXJfaW50ZWdyYXRpb25zOiBbQ2FsZW5kYXJfSW50ZWdyYXRpb25faW5zZXJ0X2lucHV0IV0hXG4gICkge1xuICAgIGluc2VydF9DYWxlbmRhcl9JbnRlZ3JhdGlvbihcbiAgICAgIG9iamVjdHM6ICRjYWxlbmRhcl9pbnRlZ3JhdGlvbnNcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IENhbGVuZGFyX0ludGVncmF0aW9uX3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICB0b2tlblxuICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIGVuYWJsZWRcbiAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgIGFwcElkXG4gICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICBjb250YWN0TmFtZVxuICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgIF1cbiAgICAgIH1cbiAgICApIHtcbiAgICAgIHJldHVybmluZyB7XG4gICAgICAgIGlkXG4gICAgICB9XG4gICAgfVxuICB9XG5gO1xuIl19