export default `
query GetContactByNameForUserId($userId: uuid!, $name: String!) {
  Contact(where: {_or: {firstName: {_ilike: $name}, name: {_ilike: $name}, phoneticFirstName: {_ilike: $name}, nickname: {_ilike: $name}, phoneticLastName: {_ilike: $name}, phoneticMiddleName: {_ilike: $name}, lastName: {_ilike: $name}, jobTitle: {_ilike: $name}}, userId: {_eq: $userId}}) {
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
