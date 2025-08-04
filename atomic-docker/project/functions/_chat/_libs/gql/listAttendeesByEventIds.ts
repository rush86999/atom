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
