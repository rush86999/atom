import { gql } from '@apollo/client';

export default gql`
  mutation RemoveCategoriesForEvent($eventId: String!) {
    delete_Category_Event(where: { eventId: { _eq: $eventId } }) {
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
