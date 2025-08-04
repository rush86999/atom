"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListCategoriesForUser($userId: uuid!) {
    Category(where: { userId: { _eq: $userId } }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhdGVnb3JpZXNGb3JVc2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdENhdGVnb3JpZXNGb3JVc2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWdDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBMaXN0Q2F0ZWdvcmllc0ZvclVzZXIoJHVzZXJJZDogdXVpZCEpIHtcbiAgICBDYXRlZ29yeSh3aGVyZTogeyB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfSkge1xuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgIGRlZmF1bHRUaW1lQmxvY2tpbmdcbiAgICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZVxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICBjb3B5SXNCcmVha1xuICAgICAgZGVmYXVsdElzQnJlYWtcbiAgICAgIGNvbG9yXG4gICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIGRlZmF1bHRJc01lZXRpbmdcbiAgICAgIGRlZmF1bHRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==