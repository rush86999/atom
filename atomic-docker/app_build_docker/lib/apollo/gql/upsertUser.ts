import { gql } from '@apollo/client';

export default gql`
  mutation InsertUser($user: User_insert_input!) {
    insert_User_one(
      object: $user
      on_conflict: {
        constraint: User_pkey
        update_columns: [email, name, deleted, updatedAt]
      }
    ) {
      id
      name
      email
      deleted
      createdDate
      updatedAt
    }
  }
`;
