"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query SearchContacts($name: String!, $userId: uuid!) {
    Contact(where: { name: { _ilike: $name }, userId: { _eq: $userId } }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VhcmNoQ29udGFjdHNCeU5hbWVRdWVyeS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlYXJjaENvbnRhY3RzQnlOYW1lUXVlcnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQWlDakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBTZWFyY2hDb250YWN0cygkbmFtZTogU3RyaW5nISwgJHVzZXJJZDogdXVpZCEpIHtcbiAgICBDb250YWN0KHdoZXJlOiB7IG5hbWU6IHsgX2lsaWtlOiAkbmFtZSB9LCB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfSkge1xuICAgICAgYXBwXG4gICAgICBjb21wYW55XG4gICAgICBjb250YWN0VHlwZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGRlcGFydG1lbnRcbiAgICAgIGVtYWlsc1xuICAgICAgZmlyc3ROYW1lXG4gICAgICBpZFxuICAgICAgaW1BZGRyZXNzZXNcbiAgICAgIGltYWdlXG4gICAgICBpbWFnZUF2YWlsYWJsZVxuICAgICAgam9iVGl0bGVcbiAgICAgIGxhc3ROYW1lXG4gICAgICBsaW5rQWRkcmVzc2VzXG4gICAgICBtYWlkZW5OYW1lXG4gICAgICBtaWRkbGVOYW1lXG4gICAgICBuYW1lXG4gICAgICBuYW1lUHJlZml4XG4gICAgICBuYW1lU3VmZml4XG4gICAgICBuaWNrbmFtZVxuICAgICAgbm90ZXNcbiAgICAgIHBob25lTnVtYmVyc1xuICAgICAgcGhvbmV0aWNGaXJzdE5hbWVcbiAgICAgIHBob25ldGljTGFzdE5hbWVcbiAgICAgIHBob25ldGljTWlkZGxlTmFtZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=