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
