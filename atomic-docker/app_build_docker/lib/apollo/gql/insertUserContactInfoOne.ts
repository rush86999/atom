import { gql } from '@apollo/client';

export default gql`
  mutation InsertUserContactInfoOne(
    $contactInfo: User_Contact_Info_insert_input!
  ) {
    insert_User_Contact_Info_one(object: $contactInfo) {
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
