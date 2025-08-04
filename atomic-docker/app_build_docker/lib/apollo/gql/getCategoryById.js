"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCategoryById($id: uuid!) {
    Category_by_pk(id: $id) {
      color
      copyAvailability
      copyIsBreak
      copyIsExternalMeeting
      copyIsMeeting
      copyModifiable
      copyPriorityLevel
      copyReminders
      copyTimeBlocking
      copyTimePreference
      createdDate
      defaultAvailability
      defaultExternalMeetingModifiable
      defaultIsBreak
      defaultIsExternalMeeting
      defaultIsMeeting
      defaultMeetingModifiable
      defaultModifiable
      defaultPriorityLevel
      defaultReminders
      defaultTimeBlocking
      defaultTimePreference
      deleted
      id
      name
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2F0ZWdvcnlCeUlkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0Q2F0ZWdvcnlCeUlkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWdDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBHZXRDYXRlZ29yeUJ5SWQoJGlkOiB1dWlkISkge1xuICAgIENhdGVnb3J5X2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgIGNvbG9yXG4gICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICBjb3B5SXNCcmVha1xuICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgIGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICBkZWZhdWx0SXNCcmVha1xuICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBkZWZhdWx0SXNNZWV0aW5nXG4gICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICBkZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICBkZWxldGVkXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=