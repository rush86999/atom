"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertCategory($categories: [Category_insert_input!]!) {
    insert_Category(
      objects: $categories
      on_conflict: {
        constraint: Category_pkey
        update_columns: [
          name
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
          color
          copyIsMeeting
          copyIsExternalMeeting
          defaultIsMeeting
          defaultIsExternalMeeting
          deleted
          updatedAt
          defaultIsBreak
          defaultMeetingModifiable
          defaultExternalMeetingModifiable
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0Q2F0ZWdvcnkuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRDYXRlZ29yeS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBdUNqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIEluc2VydENhdGVnb3J5KCRjYXRlZ29yaWVzOiBbQ2F0ZWdvcnlfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgaW5zZXJ0X0NhdGVnb3J5KFxuICAgICAgb2JqZWN0czogJGNhdGVnb3JpZXNcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IENhdGVnb3J5X3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICBkZWZhdWx0VGltZUJsb2NraW5nXG4gICAgICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgICAgIGRlZmF1bHRQcmlvcml0eUxldmVsXG4gICAgICAgICAgZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgIGNvbG9yXG4gICAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgIGRlZmF1bHRJc01lZXRpbmdcbiAgICAgICAgICBkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgZGVmYXVsdElzQnJlYWtcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBdXG4gICAgICB9XG4gICAgKSB7XG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBpZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==