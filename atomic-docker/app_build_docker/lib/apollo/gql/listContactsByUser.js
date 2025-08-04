"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query listContactsByUser($userId: uuid!) {
    Contact(where: { userId: { _eq: $userId } }) {
      id
      name
      firstName
      middleName
      lastName
      maidenName
      namePrefix
      nameSuffix
      nickname
      phoneticFirstName
      phoneticMiddleName
      phoneticLastName
      company
      jobTitle
      department
      notes
      imageAvailable
      image
      contactType
      emails
      phoneNumbers
      imAddresses
      linkAddresses
      app
      deleted
      createdDate
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENvbnRhY3RzQnlVc2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdENvbnRhY3RzQnlVc2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FpQ2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgbGlzdENvbnRhY3RzQnlVc2VyKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgQ29udGFjdCh3aGVyZTogeyB1c2VySWQ6IHsgX2VxOiAkdXNlcklkIH0gfSkge1xuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIGZpcnN0TmFtZVxuICAgICAgbWlkZGxlTmFtZVxuICAgICAgbGFzdE5hbWVcbiAgICAgIG1haWRlbk5hbWVcbiAgICAgIG5hbWVQcmVmaXhcbiAgICAgIG5hbWVTdWZmaXhcbiAgICAgIG5pY2tuYW1lXG4gICAgICBwaG9uZXRpY0ZpcnN0TmFtZVxuICAgICAgcGhvbmV0aWNNaWRkbGVOYW1lXG4gICAgICBwaG9uZXRpY0xhc3ROYW1lXG4gICAgICBjb21wYW55XG4gICAgICBqb2JUaXRsZVxuICAgICAgZGVwYXJ0bWVudFxuICAgICAgbm90ZXNcbiAgICAgIGltYWdlQXZhaWxhYmxlXG4gICAgICBpbWFnZVxuICAgICAgY29udGFjdFR5cGVcbiAgICAgIGVtYWlsc1xuICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICBpbUFkZHJlc3Nlc1xuICAgICAgbGlua0FkZHJlc3Nlc1xuICAgICAgYXBwXG4gICAgICBkZWxldGVkXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICB9XG4gIH1cbmA7XG4iXX0=