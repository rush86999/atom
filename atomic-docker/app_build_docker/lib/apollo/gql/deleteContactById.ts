import { gql } from '@apollo/client';

export default gql`
  mutation DeleteContactById($id: String!) {
    delete_Contact_by_pk(id: $id) {
      app
      company
      contactType
      createdDate
      deleted
      department
      emails
      firstName
      id
      imAddresses
      imageAvailable
      jobTitle
      lastName
      linkAddresses
      maidenName
      middleName
      name
      namePrefix
      nameSuffix
      nickname
      notes
      phoneNumbers
      phoneticFirstName
      phoneticLastName
      phoneticMiddleName
      updatedAt
      userId
    }
  }
`;
