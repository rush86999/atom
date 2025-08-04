export default `
query GetUserById($id: uuid!) {
  User_by_pk(id: $id) {
    createdDate
    deleted
    email
    id
    name
    updatedAt
    userPreferenceId
  }
}
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0VXNlckJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRVc2VyQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Q0FZZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgR2V0VXNlckJ5SWQoJGlkOiB1dWlkISkge1xuICBVc2VyX2J5X3BrKGlkOiAkaWQpIHtcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBlbWFpbFxuICAgIGlkXG4gICAgbmFtZVxuICAgIHVwZGF0ZWRBdFxuICAgIHVzZXJQcmVmZXJlbmNlSWRcbiAgfVxufVxuYDtcbiJdfQ==