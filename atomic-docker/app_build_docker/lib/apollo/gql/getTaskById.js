"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetTaskById($id: uuid!) {
    Task_by_pk(id: $id) {
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
      updatedAt
      userId
      type
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0VGFza0J5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRUYXNrQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXNCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBHZXRUYXNrQnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgVGFza19ieV9wayhpZDogJGlkKSB7XG4gICAgICBjb21wbGV0ZWREYXRlXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZHVyYXRpb25cbiAgICAgIGV2ZW50SWRcbiAgICAgIGhhcmREZWFkbGluZVxuICAgICAgaWRcbiAgICAgIGltcG9ydGFudFxuICAgICAgbm90ZXNcbiAgICAgIG9yZGVyXG4gICAgICBwYXJlbnRJZFxuICAgICAgcHJpb3JpdHlcbiAgICAgIHNvZnREZWFkbGluZVxuICAgICAgc3RhdHVzXG4gICAgICBzeW5jRGF0YVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIHR5cGVcbiAgICB9XG4gIH1cbmA7XG4iXX0=