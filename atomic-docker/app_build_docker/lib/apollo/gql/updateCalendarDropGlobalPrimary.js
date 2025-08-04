"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateCalendarDropGlobalPrimary($id: String!) {
    update_Calendar_by_pk(
      pk_columns: { id: $id }
      _set: { globalPrimary: false }
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlQ2FsZW5kYXJEcm9wR2xvYmFsUHJpbWFyeS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZUNhbGVuZGFyRHJvcEdsb2JhbFByaW1hcnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F5QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlQ2FsZW5kYXJEcm9wR2xvYmFsUHJpbWFyeSgkaWQ6IFN0cmluZyEpIHtcbiAgICB1cGRhdGVfQ2FsZW5kYXJfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyBnbG9iYWxQcmltYXJ5OiBmYWxzZSB9XG4gICAgKSB7XG4gICAgICBhY2Nlc3NMZXZlbFxuICAgICAgYWNjb3VudFxuICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICBjb2xvcklkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZGVsZXRlZFxuICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICBnbG9iYWxQcmltYXJ5XG4gICAgICBpZFxuICAgICAgbW9kaWZpYWJsZVxuICAgICAgcmVzb3VyY2VcbiAgICAgIHRpdGxlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgcGFnZVRva2VuXG4gICAgICBzeW5jVG9rZW5cbiAgICB9XG4gIH1cbmA7XG4iXX0=