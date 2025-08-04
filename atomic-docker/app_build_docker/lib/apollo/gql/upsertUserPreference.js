"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertUserPreference(
    $userPreference: User_Preference_insert_input!
  ) {
    insert_User_Preference_one(
      object: $userPreference
      on_conflict: {
        constraint: UserPreference_pkey
        update_columns: [
          userId
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
          breakLength
          breakColor
          maxWorkLoadPercent
          backToBackMeetings
          maxNumberOfMeetings
          minNumberOfBreaks
          copyIsMeeting
          copyIsExternalMeeting
          copyColor
          deleted
          updatedAt
        ]
      }
    ) {
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
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0VXNlclByZWZlcmVuY2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRVc2VyUHJlZmVyZW5jZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FvRWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gSW5zZXJ0VXNlclByZWZlcmVuY2UoXG4gICAgJHVzZXJQcmVmZXJlbmNlOiBVc2VyX1ByZWZlcmVuY2VfaW5zZXJ0X2lucHV0IVxuICApIHtcbiAgICBpbnNlcnRfVXNlcl9QcmVmZXJlbmNlX29uZShcbiAgICAgIG9iamVjdDogJHVzZXJQcmVmZXJlbmNlXG4gICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICBjb25zdHJhaW50OiBVc2VyUHJlZmVyZW5jZV9wa2V5XG4gICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgICAgZm9sbG93VXBcbiAgICAgICAgICBpc1B1YmxpY0NhbGVuZGFyXG4gICAgICAgICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzXG4gICAgICAgICAgc3RhcnRUaW1lc1xuICAgICAgICAgIGVuZFRpbWVzXG4gICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICBicmVha0xlbmd0aFxuICAgICAgICAgIGJyZWFrQ29sb3JcbiAgICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgICBiYWNrVG9CYWNrTWVldGluZ3NcbiAgICAgICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICAgICAgbWluTnVtYmVyT2ZCcmVha3NcbiAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgY29weUNvbG9yXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICBdXG4gICAgICB9XG4gICAgKSB7XG4gICAgICBpZFxuICAgICAgcmVtaW5kZXJzXG4gICAgICBmb2xsb3dVcFxuICAgICAgaXNQdWJsaWNDYWxlbmRhclxuICAgICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzXG4gICAgICBzdGFydFRpbWVzXG4gICAgICBlbmRUaW1lc1xuICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICBjb3B5SXNCcmVha1xuICAgICAgbWF4V29ya0xvYWRQZXJjZW50XG4gICAgICBiYWNrVG9CYWNrTWVldGluZ3NcbiAgICAgIG1heE51bWJlck9mTWVldGluZ3NcbiAgICAgIG1pbk51bWJlck9mQnJlYWtzXG4gICAgICBicmVha0xlbmd0aFxuICAgICAgYnJlYWtDb2xvclxuICAgICAgY29weUlzTWVldGluZ1xuICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBjb3B5Q29sb3JcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==