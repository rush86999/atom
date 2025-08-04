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
