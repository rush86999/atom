import { gql } from '@apollo/client';

export default gql`
  mutation RemoveEventConnectionsForCategory($categoryId: uuid!) {
    delete_Category_Event(where: { categoryId: { _eq: $categoryId } }) {
      affected_rows
      returning {
        id
        categoryId
        createdDate
        deleted
        eventId
        updatedAt
        userId
      }
    }
  }
`;
