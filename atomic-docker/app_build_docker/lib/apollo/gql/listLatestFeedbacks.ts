import { gql } from '@apollo/client';

export default gql`
  query ListLatestFeedbacks($userId: uuid!) {
    Feedback(
      where: { userId: { _eq: $userId } }
      order_by: { lastSeen: desc }
    ) {
      count
      createdDate
      deleted
      id
      lastSeen
      question1_A
      question1_B
      question1_C
      question2
      question3
      question4
      updatedAt
      userId
    }
  }
`;
