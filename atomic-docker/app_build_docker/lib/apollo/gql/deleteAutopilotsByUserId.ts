import { gql } from '@apollo/client';

export default gql`
  mutation DeleteAutopilotsByUserId($userId: uuid!) {
    delete_Autopilot(where: { userId: { _eq: $userId } }) {
      affected_rows
      returning {
        createdDate
        id
        payload
        scheduleAt
        timezone
        updatedAt
        userId
      }
    }
  }
`;
