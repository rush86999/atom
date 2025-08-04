"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query SearchMeetingAssists($userId: uuid!, $summary: String!) {
    Meeting_Assist(
      where: { userId: { _eq: $userId }, summary: { _ilike: $summary } }
      order_by: { windowStartDate: desc_nulls_first }
    ) {
      allowAttendeeUpdatePreferences
      anyoneCanAddSelf
      attendeeCanModify
      attendeeCount
      attendeeRespondedCount
      backgroundColor
      bufferTime
      calendarId
      cancelIfAnyRefuse
      cancelled
      colorId
      conferenceApp
      createdDate
      duration
      enableAttendeePreferences
      enableConference
      enableHostPreferences
      endDate
      eventId
      expireDate
      foregroundColor
      frequency
      guaranteeAvailability
      guestsCanInviteOthers
      guestsCanSeeOtherGuests
      id
      interval
      location
      minThresholdCount
      notes
      originalMeetingId
      priority
      reminders
      sendUpdates
      startDate
      summary
      timezone
      transparency
      until
      updatedAt
      useDefaultAlarms
      userId
      visibility
      windowEndDate
      windowStartDate
      lockAfter
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VhcmNoTWVldGluZ0Fzc2lzdHNRdWVyeS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlYXJjaE1lZXRpbmdBc3Npc3RzUXVlcnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXNEakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBTZWFyY2hNZWV0aW5nQXNzaXN0cygkdXNlcklkOiB1dWlkISwgJHN1bW1hcnk6IFN0cmluZyEpIHtcbiAgICBNZWV0aW5nX0Fzc2lzdChcbiAgICAgIHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSwgc3VtbWFyeTogeyBfaWxpa2U6ICRzdW1tYXJ5IH0gfVxuICAgICAgb3JkZXJfYnk6IHsgd2luZG93U3RhcnREYXRlOiBkZXNjX251bGxzX2ZpcnN0IH1cbiAgICApIHtcbiAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnlcbiAgICAgIGF0dGVuZGVlQ291bnRcbiAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgYnVmZmVyVGltZVxuICAgICAgY2FsZW5kYXJJZFxuICAgICAgY2FuY2VsSWZBbnlSZWZ1c2VcbiAgICAgIGNhbmNlbGxlZFxuICAgICAgY29sb3JJZFxuICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGR1cmF0aW9uXG4gICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzXG4gICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgIGVuZERhdGVcbiAgICAgIGV2ZW50SWRcbiAgICAgIGV4cGlyZURhdGVcbiAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgZnJlcXVlbmN5XG4gICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgIGlkXG4gICAgICBpbnRlcnZhbFxuICAgICAgbG9jYXRpb25cbiAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICBub3Rlc1xuICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgIHByaW9yaXR5XG4gICAgICByZW1pbmRlcnNcbiAgICAgIHNlbmRVcGRhdGVzXG4gICAgICBzdGFydERhdGVcbiAgICAgIHN1bW1hcnlcbiAgICAgIHRpbWV6b25lXG4gICAgICB0cmFuc3BhcmVuY3lcbiAgICAgIHVudGlsXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgIHVzZXJJZFxuICAgICAgdmlzaWJpbGl0eVxuICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICBsb2NrQWZ0ZXJcbiAgICB9XG4gIH1cbmA7XG4iXX0=