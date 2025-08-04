"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetAnyCalendar($userId: uuid!) {
    Calendar(
      where: {
        userId: { _eq: $userId }
        accessLevel: { _nin: ["reader", "freeBusyReader"] }
      }
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
      pageToken
      syncToken
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0QW55Q2FsZW5kYXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRBbnlDYWxlbmRhci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBMkJqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IEdldEFueUNhbGVuZGFyKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgQ2FsZW5kYXIoXG4gICAgICB3aGVyZToge1xuICAgICAgICB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH1cbiAgICAgICAgYWNjZXNzTGV2ZWw6IHsgX25pbjogW1wicmVhZGVyXCIsIFwiZnJlZUJ1c3lSZWFkZXJcIl0gfVxuICAgICAgfVxuICAgICkge1xuICAgICAgaWRcbiAgICAgIHRpdGxlXG4gICAgICBjb2xvcklkXG4gICAgICBhY2NvdW50XG4gICAgICBhY2Nlc3NMZXZlbFxuICAgICAgbW9kaWZpYWJsZVxuICAgICAgcmVzb3VyY2VcbiAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgIHBhZ2VUb2tlblxuICAgICAgc3luY1Rva2VuXG4gICAgfVxuICB9XG5gO1xuIl19