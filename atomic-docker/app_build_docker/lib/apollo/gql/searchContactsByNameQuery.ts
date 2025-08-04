import { gql } from '@apollo/client';

export default gql`
  query SearchContacts($name: String!, $userId: uuid!) {
    Contact(where: { name: { _ilike: $name }, userId: { _eq: $userId } }) {
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
      image
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
