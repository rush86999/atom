"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertReminder($reminders: [Reminder_insert_input!]!) {
    insert_Reminder(
      objects: $reminders
      on_conflict: {
        constraint: Reminder_pkey
        update_columns: [
          eventId
          reminderDate
          timezone
          method
          minutes
          useDefault
          updatedAt
          deleted
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0UmVtaW5kZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRSZW1pbmRlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F1QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gSW5zZXJ0UmVtaW5kZXIoJHJlbWluZGVyczogW1JlbWluZGVyX2luc2VydF9pbnB1dCFdISkge1xuICAgIGluc2VydF9SZW1pbmRlcihcbiAgICAgIG9iamVjdHM6ICRyZW1pbmRlcnNcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IFJlbWluZGVyX3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICBldmVudElkXG4gICAgICAgICAgcmVtaW5kZXJEYXRlXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICBtZXRob2RcbiAgICAgICAgICBtaW51dGVzXG4gICAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgXVxuICAgICAgfVxuICAgICkge1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgaWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=