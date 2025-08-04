"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteCategoryById($id: uuid!) {
    delete_Category_by_pk(id: $id) {
      id
      name
      deleted
      createdDate
      updatedAt
      userId
      copyAvailability
      copyTimeBlocking
      copyTimePreference
      copyReminders
      copyPriorityLevel
      copyModifiable
      defaultAvailability
      defaultTimeBlocking
      defaultTimePreference
      defaultReminders
      defaultPriorityLevel
      defaultModifiable
      copyIsBreak
      defaultIsBreak
      color
      copyIsMeeting
      copyIsExternalMeeting
      defaultIsMeeting
      defaultIsExternalMeeting
      defaultMeetingModifiable
      defaultExternalMeetingModifiable
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ2F0ZWdvcnlCeUlkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGVsZXRlQ2F0ZWdvcnlCeUlkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWdDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVDYXRlZ29yeUJ5SWQoJGlkOiB1dWlkISkge1xuICAgIGRlbGV0ZV9DYXRlZ29yeV9ieV9wayhpZDogJGlkKSB7XG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgZGVsZXRlZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICBkZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgIGNvcHlJc0JyZWFrXG4gICAgICBkZWZhdWx0SXNCcmVha1xuICAgICAgY29sb3JcbiAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgZGVmYXVsdElzTWVldGluZ1xuICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgIGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgfVxuICB9XG5gO1xuIl19