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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluZENvbnRhY3RWaWFFbWFpbEJ5VXNlcklkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZmluZENvbnRhY3RWaWFFbWFpbEJ5VXNlcklkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLGVBQWU7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWlDZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgRmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQoJHVzZXJJZDogdXVpZCEsICRlbWFpbEZpbHRlcjoganNvbmIpIHtcbiAgQ29udGFjdCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVtYWlsczoge19jb250YWluczogJGVtYWlsRmlsdGVyfX0pIHtcbiAgICBhcHBcbiAgICBjb21wYW55XG4gICAgY29udGFjdFR5cGVcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBkZXBhcnRtZW50XG4gICAgZW1haWxzXG4gICAgZmlyc3ROYW1lXG4gICAgaWRcbiAgICBpbUFkZHJlc3Nlc1xuICAgIGltYWdlXG4gICAgaW1hZ2VBdmFpbGFibGVcbiAgICBqb2JUaXRsZVxuICAgIGxhc3ROYW1lXG4gICAgbGlua0FkZHJlc3Nlc1xuICAgIG1haWRlbk5hbWVcbiAgICBtaWRkbGVOYW1lXG4gICAgbmFtZVxuICAgIG5hbWVQcmVmaXhcbiAgICBuYW1lU3VmZml4XG4gICAgbmlja25hbWVcbiAgICBub3Rlc1xuICAgIHBob25lTnVtYmVyc1xuICAgIHBob25ldGljRmlyc3ROYW1lXG4gICAgcGhvbmV0aWNMYXN0TmFtZVxuICAgIHBob25ldGljTWlkZGxlTmFtZVxuICAgIHVwZGF0ZWRBdFxuICAgIHVzZXJJZFxuICB9XG59XG5gO1xuIl19