export default `
query GetChatMeetingPreferenceByUserId($userId: uuid!) {
    Chat_Meeting_Preference(where: {userId: {_eq: $userId}}) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlQnlVc2VySWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VCeVVzZXJJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7R0F3QlosQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbnF1ZXJ5IEdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUJ5VXNlcklkKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2Uod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgYnVmZmVyVGltZVxuICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGR1cmF0aW9uXG4gICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICBpZFxuICAgICAgbmFtZVxuICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICByZW1pbmRlcnNcbiAgICAgIHNlbmRVcGRhdGVzXG4gICAgICB0aW1lem9uZVxuICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgIHVzZXJJZFxuICAgICAgdmlzaWJpbGl0eVxuICAgIH1cbiAgfVxuICBgO1xuIl19