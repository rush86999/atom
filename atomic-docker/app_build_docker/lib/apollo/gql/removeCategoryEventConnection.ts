import { gql } from '@apollo/client';

export default gql`
  mutation RemoveCategoryEventConnection(
    $categoryId: uuid!
    $eventId: String!
  ) {
    delete_Category_Event(
      where: { categoryId: { _eq: $categoryId }, eventId: { _eq: $eventId } }
    ) {
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
