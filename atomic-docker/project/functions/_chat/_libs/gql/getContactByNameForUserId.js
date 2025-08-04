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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q29udGFjdEJ5TmFtZUZvclVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdldENvbnRhY3RCeU5hbWVGb3JVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWtDZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgR2V0Q29udGFjdEJ5TmFtZUZvclVzZXJJZCgkdXNlcklkOiB1dWlkISwgJG5hbWU6IFN0cmluZyEpIHtcbiAgQ29udGFjdCh3aGVyZToge19vcjoge2ZpcnN0TmFtZToge19pbGlrZTogJG5hbWV9LCBuYW1lOiB7X2lsaWtlOiAkbmFtZX0sIHBob25ldGljRmlyc3ROYW1lOiB7X2lsaWtlOiAkbmFtZX0sIG5pY2tuYW1lOiB7X2lsaWtlOiAkbmFtZX0sIHBob25ldGljTGFzdE5hbWU6IHtfaWxpa2U6ICRuYW1lfSwgcGhvbmV0aWNNaWRkbGVOYW1lOiB7X2lsaWtlOiAkbmFtZX0sIGxhc3ROYW1lOiB7X2lsaWtlOiAkbmFtZX0sIGpvYlRpdGxlOiB7X2lsaWtlOiAkbmFtZX19LCB1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgIGFwcFxuICAgIGNvbXBhbnlcbiAgICBjb250YWN0VHlwZVxuICAgIGNyZWF0ZWREYXRlXG4gICAgZGVsZXRlZFxuICAgIGRlcGFydG1lbnRcbiAgICBlbWFpbHNcbiAgICBmaXJzdE5hbWVcbiAgICBpZFxuICAgIGltQWRkcmVzc2VzXG4gICAgaW1hZ2VcbiAgICBpbWFnZUF2YWlsYWJsZVxuICAgIGpvYlRpdGxlXG4gICAgbGFzdE5hbWVcbiAgICBsaW5rQWRkcmVzc2VzXG4gICAgbWFpZGVuTmFtZVxuICAgIG1pZGRsZU5hbWVcbiAgICBuYW1lXG4gICAgbmFtZVByZWZpeFxuICAgIG5hbWVTdWZmaXhcbiAgICBuaWNrbmFtZVxuICAgIG5vdGVzXG4gICAgcGhvbmVOdW1iZXJzXG4gICAgcGhvbmV0aWNGaXJzdE5hbWVcbiAgICBwaG9uZXRpY0xhc3ROYW1lXG4gICAgcGhvbmV0aWNNaWRkbGVOYW1lXG4gICAgdXBkYXRlZEF0XG4gICAgdXNlcklkXG4gIH1cbn1cblxuYDtcbiJdfQ==