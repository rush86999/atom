import { gql } from '@apollo/client';

export default gql`
  subscription OnCategoryEventConnectionAdded(
    $userId: uuid!
    $createdDate: timestamptz!
  ) {
    Category_Event(
      where: { userId: { _eq: $userId }, createdDate: { _gt: $createdDate } }
      order_by: { createdDate: desc }
    ) {
      categoryId
      createdDate
      deleted
      eventId
      id
      updatedAt
      userId
    }
  }
`;
