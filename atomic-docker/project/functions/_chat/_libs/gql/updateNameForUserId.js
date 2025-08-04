export default `
mutation UpdateNameForUserById($id: uuid!, $name: String!) {
  update_User_by_pk(pk_columns: {id: $id}, _set: {name: $name}) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlTmFtZUZvclVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZU5hbWVGb3JVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7O0NBWWQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbm11dGF0aW9uIFVwZGF0ZU5hbWVGb3JVc2VyQnlJZCgkaWQ6IHV1aWQhLCAkbmFtZTogU3RyaW5nISkge1xuICB1cGRhdGVfVXNlcl9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHtuYW1lOiAkbmFtZX0pIHtcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBlbWFpbFxuICAgIGlkXG4gICAgbmFtZVxuICAgIHVwZGF0ZWRBdFxuICAgIHVzZXJQcmVmZXJlbmNlSWRcbiAgfVxufVxuYDtcbiJdfQ==