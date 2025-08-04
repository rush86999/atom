export default `
query listAttendeesByIds($ids: [String!]!) {
  Attendee(where: {id: {_in: $ids}}) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdEF0dGVuZGVlc0J5SWRzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdEF0dGVuZGVlc0J5SWRzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLGVBQWU7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgbGlzdEF0dGVuZGVlc0J5SWRzKCRpZHM6IFtTdHJpbmchXSEpIHtcbiAgQXR0ZW5kZWUod2hlcmU6IHtpZDoge19pbjogJGlkc319KSB7XG4gICAgYWRkaXRpb25hbEd1ZXN0c1xuICAgIGNvbW1lbnRcbiAgICBjb250YWN0SWRcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBlbWFpbHNcbiAgICBldmVudElkXG4gICAgaWRcbiAgICBpbUFkZHJlc3Nlc1xuICAgIG5hbWVcbiAgICBvcHRpb25hbFxuICAgIHBob25lTnVtYmVyc1xuICAgIHJlc291cmNlXG4gICAgcmVzcG9uc2VTdGF0dXNcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgfVxufVxuYDtcbiJdfQ==