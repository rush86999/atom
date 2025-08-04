"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertMeetingAssistInvite(
    $meetingAssistInvites: [Meeting_Assist_Invite_insert_input!]!
  ) {
    insert_Meeting_Assist_Invite(
      objects: $meetingAssistInvites
      on_conflict: {
        constraint: Meeting_Assist_Invite_pkey
        update_columns: [
          email
          hostId
          hostName
          meetingId
          name
          response
          updatedAt
          userId
          contactId
        ]
      }
    ) {
      affected_rows
      returning {
        createdDate
        email
        hostId
        hostName
        id
        meetingId
        name
        response
        updatedAt
        userId
        contactId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZXNNdXRhdGlvbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVzTXV0YXRpb24udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FxQ2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gSW5zZXJ0TWVldGluZ0Fzc2lzdEludml0ZShcbiAgICAkbWVldGluZ0Fzc2lzdEludml0ZXM6IFtNZWV0aW5nX0Fzc2lzdF9JbnZpdGVfaW5zZXJ0X2lucHV0IV0hXG4gICkge1xuICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9JbnZpdGUoXG4gICAgICBvYmplY3RzOiAkbWVldGluZ0Fzc2lzdEludml0ZXNcbiAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgIGNvbnN0cmFpbnQ6IE1lZXRpbmdfQXNzaXN0X0ludml0ZV9wa2V5XG4gICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgZW1haWxcbiAgICAgICAgICBob3N0SWRcbiAgICAgICAgICBob3N0TmFtZVxuICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgIG5hbWVcbiAgICAgICAgICByZXNwb25zZVxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICBdXG4gICAgICB9XG4gICAgKSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBlbWFpbFxuICAgICAgICBob3N0SWRcbiAgICAgICAgaG9zdE5hbWVcbiAgICAgICAgaWRcbiAgICAgICAgbWVldGluZ0lkXG4gICAgICAgIG5hbWVcbiAgICAgICAgcmVzcG9uc2VcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgICBjb250YWN0SWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=