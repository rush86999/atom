declare const _default: "\nquery listAttendeesByIds($ids: [String!]!) {\n  Attendee(where: {id: {_in: $ids}}) {\n    additionalGuests\n    comment\n    contactId\n    createdDate\n    deleted\n    emails\n    eventId\n    id\n    imAddresses\n    name\n    optional\n    phoneNumbers\n    resource\n    responseStatus\n    updatedAt\n    userId\n  }\n}\n";
export default _default;
