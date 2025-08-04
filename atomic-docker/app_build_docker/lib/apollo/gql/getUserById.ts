import { gql } from '@apollo/client';

export default gql`
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
