import { gql } from '@apollo/client';

export default gql`
  query GetCustomerByUserId($userId: uuid!) {
    Customer(where: { userId: { _eq: $userId } }) {
      address
      createdDate
      description
      email
      id
      name
      phone
      updatedAt
      userId
    }
  }
`;
