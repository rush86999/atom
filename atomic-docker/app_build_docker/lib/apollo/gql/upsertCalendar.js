"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertCalendar($calendar: Calendar_insert_input!) {
    insert_Calendar_one(
      object: $calendar
      on_conflict: {
        constraint: Calendar_pkey
        update_columns: [
          title
          colorId
          account
          accessLevel
          resource
          modifiable
          defaultReminders
          globalPrimary
          backgroundColor
          foregroundColor
          deleted
          updatedAt
          pageToken
          syncToken
        ]
      }
    ) {
      id
      accessLevel
      account
      backgroundColor
      colorId
      createdDate
      defaultReminders
      deleted
      globalPrimary
      foregroundColor
      modifiable
      resource
      title
      updatedAt
      userId
      pageToken
      syncToken
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0Q2FsZW5kYXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRDYWxlbmRhci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQTJDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBJbnNlcnRDYWxlbmRhcigkY2FsZW5kYXI6IENhbGVuZGFyX2luc2VydF9pbnB1dCEpIHtcbiAgICBpbnNlcnRfQ2FsZW5kYXJfb25lKFxuICAgICAgb2JqZWN0OiAkY2FsZW5kYXJcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IENhbGVuZGFyX3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICB0aXRsZVxuICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICBhY2NvdW50XG4gICAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgXVxuICAgICAgfVxuICAgICkge1xuICAgICAgaWRcbiAgICAgIGFjY2Vzc0xldmVsXG4gICAgICBhY2NvdW50XG4gICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgIGNvbG9ySWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICBkZWxldGVkXG4gICAgICBnbG9iYWxQcmltYXJ5XG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIG1vZGlmaWFibGVcbiAgICAgIHJlc291cmNlXG4gICAgICB0aXRsZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIHBhZ2VUb2tlblxuICAgICAgc3luY1Rva2VuXG4gICAgfVxuICB9XG5gO1xuIl19