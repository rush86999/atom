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
