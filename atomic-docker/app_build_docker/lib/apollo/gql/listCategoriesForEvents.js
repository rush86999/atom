"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const graphql_tag_1 = __importDefault(require("graphql-tag"));
exports.default = (0, graphql_tag_1.default) `
  query ListCategoriesForEventIds($eventIds: [String!]!) {
    Category_Event(where: { eventId: { _in: $eventIds } }) {
      Category {
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
      eventId
      categoryId
      createdDate
      deleted
      id
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhdGVnb3JpZXNGb3JFdmVudHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50cy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQUFBLDhEQUE4QjtBQUU5QixrQkFBZSxJQUFBLHFCQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBeUNqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdxbCBmcm9tICdncmFwaHFsLXRhZyc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgTGlzdENhdGVnb3JpZXNGb3JFdmVudElkcygkZXZlbnRJZHM6IFtTdHJpbmchXSEpIHtcbiAgICBDYXRlZ29yeV9FdmVudCh3aGVyZTogeyBldmVudElkOiB7IF9pbjogJGV2ZW50SWRzIH0gfSkge1xuICAgICAgQ2F0ZWdvcnkge1xuICAgICAgICBjb2xvclxuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBkZWZhdWx0SXNCcmVha1xuICAgICAgICBkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgZGVmYXVsdElzTWVldGluZ1xuICAgICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgICAgZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgICBkZWZhdWx0VGltZUJsb2NraW5nXG4gICAgICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZVxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGlkXG4gICAgICAgIG5hbWVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgICAgZXZlbnRJZFxuICAgICAgY2F0ZWdvcnlJZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGlkXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==