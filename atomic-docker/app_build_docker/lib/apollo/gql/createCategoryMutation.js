"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation CreateCategory(
    $id: uuid!
    $userId: uuid!
    $name: String!
    $updatedAt: timestamptz
    $createdDate: timestamptz
  ) {
    insert_Category_one(
      object: {
        name: $name
        id: $id
        deleted: false
        updatedAt: $updatedAt
        createdDate: $createdDate
        userId: $userId
        defaultAvailability: false
        defaultModifiable: true
        defaultIsMeeting: false
        defaultIsExternalMeeting: false
        defaultMeetingModifiable: true
        defaultExternalMeetingModifiable: true
      }
    ) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3JlYXRlQ2F0ZWdvcnlNdXRhdGlvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNyZWF0ZUNhdGVnb3J5TXV0YXRpb24udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBcURqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIENyZWF0ZUNhdGVnb3J5KFxuICAgICRpZDogdXVpZCFcbiAgICAkdXNlcklkOiB1dWlkIVxuICAgICRuYW1lOiBTdHJpbmchXG4gICAgJHVwZGF0ZWRBdDogdGltZXN0YW1wdHpcbiAgICAkY3JlYXRlZERhdGU6IHRpbWVzdGFtcHR6XG4gICkge1xuICAgIGluc2VydF9DYXRlZ29yeV9vbmUoXG4gICAgICBvYmplY3Q6IHtcbiAgICAgICAgbmFtZTogJG5hbWVcbiAgICAgICAgaWQ6ICRpZFxuICAgICAgICBkZWxldGVkOiBmYWxzZVxuICAgICAgICB1cGRhdGVkQXQ6ICR1cGRhdGVkQXRcbiAgICAgICAgY3JlYXRlZERhdGU6ICRjcmVhdGVkRGF0ZVxuICAgICAgICB1c2VySWQ6ICR1c2VySWRcbiAgICAgICAgZGVmYXVsdEF2YWlsYWJpbGl0eTogZmFsc2VcbiAgICAgICAgZGVmYXVsdE1vZGlmaWFibGU6IHRydWVcbiAgICAgICAgZGVmYXVsdElzTWVldGluZzogZmFsc2VcbiAgICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nOiBmYWxzZVxuICAgICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGU6IHRydWVcbiAgICAgICAgZGVmYXVsdEV4dGVybmFsTWVldGluZ01vZGlmaWFibGU6IHRydWVcbiAgICAgIH1cbiAgICApIHtcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICBkZWxldGVkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgY29weVJlbWluZGVyc1xuICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICBkZWZhdWx0QXZhaWxhYmlsaXR5XG4gICAgICBkZWZhdWx0VGltZUJsb2NraW5nXG4gICAgICBkZWZhdWx0VGltZVByZWZlcmVuY2VcbiAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgIGRlZmF1bHRQcmlvcml0eUxldmVsXG4gICAgICBkZWZhdWx0TW9kaWZpYWJsZVxuICAgICAgY29weUlzQnJlYWtcbiAgICAgIGRlZmF1bHRJc0JyZWFrXG4gICAgICBjb2xvclxuICAgICAgY29weUlzTWVldGluZ1xuICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICBkZWZhdWx0SXNNZWV0aW5nXG4gICAgICBkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIGRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgZGVmYXVsdEV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICB9XG4gIH1cbmA7XG4iXX0=