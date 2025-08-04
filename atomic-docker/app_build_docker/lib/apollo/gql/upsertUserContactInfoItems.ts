import { gql } from '@apollo/client';

export default gql`
  mutation UpsertUserContactInfo(
    $contactInfoItems: [User_Contact_Info_insert_input!]!
  ) {
    insert_User_Contact_Info(
      objects: $contactInfoItems
      on_conflict: {
        constraint: User_Contact_Info_pkey
        update_columns: [name, primary, type, updatedAt]
      }
    ) {
      affected_rows
      returning {
        createdDate
        id
        name
        primary
        type
        updatedAt
        userId
      }
    }
  }
`;
