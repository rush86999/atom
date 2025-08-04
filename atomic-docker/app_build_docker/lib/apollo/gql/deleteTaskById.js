"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteTaskById($id: uuid!) {
    delete_Task_by_pk(id: $id) {
      completedDate
      createdDate
      duration
      eventId
      hardDeadline
      id
      important
      notes
      order
      parentId
      priority
      softDeadline
      status
      syncData
      type
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlVGFza0J5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVUYXNrQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXNCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVUYXNrQnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgZGVsZXRlX1Rhc2tfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgY29tcGxldGVkRGF0ZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGR1cmF0aW9uXG4gICAgICBldmVudElkXG4gICAgICBoYXJkRGVhZGxpbmVcbiAgICAgIGlkXG4gICAgICBpbXBvcnRhbnRcbiAgICAgIG5vdGVzXG4gICAgICBvcmRlclxuICAgICAgcGFyZW50SWRcbiAgICAgIHByaW9yaXR5XG4gICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgIHN0YXR1c1xuICAgICAgc3luY0RhdGFcbiAgICAgIHR5cGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19