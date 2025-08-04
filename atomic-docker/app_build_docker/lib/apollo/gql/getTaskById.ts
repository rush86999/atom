import { gql } from '@apollo/client';

export default gql`
  query GetTaskById($id: uuid!) {
    Task_by_pk(id: $id) {
      completedDate
      createdDate
      duration
      eventId
      hardDeadline
      id
      important
      notes
      order
      parentId
      priority
      softDeadline
      status
      syncData
      updatedAt
      userId
      type
    }
  }
`;
