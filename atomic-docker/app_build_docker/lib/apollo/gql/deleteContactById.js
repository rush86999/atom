"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteContactById($id: String!) {
    delete_Contact_by_pk(id: $id) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ29udGFjdEJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVDb250YWN0QnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FnQ2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gRGVsZXRlQ29udGFjdEJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gICAgZGVsZXRlX0NvbnRhY3RfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgYXBwXG4gICAgICBjb21wYW55XG4gICAgICBjb250YWN0VHlwZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGRlcGFydG1lbnRcbiAgICAgIGVtYWlsc1xuICAgICAgZmlyc3ROYW1lXG4gICAgICBpZFxuICAgICAgaW1BZGRyZXNzZXNcbiAgICAgIGltYWdlQXZhaWxhYmxlXG4gICAgICBqb2JUaXRsZVxuICAgICAgbGFzdE5hbWVcbiAgICAgIGxpbmtBZGRyZXNzZXNcbiAgICAgIG1haWRlbk5hbWVcbiAgICAgIG1pZGRsZU5hbWVcbiAgICAgIG5hbWVcbiAgICAgIG5hbWVQcmVmaXhcbiAgICAgIG5hbWVTdWZmaXhcbiAgICAgIG5pY2tuYW1lXG4gICAgICBub3Rlc1xuICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICBwaG9uZXRpY0ZpcnN0TmFtZVxuICAgICAgcGhvbmV0aWNMYXN0TmFtZVxuICAgICAgcGhvbmV0aWNNaWRkbGVOYW1lXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==