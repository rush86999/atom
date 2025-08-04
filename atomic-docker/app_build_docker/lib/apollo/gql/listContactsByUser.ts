import { gql } from '@apollo/client';

export default gql`
  query listContactsByUser($userId: uuid!) {
    Contact(where: { userId: { _eq: $userId } }) {
      id
      name
      firstName
      middleName
      lastName
      maidenName
      namePrefix
      nameSuffix
      nickname
      phoneticFirstName
      phoneticMiddleName
      phoneticLastName
      company
      jobTitle
      department
      notes
      imageAvailable
      image
      contactType
      emails
      phoneNumbers
      imAddresses
      linkAddresses
      app
      deleted
      createdDate
      updatedAt
      userId
    }
  }
`;
