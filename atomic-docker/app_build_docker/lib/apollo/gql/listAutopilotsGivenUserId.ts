import { gql } from '@apollo/client';

export default gql`
  query ListAutopilotsGivenUserId($userId: uuid!) {
    Autopilot(where: { userId: { _eq: $userId } }) {
      createdDate
      id
      payload
      scheduleAt
      timezone
      updatedAt
      userId
    }
  }
`;
