import { gql } from '@apollo/client';

export default gql`
  mutation UpdateFeedbackForCount(
    $id: uuid!
    $lastSeen: timestamptz!
    $count: Int!
  ) {
    update_Feedback_by_pk(
      pk_columns: { id: $id }
      _set: { lastSeen: $lastSeen, count: $count }
    ) {
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
