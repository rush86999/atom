export default `
query GetContactInfosWithIds($ids: [String!]!) {
  User_Contact_Info(where: {id: {_in: $ids}}) {
    createdDate
    id
    name
    primary
    type
    updatedAt
    userId
  }
}
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q29udGFjdEluZm9zQnlJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDb250YWN0SW5mb3NCeUlkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Q0FZZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgR2V0Q29udGFjdEluZm9zV2l0aElkcygkaWRzOiBbU3RyaW5nIV0hKSB7XG4gIFVzZXJfQ29udGFjdF9JbmZvKHdoZXJlOiB7aWQ6IHtfaW46ICRpZHN9fSkge1xuICAgIGNyZWF0ZWREYXRlXG4gICAgaWRcbiAgICBuYW1lXG4gICAgcHJpbWFyeVxuICAgIHR5cGVcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgfVxufVxuYDtcbiJdfQ==