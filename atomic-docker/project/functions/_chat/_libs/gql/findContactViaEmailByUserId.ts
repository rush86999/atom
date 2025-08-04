export default `
query FindContactByEmailGivenUserId($userId: uuid!, $emailFilter: jsonb) {
  Contact(where: {userId: {_eq: $userId}, emails: {_contains: $emailFilter}}) {
    app
    company
    contactType
    createdDate
    deleted
    department
    emails
    firstName
    id
    imAddresses
    image
    imageAvailable
    jobTitle
    lastName
    linkAddresses
    maidenName
    middleName
    name
    namePrefix
    nameSuffix
    nickname
    notes
    phoneNumbers
    phoneticFirstName
    phoneticLastName
    phoneticMiddleName
    updatedAt
    userId
  }
}
`;
