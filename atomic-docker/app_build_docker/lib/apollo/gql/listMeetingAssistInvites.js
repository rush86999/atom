"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListMeetingAssistInvites($meetingId: uuid!) {
    Meeting_Assist_Invite(where: { meetingId: { _eq: $meetingId } }) {
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
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7O0NBZ0JqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IExpc3RNZWV0aW5nQXNzaXN0SW52aXRlcygkbWVldGluZ0lkOiB1dWlkISkge1xuICAgIE1lZXRpbmdfQXNzaXN0X0ludml0ZSh3aGVyZTogeyBtZWV0aW5nSWQ6IHsgX2VxOiAkbWVldGluZ0lkIH0gfSkge1xuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGVtYWlsXG4gICAgICBob3N0SWRcbiAgICAgIGhvc3ROYW1lXG4gICAgICBpZFxuICAgICAgbWVldGluZ0lkXG4gICAgICBuYW1lXG4gICAgICByZXNwb25zZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIGNvbnRhY3RJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==