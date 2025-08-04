"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateCalendarToGlobalPrimary($id: String!) {
    update_Calendar_by_pk(
      pk_columns: { id: $id }
      _set: { globalPrimary: true }
    ) {
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
      resource
      title
      updatedAt
      userId
      pageToken
      syncToken
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlQ2FsZW5kYXJUb0dsb2JhbFByaW1hcnkuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXlCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBVcGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSgkaWQ6IFN0cmluZyEpIHtcbiAgICB1cGRhdGVfQ2FsZW5kYXJfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyBnbG9iYWxQcmltYXJ5OiB0cnVlIH1cbiAgICApIHtcbiAgICAgIGFjY2Vzc0xldmVsXG4gICAgICBhY2NvdW50XG4gICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgIGNvbG9ySWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICBkZWxldGVkXG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgIGlkXG4gICAgICBtb2RpZmlhYmxlXG4gICAgICByZXNvdXJjZVxuICAgICAgdGl0bGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgICBwYWdlVG9rZW5cbiAgICAgIHN5bmNUb2tlblxuICAgIH1cbiAgfVxuYDtcbiJdfQ==