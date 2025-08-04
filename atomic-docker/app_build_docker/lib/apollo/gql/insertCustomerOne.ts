import { gql } from '@apollo/client';

export default gql`
  mutation InsertCustomerOne($customer: Customer_insert_input!) {
    insert_Customer_one(object: $customer) {
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
