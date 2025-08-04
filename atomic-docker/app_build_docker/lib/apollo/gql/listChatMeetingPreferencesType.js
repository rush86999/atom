"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query listChatMeetingPreferences($userId: uuid!) {
    Chat_Meeting_Preference(where: { userId: { _eq: $userId } }) {
      anyoneCanAddSelf
      bufferTime
      conferenceApp
      createdDate
      duration
      enableConference
      guestsCanInviteOthers
      guestsCanSeeOtherGuests
      id
      name
      primaryEmail
      reminders
      sendUpdates
      timezone
      transparency
      updatedAt
      useDefaultAlarms
      userId
      visibility
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F3QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgbGlzdENoYXRNZWV0aW5nUHJlZmVyZW5jZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICBDaGF0X01lZXRpbmdfUHJlZmVyZW5jZSh3aGVyZTogeyB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfSkge1xuICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgYnVmZmVyVGltZVxuICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGR1cmF0aW9uXG4gICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICByZW1pbmRlcnNcbiAgICAgIHNlbmRVcGRhdGVzXG4gICAgICB0aW1lem9uZVxuICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgIHVzZXJJZFxuICAgICAgdmlzaWJpbGl0eVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==