export default `
query listAttendeesByEventIds($eventIds: [String!]!) {
  Attendee(where: {eventId: {_in: $eventIds}}) {
    additionalGuests
    comment
    contactId
    createdDate
    deleted
    emails
    eventId
    id
    imAddresses
    name
    optional
    phoneNumbers
    resource
    responseStatus
    updatedAt
    userId
  }
}
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdEF0dGVuZGVlc0J5RXZlbnRJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0QXR0ZW5kZWVzQnlFdmVudElkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FxQmQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbnF1ZXJ5IGxpc3RBdHRlbmRlZXNCeUV2ZW50SWRzKCRldmVudElkczogW1N0cmluZyFdISkge1xuICBBdHRlbmRlZSh3aGVyZToge2V2ZW50SWQ6IHtfaW46ICRldmVudElkc319KSB7XG4gICAgYWRkaXRpb25hbEd1ZXN0c1xuICAgIGNvbW1lbnRcbiAgICBjb250YWN0SWRcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBlbWFpbHNcbiAgICBldmVudElkXG4gICAgaWRcbiAgICBpbUFkZHJlc3Nlc1xuICAgIG5hbWVcbiAgICBvcHRpb25hbFxuICAgIHBob25lTnVtYmVyc1xuICAgIHJlc291cmNlXG4gICAgcmVzcG9uc2VTdGF0dXNcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgfVxufVxuYDtcbiJdfQ==