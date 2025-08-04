"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetGlobalPrimaryCalendar($userId: uuid!) {
    Calendar(
      where: { userId: { _eq: $userId }, globalPrimary: { _eq: true } }
    ) {
      id
      title
      colorId
      account
      accessLevel
      modifiable
      resource
      defaultReminders
      globalPrimary
      deleted
      createdDate
      updatedAt
      userId
      foregroundColor
      backgroundColor
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBc0JqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IEdldEdsb2JhbFByaW1hcnlDYWxlbmRhcigkdXNlcklkOiB1dWlkISkge1xuICAgIENhbGVuZGFyKFxuICAgICAgd2hlcmU6IHsgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9LCBnbG9iYWxQcmltYXJ5OiB7IF9lcTogdHJ1ZSB9IH1cbiAgICApIHtcbiAgICAgIGlkXG4gICAgICB0aXRsZVxuICAgICAgY29sb3JJZFxuICAgICAgYWNjb3VudFxuICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgIG1vZGlmaWFibGVcbiAgICAgIHJlc291cmNlXG4gICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICBnbG9iYWxQcmltYXJ5XG4gICAgICBkZWxldGVkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgfVxuICB9XG5gO1xuIl19