import { gql } from '@apollo/client';

export default gql`
  query DeleteUserContactInfoItems($itemIds: [String!]!) {
    User_Contact_Info(where: { id: { _in: $itemIds } }) {
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
