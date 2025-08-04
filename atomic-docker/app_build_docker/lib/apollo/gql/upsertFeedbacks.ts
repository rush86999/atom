import { gql } from '@apollo/client';

export default gql`
  mutation InsertFeedback($feedbacks: [Feedback_insert_input!]!) {
    insert_Feedback(
      objects: $feedbacks
      on_conflict: {
        constraint: Feedback_pkey
        update_columns: [
          question1_A
          question1_B
          question1_C
          question2
          question3
          question4
          lastSeen
          count
          deleted
          updatedAt
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
