"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateCalendarsDropGlobalPrimary($ids: [String!]!) {
    update_Calendar(
      where: { id: { _in: $ids } }
      _set: { globalPrimary: false }
    ) {
      affected_rows
      returning {
        accessLevel
        account
        backgroundColor
        colorId
        createdDate
        defaultReminders
        deleted
        foregroundColor
        globalPrimary
        id
        modifiable
        pageToken
        primary
        resource
        syncToken
        title
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlQ2FsZW5kYXJzRHJvcEdsb2JhbFByaW1hcnkuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cGRhdGVDYWxlbmRhcnNEcm9wR2xvYmFsUHJpbWFyeS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0E2QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlQ2FsZW5kYXJzRHJvcEdsb2JhbFByaW1hcnkoJGlkczogW1N0cmluZyFdISkge1xuICAgIHVwZGF0ZV9DYWxlbmRhcihcbiAgICAgIHdoZXJlOiB7IGlkOiB7IF9pbjogJGlkcyB9IH1cbiAgICAgIF9zZXQ6IHsgZ2xvYmFsUHJpbWFyeTogZmFsc2UgfVxuICAgICkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgYWNjb3VudFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgY29sb3JJZFxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgICAgaWRcbiAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgcHJpbWFyeVxuICAgICAgICByZXNvdXJjZVxuICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgdGl0bGVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==