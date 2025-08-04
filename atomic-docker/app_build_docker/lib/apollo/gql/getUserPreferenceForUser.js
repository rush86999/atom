"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetUserPreferenceForUser($userId: uuid!) {
    User_Preference(where: { userId: { _eq: $userId } }) {
      id
      reminders
      followUp
      isPublicCalendar
      publicCalendarCategories
      startTimes
      endTimes
      copyAvailability
      copyTimeBlocking
      copyTimePreference
      copyReminders
      copyPriorityLevel
      copyModifiable
      copyCategories
      copyIsBreak
      maxWorkLoadPercent
      backToBackMeetings
      maxNumberOfMeetings
      minNumberOfBreaks
      breakLength
      breakColor
      copyIsMeeting
      copyIsExternalMeeting
      copyColor
      deleted
      createdDate
      updatedAt
      userId
      onBoarded
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBa0NqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IEdldFVzZXJQcmVmZXJlbmNlRm9yVXNlcigkdXNlcklkOiB1dWlkISkge1xuICAgIFVzZXJfUHJlZmVyZW5jZSh3aGVyZTogeyB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfSkge1xuICAgICAgaWRcbiAgICAgIHJlbWluZGVyc1xuICAgICAgZm9sbG93VXBcbiAgICAgIGlzUHVibGljQ2FsZW5kYXJcbiAgICAgIHB1YmxpY0NhbGVuZGFyQ2F0ZWdvcmllc1xuICAgICAgc3RhcnRUaW1lc1xuICAgICAgZW5kVGltZXNcbiAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgY29weVJlbWluZGVyc1xuICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgY29weUlzQnJlYWtcbiAgICAgIG1heFdvcmtMb2FkUGVyY2VudFxuICAgICAgYmFja1RvQmFja01lZXRpbmdzXG4gICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICBtaW5OdW1iZXJPZkJyZWFrc1xuICAgICAgYnJlYWtMZW5ndGhcbiAgICAgIGJyZWFrQ29sb3JcbiAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgY29weUNvbG9yXG4gICAgICBkZWxldGVkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIG9uQm9hcmRlZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==