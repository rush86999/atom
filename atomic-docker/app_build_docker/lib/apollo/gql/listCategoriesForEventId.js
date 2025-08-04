"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query listCategoriesForEventId($eventId: String!) {
    Category(where: { Category_Events: { eventId: { _eq: $eventId } } }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhdGVnb3JpZXNGb3JFdmVudElkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdENhdGVnb3JpZXNGb3JFdmVudElkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWdDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50SWQoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICBDYXRlZ29yeSh3aGVyZTogeyBDYXRlZ29yeV9FdmVudHM6IHsgZXZlbnRJZDogeyBfZXE6ICRldmVudElkIH0gfSB9KSB7XG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgZGVsZXRlZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICBkZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgIGNvcHlJc0JyZWFrXG4gICAgICBkZWZhdWx0SXNCcmVha1xuICAgICAgY29sb3JcbiAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgZGVmYXVsdElzTWVldGluZ1xuICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgIGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgfVxuICB9XG5gO1xuIl19